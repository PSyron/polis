from __future__ import annotations

import json
from pathlib import Path

import pytest

from polis.evaluation.quality_report import (
    QualityReportError,
    baseline_file_sha256,
    load_quality_report,
    load_threshold_proposal,
    validate_threshold_proposal,
)
from polis.evaluation.quality_report_models import ThresholdProposalV3
from polis.evaluation.quality_report_result import load_quality_result

PROPOSAL_PATH = Path("docs/quality-threshold-proposal-v3.json")
DEFAULT_BASELINE_PATH = Path("docs/quality-baseline-v3-default.json")
MORPHOLOGY_BASELINE_PATH = Path("docs/quality-baseline-v3-morphology.json")
DEFAULT_RESULT_PATH = Path("docs/quality-result-wave0-default.json")
MORPHOLOGY_RESULT_PATH = Path("docs/quality-result-wave0-morphology.json")
V2_PROPOSAL_PATH = Path("docs/quality-threshold-proposal-v2.json")


def test_v3_proposal_binds_quality_to_v3_baselines_and_performance_to_wave0() -> None:
    default = load_quality_report(DEFAULT_BASELINE_PATH)
    morphology = load_quality_report(MORPHOLOGY_BASELINE_PATH)
    default_result = load_quality_result(DEFAULT_RESULT_PATH)
    morphology_result = load_quality_result(MORPHOLOGY_RESULT_PATH)

    proposal = _load_v3_proposal()
    validate_threshold_proposal(
        proposal,
        baseline_path=DEFAULT_BASELINE_PATH,
        morphology_baseline_path=MORPHOLOGY_BASELINE_PATH,
    )

    assert isinstance(proposal, ThresholdProposalV3)
    assert proposal.dataset_sha256 == default.dataset_sha256
    assert proposal.dataset_sha256 == morphology.dataset_sha256
    assert proposal.default.baseline_sha256 == baseline_file_sha256(
        DEFAULT_BASELINE_PATH
    )
    assert proposal.morphology.baseline_sha256 == baseline_file_sha256(
        MORPHOLOGY_BASELINE_PATH
    )
    assert proposal.default.quality.minimum_precision == default.quality_precision
    assert proposal.default.quality.minimum_recall == default.quality_recall
    assert proposal.default.quality.minimum_f1 == default.quality_f1
    assert (
        proposal.default.quality.minimum_exact_span_accuracy
        == default.quality_span_accuracy
    )
    assert (
        proposal.default.quality.minimum_exact_correction_accuracy
        == default.quality_correction_accuracy
    )
    assert (
        proposal.default.quality.maximum_false_alarm_rate
        == default.quality_false_alarm_rate
    )
    assert proposal.morphology.quality.minimum_precision == morphology.quality_precision
    assert (
        proposal.default.performance.maximum_p95_latency_ns
        == default_result.latency.p95_ns
    )
    assert (
        proposal.morphology.performance.maximum_p95_latency_ns
        == morphology_result.latency.p95_ns
    )
    assert (
        proposal.default.performance.minimum_throughput_cases_per_second
        == default_result.throughput.cases_per_second
    )
    assert (
        proposal.morphology.performance.minimum_throughput_cases_per_second
        == morphology_result.throughput.cases_per_second
    )
    assert proposal.default.performance_result_path == str(DEFAULT_RESULT_PATH)
    assert proposal.morphology.performance_result_path == str(MORPHOLOGY_RESULT_PATH)
    assert proposal.quality_artifact_sha256 == default.artifact_sha256
    assert proposal.performance_artifact_sha256 == default_result.artifact_sha256
    assert proposal.status == "pending_maintainer_approval"
    assert proposal.enforced is False


def test_v3_proposal_records_zero_tolerance_fail_closed_performance_rules() -> None:
    proposal = _load_v3_proposal()
    for profile in (proposal.default, proposal.morphology):
        comparison = profile.performance
        assert comparison.allowed_regression_fraction == 0.0
        assert comparison.missing_metric == "fail"
        assert comparison.nondeterminism == "fail"
        assert comparison.environment_mismatch == "fail"
        assert comparison.performance_regression == "fail"
        assert comparison.require_identical_repetition_hashes is True
        assert comparison.required_environment_match == (
            "python_version",
            "platform_system",
            "platform_release",
            "platform_machine",
        )


def test_v3_proposal_rejects_quality_floor_drift() -> None:
    raw = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
    raw["profiles"]["default"]["quality_floors"]["minimum_recall"] = 0.0
    path = Path("/tmp/polis-v3-proposal-drift.json")
    path.write_text(json.dumps(raw), encoding="utf-8")
    proposal = load_threshold_proposal(path)
    with pytest.raises(QualityReportError, match="minimum_recall"):
        validate_threshold_proposal(
            proposal,
            baseline_path=DEFAULT_BASELINE_PATH,
            morphology_baseline_path=MORPHOLOGY_BASELINE_PATH,
        )


def test_v3_proposal_rejects_wave0_performance_drift() -> None:
    raw = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
    raw["profiles"]["default"]["performance_comparison"]["maximum_p95_latency_ns"] = 1
    path = Path("/tmp/polis-v3-proposal-perf-drift.json")
    path.write_text(json.dumps(raw), encoding="utf-8")
    proposal = load_threshold_proposal(path)
    with pytest.raises(QualityReportError, match="maximum_p95_latency_ns"):
        validate_threshold_proposal(
            proposal,
            baseline_path=DEFAULT_BASELINE_PATH,
            morphology_baseline_path=MORPHOLOGY_BASELINE_PATH,
        )


def test_v2_proposal_remains_valid_and_byte_stable() -> None:
    proposal = load_threshold_proposal(V2_PROPOSAL_PATH)
    validate_threshold_proposal(
        proposal,
        baseline_path=Path("docs/quality-baseline-v2-default.json"),
        morphology_baseline_path=Path("docs/quality-baseline-v2-morphology.json"),
    )
    assert V2_PROPOSAL_PATH.exists()


def _load_v3_proposal() -> ThresholdProposalV3:
    proposal = load_threshold_proposal(PROPOSAL_PATH)
    assert isinstance(proposal, ThresholdProposalV3)
    return proposal
