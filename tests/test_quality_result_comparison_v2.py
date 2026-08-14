from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from polis.evaluation.quality_report import (
    QualityReportError,
    baseline_file_sha256,
    load_quality_comparison,
    load_quality_report,
    load_quality_result,
    load_threshold_proposal,
    validate_threshold_proposal,
)
from polis.evaluation.quality_report_models import ThresholdProposalV2

ROOT = Path(__file__).resolve().parents[1]
RESULT_DEFAULT = ROOT / "docs/quality-result-v2-default.json"
RESULT_MORPHOLOGY = ROOT / "docs/quality-result-v2-morphology.json"
COMPARISON = ROOT / "docs/quality-comparison-v2.json"
PROPOSAL = Path("docs/quality-threshold-proposal-v2.json")
BASELINE_DEFAULT = Path("docs/quality-baseline-v2-default.json")
BASELINE_MORPHOLOGY = Path("docs/quality-baseline-v2-morphology.json")
PROTECTED = {
    ROOT / "docs/quality-baseline-v2-default.json": (
        "c1d0c19d6b0a5f7dbec1c36df28917b908b3d0a78dba32285f45e990e64f8b95"
    ),
    ROOT / "docs/quality-baseline-v2-morphology.json": (
        "6ee2fea48983d8c29346a9e8eebf3859cfc1d6e12d9c48e05a3ef399af4415a7"
    ),
    ROOT / "docs/quality-threshold-proposal-v2.json": (
        "982a4c91809d71ccd90fc3575ea5ae812c92126e964515f2a5f183be95ed3875"
    ),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_protected_prechange_artifacts_remain_byte_identical() -> None:
    for path, digest in PROTECTED.items():
        assert _sha(path) == digest


def test_result_reports_parse_and_bind_to_installed_measurement() -> None:
    default = load_quality_result(RESULT_DEFAULT)
    morphology = load_quality_result(RESULT_MORPHOLOGY)
    proposal = load_threshold_proposal(PROPOSAL)
    assert isinstance(proposal, ThresholdProposalV2)

    assert default.run_identity.profile is not None
    assert morphology.run_identity.profile is not None
    assert default.run_identity.profile.id.value == "default"
    assert morphology.run_identity.profile.id.value == "morphology"
    assert default.dataset_sha256 == proposal.dataset_sha256
    assert morphology.dataset_sha256 == proposal.dataset_sha256
    assert default.artifact_sha256 == morphology.artifact_sha256
    assert default.run_identity.source_sha == morphology.run_identity.source_sha
    assert default.quality_precision == 1.0
    assert morphology.quality_precision == 1.0
    assert default.quality_false_alarm_rate == 0.0
    assert morphology.quality_false_alarm_rate == 0.0
    assert default.counts.true_positives == 22
    assert morphology.counts.true_positives == 43
    assert len(set(default.repetition_hashes)) == 1
    assert len(set(morphology.repetition_hashes)) == 1


def test_quality_floors_pass_while_absolute_performance_caps_fail_closed() -> None:
    comparison = load_quality_comparison(COMPARISON)
    proposal = load_threshold_proposal(PROPOSAL)
    assert isinstance(proposal, ThresholdProposalV2)
    default = load_quality_result(RESULT_DEFAULT)
    morphology = load_quality_result(RESULT_MORPHOLOGY)

    for profile_id, result, floors in (
        ("default", default, proposal.default.quality),
        ("morphology", morphology, proposal.morphology.quality),
    ):
        profile = comparison.profiles[profile_id]
        quality_gates = {
            gate.gate: gate.passed
            for gate in profile.gates
            if gate.gate.startswith("quality.")
        }
        assert quality_gates["quality.minimum_precision"] is True
        assert quality_gates["quality.minimum_recall"] is True
        assert quality_gates["quality.minimum_f1"] is True
        assert quality_gates["quality.minimum_exact_span_accuracy"] is True
        assert quality_gates["quality.minimum_exact_correction_accuracy"] is True
        assert quality_gates["quality.maximum_false_alarm_rate"] is True
        assert result.quality_precision is not None
        assert result.quality_recall is not None
        assert result.quality_f1 is not None
        assert result.quality_span_accuracy is not None
        assert result.quality_correction_accuracy is not None
        assert result.quality_false_alarm_rate is not None
        assert floors.minimum_precision is not None
        assert floors.minimum_recall is not None
        assert floors.minimum_f1 is not None
        assert floors.minimum_exact_span_accuracy is not None
        assert floors.minimum_exact_correction_accuracy is not None
        assert floors.maximum_false_alarm_rate is not None
        assert result.quality_precision >= floors.minimum_precision
        assert result.quality_recall >= floors.minimum_recall
        assert result.quality_f1 >= floors.minimum_f1
        assert result.quality_span_accuracy >= floors.minimum_exact_span_accuracy
        assert (
            result.quality_correction_accuracy
            >= floors.minimum_exact_correction_accuracy
        )
        assert result.quality_false_alarm_rate <= floors.maximum_false_alarm_rate

    # Absolute pre-change performance caps remain fail-closed under zero tolerance.
    assert comparison.aggregate_verdict == "fail"
    assert comparison.profiles["default"].verdict == "fail"
    assert comparison.profiles["morphology"].verdict == "fail"
    assert any(
        gate.gate.startswith("performance.") and not gate.passed
        for gate in comparison.profiles["default"].gates
    )


def test_comparison_binds_hashes_and_rejects_unknown_fields(tmp_path: Path) -> None:
    comparison = load_quality_comparison(COMPARISON)
    assert comparison.proposal_sha256 == _sha(PROPOSAL)
    assert comparison.profiles["default"].baseline_sha256 == baseline_file_sha256(
        BASELINE_DEFAULT
    )
    assert comparison.profiles["morphology"].baseline_sha256 == baseline_file_sha256(
        BASELINE_MORPHOLOGY
    )
    assert comparison.profiles["default"].result_sha256 == _sha(RESULT_DEFAULT)
    assert comparison.profiles["morphology"].result_sha256 == _sha(RESULT_MORPHOLOGY)
    assert len(comparison.source_git_sha) == 40

    payload = json.loads(COMPARISON.read_text(encoding="utf-8"))
    payload["unexpected"] = True
    bad = tmp_path / "bad-comparison.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(QualityReportError, match="unexpected"):
        load_quality_comparison(bad)


def test_result_parser_rejects_wrong_schema(tmp_path: Path) -> None:
    payload = json.loads(RESULT_DEFAULT.read_text(encoding="utf-8"))
    payload["schema_id"] = "polis.quality-baseline"
    bad = tmp_path / "bad-result.json"
    bad.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(QualityReportError, match="schema_id"):
        load_quality_result(bad)


def test_proposal_still_validates_against_unchanged_baselines() -> None:
    proposal = load_threshold_proposal(PROPOSAL)
    validate_threshold_proposal(
        proposal,
        baseline_path=BASELINE_DEFAULT,
        morphology_baseline_path=BASELINE_MORPHOLOGY,
    )
    assert load_quality_report(BASELINE_DEFAULT).counts.true_positives == 6
    assert load_quality_report(BASELINE_MORPHOLOGY).counts.true_positives == 10


def test_result_and_comparison_contain_no_plaintext_case_fields() -> None:
    for path in (RESULT_DEFAULT, RESULT_MORPHOLOGY, COMPARISON):
        text = path.read_text(encoding="utf-8")
        for banned in (
            "Szukam klucz",
            "Narazie",
            "wogole",
            "Ta nowy",
            "Przyglądam",
            "Kiedy pada",
            "original_text",
            "gold_text",
        ):
            assert banned not in text
