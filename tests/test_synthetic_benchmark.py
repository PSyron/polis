from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import pytest

from polis.evaluation.synthetic_benchmark import (
    BenchmarkInputError,
    evaluate_benchmark,
)
from polis.evaluation.synthetic_corpus import generate, write_artifacts

type JsonValue = None | bool | int | str | list["JsonValue"] | dict[str, "JsonValue"]
type PredictionFactory = Callable[["_BenchmarkFixture"], list[JsonValue]]
type _Coverage = dict[str, dict[str, int] | int]
type _Split = dict[str, dict[str, list[str]]]


@dataclass(frozen=True, slots=True)
class _BenchmarkFixture:
    corpus_path: Path
    manifest_path: Path
    development_pair_id: str
    test_pair_id: str
    development_incorrect: str
    development_correct: str
    coverage: _Coverage
    split: _Split


def test_evaluate_benchmark_reports_declared_edit_and_abstention(
    tmp_path: Path,
) -> None:
    fixture = _write_validated_fixture(tmp_path)
    predictions_path = _write_predictions(
        tmp_path,
        [
            {
                "pair_id": fixture.development_pair_id,
                "edits": [{"start": 0, "end": 3, "replacement": "Ola"}],
            },
            {"pair_id": fixture.test_pair_id, "edits": []},
        ],
    )

    report = evaluate_benchmark(
        fixture.corpus_path, predictions_path, fixture.manifest_path
    )

    assert report["profile"] == "validated"
    assert report["generator_version"] == "polis-synthetic-corpus-v2-validated"
    assert report["score"] == {"total": 2, "accepted": 1, "abstained": 1}
    assert report["by_error_class"] == {
        "case": {"total": 1, "accepted": 1, "abstained": 0},
        "agreement": {"total": 1, "accepted": 0, "abstained": 1},
    }
    assert report["coverage"] == fixture.coverage
    assert report["split"] == fixture.split
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert fixture.development_incorrect not in serialized
    assert fixture.development_correct not in serialized


def test_evaluate_benchmark_consumes_generated_validated_partition_manifest(
    tmp_path: Path,
) -> None:
    corpus = generate(profile="validated", seed=426)
    corpus_path = tmp_path / "corpus.jsonl"
    manifest_path = tmp_path / "manifest.json"
    write_artifacts(corpus, corpus_path, manifest_path)
    predictions_path = _write_predictions(
        tmp_path,
        [
            {
                "pair_id": pair.id,
                "edits": [
                    {
                        "start": pair.start,
                        "end": pair.end,
                        "replacement": pair.suggestion,
                    }
                ],
            }
            for pair in corpus.pairs
        ],
    )

    report = evaluate_benchmark(corpus_path, predictions_path, manifest_path)

    assert report["profile"] == "validated"
    assert report["generator_version"] == "polis-synthetic-corpus-v2-validated"
    assert report["score"] == {
        "total": len(corpus.pairs),
        "accepted": len(corpus.pairs),
        "abstained": 0,
    }
    assert report["coverage"]["phenomenon_counts"]
    assert report["coverage"]["shape_strata_counts"]
    assert report["split"]["development"]["source_case_ids"]
    assert report["split"]["test"]["source_case_ids"]


@pytest.mark.parametrize(
    "make_predictions",
    [
        lambda fixture: [{"pair_id": "unknown", "edits": []}],
        lambda fixture: [{"pair_id": "", "edits": []}],
        lambda fixture: [
            {"pair_id": fixture.development_pair_id, "edits": []},
            {"pair_id": fixture.development_pair_id, "edits": []},
        ],
        lambda fixture: [
            {
                "pair_id": fixture.development_pair_id,
                "edits": [{"start": "0", "end": 3, "replacement": "Ola"}],
            }
        ],
        lambda fixture: [
            {
                "pair_id": fixture.development_pair_id,
                "edits": [{"start": -1, "end": 3, "replacement": "Ola"}],
            }
        ],
        lambda fixture: [
            {
                "pair_id": fixture.development_pair_id,
                "edits": [{"start": 0, "end": 999, "replacement": "Ola"}],
            }
        ],
        lambda fixture: [
            {
                "pair_id": fixture.development_pair_id,
                "edits": [
                    {"start": 0, "end": 3, "replacement": "Ola"},
                    {"start": 15, "end": 18, "replacement": "Ewa"},
                ],
            }
        ],
        lambda fixture: [
            {
                "pair_id": fixture.development_pair_id,
                "edits": [],
                "raw_response": "model prose is not a benchmark input",
            }
        ],
    ],
    ids=(
        "unknown-pair",
        "empty-pair-id",
        "duplicate-pair",
        "malformed-edit",
        "negative-span",
        "out-of-range-span",
        "two-disjoint-edits",
        "raw-model-response",
    ),
)
def test_evaluate_benchmark_rejects_invalid_prediction_records(
    tmp_path: Path, make_predictions: PredictionFactory
) -> None:
    fixture = _write_validated_fixture(tmp_path)
    predictions_path = _write_predictions(tmp_path, make_predictions(fixture))

    with pytest.raises(BenchmarkInputError):
        evaluate_benchmark(fixture.corpus_path, predictions_path, fixture.manifest_path)


