from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import assert_never

import pytest

from polis.evaluation.quality_report import (
    QualityReportError,
    baseline_file_sha256,
    load_quality_report,
    load_threshold_proposal,
    validate_threshold_proposal,
)
from polis.evaluation.quality_report_models import (
    ThresholdProposal,
    ThresholdProposalV2,
)

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL_PATH = Path("docs/quality-threshold-proposal-v2.json")
DEFAULT_BASELINE_PATH = Path("docs/quality-baseline-v2-default.json")
MORPHOLOGY_BASELINE_PATH = Path("docs/quality-baseline-v2-morphology.json")
V1_PROPOSAL_SHA256 = "25dbbdbc2dda1ca654e402962b74f097aa8429d675cc8fd90a6f74fb815a7ba6"


def test_v2_proposal_binds_both_measured_profiles_exactly() -> None:
    # Given
    default = load_quality_report(DEFAULT_BASELINE_PATH)
    morphology = load_quality_report(MORPHOLOGY_BASELINE_PATH)

    # When
    proposal = _load_v2_proposal()
    validate_threshold_proposal(
        proposal,
        baseline_path=DEFAULT_BASELINE_PATH,
        morphology_baseline_path=MORPHOLOGY_BASELINE_PATH,
    )

    # Then
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
    assert proposal.status == "pending_maintainer_approval"
    assert proposal.enforced is False


def test_v2_proposal_records_zero_tolerance_fail_closed_performance_rules() -> None:
    # Given
    default = load_quality_report(DEFAULT_BASELINE_PATH)
    morphology = load_quality_report(MORPHOLOGY_BASELINE_PATH)

    # When
    proposal = _load_v2_proposal()

    # Then
    for profile, baseline in (
        (proposal.default, default),
        (proposal.morphology, morphology),
    ):
        comparison = profile.performance
        assert comparison.maximum_p95_latency_ns == baseline.latency.p95_ns
        assert (
            comparison.minimum_throughput_cases_per_second
            == baseline.throughput.cases_per_second
        )
        assert comparison.maximum_peak_rss_bytes == baseline.resources.peak_rss_bytes
        assert comparison.required_warmup_repetitions == 1
        assert comparison.required_measured_repetitions == 5
        assert comparison.require_identical_repetition_hashes is True
        assert comparison.required_environment_match == (
            "python_version",
            "platform_system",
            "platform_release",
            "platform_machine",
        )
        assert comparison.allowed_regression_fraction == 0.0
        assert comparison.missing_metric == "fail"
        assert comparison.nondeterminism == "fail"
        assert comparison.environment_mismatch == "fail"
        assert comparison.performance_regression == "fail"


@pytest.mark.parametrize(
    ("profile_name", "section", "metric", "value", "message"),
    (
        ("default", "quality_floors", "minimum_recall", 0.0, "minimum_recall"),
        (
            "morphology",
            "quality_floors",
            "minimum_exact_span_accuracy",
            0.0,
            "minimum_exact_span_accuracy",
        ),
        (
            "default",
            "performance_comparison",
            "maximum_p95_latency_ns",
            0,
            "maximum_p95_latency_ns",
        ),
        (
            "morphology",
            "performance_comparison",
            "minimum_throughput_cases_per_second",
            0.0,
            "minimum_throughput_cases_per_second",
        ),
        (
            "default",
            "performance_comparison",
            "allowed_regression_fraction",
            0.1,
            "allowed_regression_fraction",
        ),
        (
            "default",
            "performance_comparison",
            "allowed_regression_fraction",
            None,
            "allowed_regression_fraction",
        ),
        (
            "morphology",
            "performance_comparison",
            "missing_metric",
            "ignore",
            "missing_metric",
        ),
    ),
)
def test_v2_proposal_rejects_gate_drift(
    tmp_path: Path,
    profile_name: str,
    section: str,
    metric: str,
    value: str | float | int | None,
    message: str,
) -> None:
    # Given
    payload = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
    payload["profiles"][profile_name][section][metric] = value
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(payload), encoding="utf-8")

    # When / Then
    with pytest.raises(QualityReportError, match=message):
        validate_threshold_proposal(
            load_threshold_proposal(proposal_path),
            baseline_path=DEFAULT_BASELINE_PATH,
            morphology_baseline_path=MORPHOLOGY_BASELINE_PATH,
        )


