from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from polis.evaluation._synthetic_corpus_cli import parse_class_quotas
from polis.evaluation._synthetic_corpus_validation import validate_single_edit
from polis.evaluation.synthetic_corpus import (
    ClassDistribution,
    build_manifest,
    generate,
    serialize_corpus,
)

_PUNCTUATION_HEAVY_DISTRIBUTION: ClassDistribution = {
    "case": 2600,
    "agreement": 1500,
    "punctuation": 500,
    "diacritics": 400,
}


def test_generate_honors_explicit_class_distribution() -> None:
    corpus = generate(
        seed=426,
        count=5000,
        class_distribution=_PUNCTUATION_HEAVY_DISTRIBUTION,
    )

    assert corpus.class_counts == _PUNCTUATION_HEAVY_DISTRIBUTION
    assert corpus.class_counts["punctuation"] >= 500


def test_explicit_class_distribution_is_deterministic_and_reversible() -> None:
    first = generate(
        seed=451,
        count=5000,
        class_distribution=_PUNCTUATION_HEAVY_DISTRIBUTION,
    )
    second = generate(
        seed=451,
        count=5000,
        class_distribution=_PUNCTUATION_HEAVY_DISTRIBUTION,
    )

    assert (
        hashlib.sha256(serialize_corpus(first)).hexdigest()
        == hashlib.sha256(serialize_corpus(second)).hexdigest()
    )
    assert all(
        validate_single_edit(
            pair.incorrect_text,
            pair.correct_text,
            start=pair.start,
            end=pair.end,
            original=pair.original,
            suggestion=pair.suggestion,
        )
        for pair in first.pairs
    )


def test_manifest_records_requested_and_obtained_class_distributions() -> None:
    corpus = generate(
        seed=426,
        count=5000,
        class_distribution=_PUNCTUATION_HEAVY_DISTRIBUTION,
    )

    manifest = build_manifest(corpus, artifact_sha256="a" * 64)

    assert manifest["requested_class_distribution"] == (_PUNCTUATION_HEAVY_DISTRIBUTION)
    assert manifest["obtained_class_distribution"] == corpus.class_counts
    punctuation_source = next(
        source
        for source in manifest["sources"]
        if source["dataset_id"] == "synthetic-punctuation-development"
    )
    assert punctuation_source["license"] == "CC0-1.0"
    assert punctuation_source["source"] == "project-authored"


def test_explicit_distribution_does_not_mix_caller_provided_sources() -> None:
    distribution: ClassDistribution = {
        "case": 1,
        "agreement": 1,
        "punctuation": 1,
        "diacritics": 1,
    }

    corpus = generate(
        clean_texts=("Dobry dom, żółć.",),
        source_license="CC0-1.0",
        source_origin="test-authored",
        seed=426,
        count=4,
        class_distribution=distribution,
    )

    assert len(corpus.sources) == 1
    assert corpus.sources[0].dataset_id == "caller-provided"
    assert corpus.sources[0].source == "test-authored"


def test_class_quota_cli_rejects_duplicate_classes() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="duplicate"):
        parse_class_quotas(
            ("case=1", "case=2", "agreement=1", "punctuation=1", "diacritics=1")
        )


def test_module_cli_writes_requested_class_distribution(tmp_path: Path) -> None:
    corpus_path = tmp_path / "cases.jsonl"
    manifest_path = tmp_path / "manifest.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "polis.evaluation.synthetic_corpus",
            "--output",
            str(corpus_path),
            "--manifest",
            str(manifest_path),
            "--seed",
            "451",
            "--count",
            "5000",
            "--class-quota",
            "case=2600",
            "--class-quota",
            "agreement=1500",
            "--class-quota",
            "punctuation=500",
            "--class-quota",
            "diacritics=400",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert len(corpus_path.read_text(encoding="utf-8").splitlines()) == 5000
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["requested_class_distribution"] == (_PUNCTUATION_HEAVY_DISTRIBUTION)
    assert manifest["obtained_class_distribution"] == (_PUNCTUATION_HEAVY_DISTRIBUTION)
    assert manifest["holdout"] is False


@pytest.mark.parametrize(
    ("distribution", "count", "message"),
    (
        (
            {"case": 1, "agreement": 1, "punctuation": 1},
            4,
            "exactly all error classes",
        ),
        (
            {"case": 1, "agreement": 1, "punctuation": 1, "diacritics": 2},
            4,
            "sum to count",
        ),
        (
            {"case": 1, "agreement": 1, "punctuation": -1, "diacritics": 3},
            4,
            "non-negative integers",
        ),
        (
            {"case": 1, "agreement": 1, "punctuation": True, "diacritics": 1},
            4,
            "non-negative integers",
        ),
        (
            {
                "case": 1,
                "agreement": 1,
                "punctuation": 10_000,
                "diacritics": 1,
            },
            10_003,
            "punctuation.*capacity",
        ),
    ),
)
def test_generate_rejects_invalid_or_over_capacity_class_distribution(
    distribution: dict[str, int], count: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        generate(
            seed=426,
            count=count,
            class_distribution=cast(ClassDistribution, distribution),
        )