@pytest.mark.parametrize("identity_key", ("source_case_ids", "correct_text_sha256"))
def test_evaluate_benchmark_rejects_source_disjoint_manifest_leakage(
    tmp_path: Path, identity_key: str
) -> None:
    fixture = _write_validated_fixture(tmp_path)
    manifest = json.loads(fixture.manifest_path.read_text(encoding="utf-8"))
    manifest["split"]["test"][identity_key] = manifest["split"]["development"][
        identity_key
    ]
    fixture.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    predictions_path = _write_predictions(
        tmp_path,
        [
            {"pair_id": fixture.development_pair_id, "edits": []},
            {"pair_id": fixture.test_pair_id, "edits": []},
        ],
    )

    with pytest.raises(BenchmarkInputError):
        evaluate_benchmark(fixture.corpus_path, predictions_path, fixture.manifest_path)


def test_evaluate_benchmark_failure_leaves_caller_report_absent(tmp_path: Path) -> None:
    fixture = _write_validated_fixture(tmp_path)
    predictions_path = _write_predictions(
        tmp_path, [{"pair_id": "unknown", "edits": []}]
    )
    report_path = tmp_path / "report.json"

    with pytest.raises(BenchmarkInputError):
        report = evaluate_benchmark(
            fixture.corpus_path, predictions_path, fixture.manifest_path
        )
        report_path.write_text(json.dumps(report), encoding="utf-8")

    assert not report_path.exists()


def _write_validated_fixture(tmp_path: Path) -> _BenchmarkFixture:
    development_incorrect = "Ala ma kota, a Ala ma psa."
    development_correct = "Ola ma kota, a Ala ma psa."
    test_incorrect = "Ten brat czyta książkę."
    test_correct = "Ta brat czyta książkę."
    records: list[JsonValue] = [
        {
            "id": "pair-development",
            "error_class": "case",
            "incorrect_text": development_incorrect,
            "correct_text": development_correct,
            "start": 0,
            "end": 3,
            "original": "Ala",
            "suggestion": "Ola",
            "source_dataset": "synthetic-test",
            "source_case_id": "source-development",
            "lemma": "Ala",
            "generated_tag": "case-government",
        },
        {
            "id": "pair-test",
            "error_class": "agreement",
            "incorrect_text": test_incorrect,
            "correct_text": test_correct,
            "start": 0,
            "end": 3,
            "original": "Ten",
            "suggestion": "Ta",
            "source_dataset": "synthetic-test",
            "source_case_id": "source-test",
            "lemma": "ten",
            "generated_tag": "agreement-number",
        },
    ]
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    coverage: _Coverage = {
        "phenomenon_counts": {"case-government": 1, "agreement-number": 1},
        "shape_strata_counts": {"simple-clause": 2},
        "hard_negative_count": 1,
    }
    split: _Split = {
        "development": {
            "pair_ids": ["pair-development"],
            "source_case_ids": ["source-development"],
            "correct_text_sha256": [_digest(development_correct)],
        },
        "test": {
            "pair_ids": ["pair-test"],
            "source_case_ids": ["source-test"],
            "correct_text_sha256": [_digest(test_correct)],
        },
    }
    manifest = {
        "schema_id": "polis.synthetic-corpus-manifest",
        "schema_version": 1,
        "profile": "validated",
        "generator_version": "polis-synthetic-corpus-v2-validated",
        "seed": 452,
        "requested_count": 2,
        "pair_count": 2,
        "class_counts": {"case": 1, "agreement": 1},
        "artifact_sha256": _digest(corpus_path.read_text(encoding="utf-8")),
        "license": "CC0-1.0",
        "source": "project-authored",
        "purpose": "repeatable-development-only",
        "holdout": False,
        "sources": [],
        "coverage": coverage,
        "split": split,
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    return _BenchmarkFixture(
        corpus_path=corpus_path,
        manifest_path=manifest_path,
        development_pair_id="pair-development",
        test_pair_id="pair-test",
        development_incorrect=development_incorrect,
        development_correct=development_correct,
        coverage=coverage,
        split=split,
    )


def _write_predictions(tmp_path: Path, records: list[JsonValue]) -> Path:
    path = tmp_path / "predictions.jsonl"
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    return path


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()
