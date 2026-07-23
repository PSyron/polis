from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import pytest
from experiments.sentence_safety_gate.gate import (
    FreezeInputs,
    GoldEdit,
    RunnerObservation,
    SentenceCase,
    canonical_json_sha256,
    freeze_gate,
    load_development_sentences,
    load_gate_config,
    load_reserved_holdout_sentences,
    reserve_holdout_once,
    score_exact_edits,
    validate_privacy_safe_report,
    validate_runner_response,
    verify_frozen_gate,
)
from experiments.sentence_safety_gate.run_evaluation import (
    CaseRun,
    PerformanceEvidence,
    parse_arguments,
    summarize_split,
)

ROOT = Path(__file__).resolve().parents[1]
SAFETY_XML = (
    ROOT
    / "tests"
    / "fixtures"
    / "evaluation"
    / "polish_correction_safety_corpus_v1.xml"
)
REAL_MARKER = ROOT / "experiments" / "sentence_safety_gate" / "holdout.started"
FROZEN_GATE = ROOT / "experiments" / "sentence_safety_gate" / "frozen_gate.json"
FINAL_REPORT = ROOT / "experiments" / "sentence_safety_gate" / "report.json"
EVALUATED_SOURCE = (
    ROOT / "experiments" / "sentence_safety_gate" / "evaluated_source.json"
)
CONFIG = ROOT / "experiments" / "sentence_safety_gate" / "config.json"


def test_development_loader_materializes_exactly_80_without_holdout() -> None:
    materialized: list[str] = []

    cases = load_development_sentences(
        SAFETY_XML,
        on_materialized=materialized.append,
    )

    assert len(cases) == 80
    assert {case.split for case in cases} == {"development"}
    assert materialized == [case.case_id for case in cases]
    assert all(int(case_id[-3:]) <= 20 for case_id in materialized)


def test_empty_prediction_precision_is_undefined() -> None:
    counts = score_exact_edits(
        (GoldEdit("syntax", 0, 1, "x", "y"),),
        (),
    )

    assert counts.precision is None
    assert counts.recall == 0.0


def test_real_holdout_marker_retains_the_failed_one_shot_verdict() -> None:
    marker = json.loads(REAL_MARKER.read_text(encoding="utf-8"))
    frozen = json.loads(FROZEN_GATE.read_text(encoding="utf-8"))
    report = validate_privacy_safe_report(
        json.loads(FINAL_REPORT.read_text(encoding="utf-8"))
    )

    assert marker == frozen
    assert report["decision"] == {"qualified": False, "scope": "sentence_only"}
    holdout = report["holdout"]
    assert isinstance(holdout, dict)
    assert holdout["total_cases"] == 160
    assert holdout["decision"] == {"qualified": False}


def test_evaluated_source_provenance_matches_frozen_artifacts() -> None:
    provenance = json.loads(EVALUATED_SOURCE.read_text(encoding="utf-8"))
    frozen = json.loads(FROZEN_GATE.read_text(encoding="utf-8"))

    assert set(provenance) == {
        "evaluated_commit",
        "evaluated_tree",
        "post_verdict_changes_are_not_evaluated",
        "schema_version",
        "sdist_sha256",
        "wheel_sha256",
    }
    assert provenance["schema_version"] == 1
    assert provenance["evaluated_commit"] == (
        "24cda9ae664bcdf9d486ae713ad426257e614085"
    )
    assert provenance["evaluated_tree"] == ("f42ff0b8ccb5a4241c10be2dcd1a0c8976a635b8")
    assert provenance["wheel_sha256"] == frozen["wheel_sha256"]
    assert provenance["sdist_sha256"] == frozen["sdist_sha256"]
    assert provenance["post_verdict_changes_are_not_evaluated"] is True


def test_committed_configuration_targets_only_the_safety_corpus() -> None:
    config = load_gate_config(CONFIG)

    assert config.experiment_id == "polis-installed-sentence-safety-gate-v1"
    assert config.corpus_id == "polis_polish_correction_safety_corpus_v1"
    assert config.canonical_corpus_digest == (
        "2fc05cd5552071ade7b392b3075d15bfaf57cf3f4b84df450c605b48d1615982"
    )
    assert config.corpus_sha256 == (
        "921ce0accd120e443a9131f192b8669484d4dd24bf18898fbd2ebcafbe1a87d9"
    )
    assert config.corpus_xml_sha256 == (
        "f2fcefef2172efcf3e27338bacc106230cde48b37c3c6989a4803bddc8dcc908"
    )
    assert "corpus_v3" not in CONFIG.read_text(encoding="utf-8")