def test_v2_proposal_fails_closed_when_a_required_metric_is_missing(
    tmp_path: Path,
) -> None:
    # Given
    payload = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
    del payload["profiles"]["default"]["quality_floors"]["minimum_f1"]
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(payload), encoding="utf-8")

    # When / Then
    with pytest.raises(QualityReportError, match="missing fields"):
        load_threshold_proposal(proposal_path)


def test_v2_proposal_rejects_cross_profile_environment_mismatch(
    tmp_path: Path,
) -> None:
    # Given
    default_path = tmp_path / "default.json"
    morphology_path = tmp_path / "morphology.json"
    default_path.write_bytes(DEFAULT_BASELINE_PATH.read_bytes())
    morphology_payload = json.loads(
        MORPHOLOGY_BASELINE_PATH.read_text(encoding="utf-8")
    )
    morphology_payload["environment"]["platform_release"] = "different"
    morphology_path.write_text(json.dumps(morphology_payload), encoding="utf-8")
    proposal_payload = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
    proposal_payload["profiles"]["default"]["baseline_path"] = str(default_path)
    proposal_payload["profiles"]["default"]["baseline_sha256"] = baseline_file_sha256(
        default_path
    )
    proposal_payload["profiles"]["morphology"]["baseline_path"] = str(morphology_path)
    proposal_payload["profiles"]["morphology"]["baseline_sha256"] = (
        baseline_file_sha256(morphology_path)
    )
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal_payload), encoding="utf-8")

    # When / Then
    with pytest.raises(QualityReportError, match="environment mismatch"):
        validate_threshold_proposal(
            load_threshold_proposal(proposal_path),
            baseline_path=default_path,
            morphology_baseline_path=morphology_path,
        )


def test_v2_proposal_fails_closed_on_nondeterministic_baseline(
    tmp_path: Path,
) -> None:
    # Given
    default_payload = json.loads(DEFAULT_BASELINE_PATH.read_text(encoding="utf-8"))
    default_payload["reproducibility"]["repetition_hashes"][-1] = "0" * 64
    default_path = tmp_path / "default.json"
    default_path.write_text(json.dumps(default_payload), encoding="utf-8")
    proposal_payload = json.loads(PROPOSAL_PATH.read_text(encoding="utf-8"))
    proposal_payload["profiles"]["default"]["baseline_path"] = str(default_path)
    proposal_payload["profiles"]["default"]["baseline_sha256"] = baseline_file_sha256(
        default_path
    )
    proposal_path = tmp_path / "proposal.json"
    proposal_path.write_text(json.dumps(proposal_payload), encoding="utf-8")

    # When / Then
    with pytest.raises(QualityReportError, match="measurement evidence"):
        validate_threshold_proposal(
            load_threshold_proposal(proposal_path),
            baseline_path=default_path,
            morphology_baseline_path=MORPHOLOGY_BASELINE_PATH,
        )


def test_v1_proposal_remains_byte_identical_and_valid() -> None:
    # Given
    proposal_path = ROOT / "docs/quality-threshold-proposal-v1.json"
    baseline_path = Path("docs/quality-baseline-v1.json")

    # When
    proposal = load_threshold_proposal(proposal_path)
    validate_threshold_proposal(proposal, baseline_path=baseline_path)

    # Then
    assert hashlib.sha256(proposal_path.read_bytes()).hexdigest() == V1_PROPOSAL_SHA256


def _load_v2_proposal() -> ThresholdProposalV2:
    proposal = load_threshold_proposal(PROPOSAL_PATH)
    match proposal:
        case ThresholdProposalV2():
            return proposal
        case ThresholdProposal():
            pytest.fail("expected a v2 threshold proposal")
        case unreachable:
            assert_never(unreachable)