def test_configuration_rejects_a_different_canonical_corpus_digest(
    tmp_path: Path,
) -> None:
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw["corpus"]["canonical_digest"] = "0" * 64
    changed = tmp_path / "config.json"
    changed.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="canonical safety corpus digest"):
        load_gate_config(changed)


def test_exact_scorer_rejects_duplicate_edits() -> None:
    duplicate = GoldEdit("syntax", 0, 1, "x", "y")

    with pytest.raises(ValueError, match="duplicates"):
        score_exact_edits((duplicate, duplicate), ())


def test_freeze_binds_files_directories_and_development_report(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.py"
    source.write_text("first\n", encoding="utf-8")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "manifest.json").write_text("{}\n", encoding="utf-8")
    frozen_path = tmp_path / "frozen.json"
    inputs = FreezeInputs(files={"source": source}, directories={"runtime": runtime})
    report = {"development": {"decision": "qualified"}}

    frozen = freeze_gate(inputs, frozen_path, development_report=report)

    assert frozen.development_report_sha256 == canonical_json_sha256(report)
    assert (
        verify_frozen_gate(
            frozen_path,
            inputs,
            development_report=report,
        )
        == frozen
    )
    source.write_text("changed\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        verify_frozen_gate(frozen_path, inputs, development_report=report)


def test_holdout_reservation_is_atomic_and_cannot_repeat(tmp_path: Path) -> None:
    source = tmp_path / "source.py"
    source.write_text("frozen\n", encoding="utf-8")
    frozen_path = tmp_path / "frozen.json"
    marker = tmp_path / "holdout.started"
    inputs = FreezeInputs(files={"source": source}, directories={})
    report = {"development": {"decision": "qualified"}}
    freeze_gate(inputs, frozen_path, development_report=report)

    reserve_holdout_once(
        frozen_path,
        marker,
        inputs,
        development_report=report,
    )

    assert json.loads(marker.read_text(encoding="utf-8"))
    with pytest.raises(FileExistsError, match="already reserved"):
        reserve_holdout_once(
            frozen_path,
            marker,
            inputs,
            development_report=report,
        )


def test_holdout_reservation_is_durable_before_returning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.py"
    source.write_text("frozen\n", encoding="utf-8")
    frozen_path = tmp_path / "frozen.json"
    marker = tmp_path / "holdout.started"
    inputs = FreezeInputs(files={"source": source}, directories={})
    report = {"development": {"decision": "qualified"}}
    freeze_gate(inputs, frozen_path, development_report=report)
    fsynced: list[int] = []
    monkeypatch.setattr(os, "fsync", fsynced.append)

    reserve_holdout_once(
        frozen_path,
        marker,
        inputs,
        development_report=report,
    )

    expected_calls = 2 if os.name == "posix" else 1
    assert len(fsynced) == expected_calls


def test_holdout_loader_rejects_access_before_marker(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="reserved"):
        load_reserved_holdout_sentences(
            tmp_path / "corpus.json",
            tmp_path / "missing.started",
            tmp_path / "frozen.json",
            FreezeInputs(files={"gate": tmp_path / "gate.py"}, directories={}),
        )


@pytest.mark.parametrize(
    "unsafe_report",
    [
        {"case": {"text": "Prywatne zdanie."}},
        {"case": {"expected_output": "Poufna odpowiedź."}},
        {"environment": {"path": "/Users/example/private"}},
    ],
)
def test_privacy_safe_report_rejects_text_and_private_paths(
    unsafe_report: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="cannot contain"):
        validate_privacy_safe_report(unsafe_report)


def _finding(
    *,
    finding_id: str = "finding-1",
    start: int = 4,
    end: int = 4,
    original: str = "",
    suggestion: str = ",",
) -> dict[str, object]:
    return {
        "id": finding_id,
        "category": "punctuation",
        "severity": "warning",
        "original": original,
        "suggestion": suggestion,
        "start": start,
        "end": end,
        "confidence": 1.0,
        "source": "rule:syntax.comma_space",
    }


def _runner_response() -> dict[str, object]:
    finding = _finding()
    return {
        "schema_version": 1,
        "request_id": 1,
        "status": "complete",
        "analysis_findings": [finding],
        "automatic_findings": [finding],
        "reviewable_findings": [],
        "corrected_text": "Wiem, że wróci.",
        "selected_text": "Wiem, że wróci.",
        "selected_finding_ids": [],
        "suggestion_outcomes": [],
        "elapsed_ms": 1.0,
        "python_rss_bytes": 10,
        "child_rss_bytes": 20,
        "combined_rss_bytes": 30,
        "python_peak_rss_bytes": 11,
        "child_peak_rss_bytes": 22,
        "combined_peak_rss_bytes": 33,
        "model_calls": 0,
        "process_start_count": 1,
    }


def test_runner_response_reconstructs_exact_original_text_edits() -> None:
    observation = validate_runner_response(
        "Wiem że wróci.",
        _runner_response(),
    )

    assert observation.corrected_text == "Wiem, że wróci."
    assert observation.process_start_count == 1


def test_runner_response_rejects_offset_not_matching_original_text() -> None:
    response = _runner_response()
    response["analysis_findings"] = [
        _finding(start=5, end=7, original="xx", suggestion=",")
    ]
    response["automatic_findings"] = response["analysis_findings"]

    with pytest.raises(ValueError, match="original"):
        validate_runner_response("Wiem że wróci.", response)


def test_empty_channels_serialize_undefined_metrics_as_null() -> None:
    case = SentenceCase(
        case_id="safety_hard_negative_001",
        stratum="hard_negative",
        split="development",
        source="To zdanie jest poprawne.",
        expected_output="To zdanie jest poprawne.",
        gold_edits=(),
        tags=("hard_negative",),
    )
    observation = RunnerObservation(
        request_id=1,
        automatic_edits=(),
        reviewable_edits=(),
        analysis_finding_ids=(),
        corrected_text=case.source,
        selected_text=case.source,
        suggestion_outcomes=(),
        elapsed_ms=1.0,
        python_rss_bytes=10,
        child_rss_bytes=20,
        combined_rss_bytes=30,
        python_peak_rss_bytes=11,
        child_peak_rss_bytes=22,
        combined_peak_rss_bytes=33,
        model_calls=0,
        process_start_count=1,
    )
    performance = PerformanceEvidence(
        cold_e2e_ms=2.0,
        warm_in_process_p50_ms=1.0,
        warm_in_process_p95_ms=1.0,
        warm_e2e_p50_ms=1.0,
        warm_e2e_p95_ms=1.0,
        cases_per_second=1.0,
        characters_per_second=10.0,
        python_loaded_rss_bytes=10,
        child_loaded_rss_bytes=20,
        combined_loaded_rss_bytes=30,
        python_peak_rss_bytes=11,
        child_peak_rss_bytes=22,
        combined_peak_rss_bytes=33,
        swap_delta_bytes=0,
        socket_count=0,
        model_calls=0,
        process_start_count=1,
        stable_repetitions=2,
    )

    report = summarize_split(
        (CaseRun(case, observation, 1.0, "0" * 64),),
        performance,
    )
    automatic = cast(dict[str, Any], report["automatic"])
    reviewable = cast(dict[str, Any], report["reviewable"])

    assert automatic["precision"] is None
    assert automatic["correction_accuracy"] is None
    assert reviewable["precision"] is None
    assert reviewable["correction_accuracy"] is None


def test_evaluator_cli_requires_exactly_one_mode() -> None:
    with pytest.raises(SystemExit):
        parse_arguments([])


def test_evaluator_cli_supports_reversible_preflight_without_output() -> None:
    arguments = parse_arguments(
        [
            "--preflight",
            "--dist",
            "/private/tmp/dist",
            "--vendored-stdio",
            "/private/tmp/run_stdio.sh",
        ]
    )

    assert arguments.preflight is True
    assert arguments.output is None
    assert arguments.freeze is None


def test_development_verification_requires_report_and_freeze() -> None:
    with pytest.raises(SystemExit):
        parse_arguments(
            [
                "--verify-development",
                "--dist",
                "/private/tmp/dist",
                "--vendored-stdio",
                "/private/tmp/run_stdio.sh",
            ]
        )
