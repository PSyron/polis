"""Exact validation of dual-profile v2 threshold proposals."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from polis.evaluation.quality_protocol import InstallationProfile
from polis.evaluation.quality_report_baseline import (
    baseline_file_sha256,
    load_quality_report,
)
from polis.evaluation.quality_report_models import (
    PerformanceComparison,
    ProfileThresholdProposal,
    QualityReport,
    QualityReportError,
    ThresholdProposalV2,
)

_FAIL: Final = "fail"
_ENVIRONMENT_FIELDS: Final = (
    "python_version",
    "platform_system",
    "platform_release",
    "platform_machine",
)


def validate_threshold_proposal_v2(
    proposal: ThresholdProposalV2,
    default_baseline_path: Path,
    morphology_baseline_path: Path | None,
) -> None:
    """Bind both profile gates exactly to stable installed-wheel baselines."""

    if morphology_baseline_path is None:
        raise QualityReportError("v2 threshold proposal requires both baselines")
    if proposal.status != "pending_maintainer_approval":
        raise QualityReportError(
            "threshold proposal status must be pending_maintainer_approval"
        )
    if proposal.enforced:
        raise QualityReportError("threshold proposal must not be enforced")
    default = load_quality_report(default_baseline_path)
    morphology = load_quality_report(morphology_baseline_path)
    _validate_profile_binding(
        proposal.default, default, default_baseline_path, InstallationProfile.DEFAULT
    )
    _validate_profile_binding(
        proposal.morphology,
        morphology,
        morphology_baseline_path,
        InstallationProfile.MORPHOLOGY,
    )
    if proposal.dataset_sha256 != default.dataset_sha256:
        raise QualityReportError("threshold proposal dataset_sha256 mismatch")
    if default.dataset_sha256 != morphology.dataset_sha256:
        raise QualityReportError("threshold proposal baselines dataset mismatch")
    if {
        default.artifact_sha256,
        morphology.artifact_sha256,
    } != {proposal.artifact_sha256}:
        raise QualityReportError("threshold proposal artifact_sha256 mismatch")
    if {
        default.run_identity.source_sha,
        morphology.run_identity.source_sha,
    } != {proposal.source_git_sha}:
        raise QualityReportError("threshold proposal source_git_sha mismatch")
    for field in _ENVIRONMENT_FIELDS:
        if getattr(default.run_identity, field) != getattr(
            morphology.run_identity, field
        ):
            raise QualityReportError(
                "threshold proposal baselines environment mismatch"
            )


def _validate_profile_binding(
    proposal: ProfileThresholdProposal,
    baseline: QualityReport,
    baseline_path: Path,
    profile: InstallationProfile,
) -> None:
    if proposal.baseline_path != str(baseline_path):
        raise QualityReportError("threshold proposal baseline_path mismatch")
    if proposal.baseline_sha256 != baseline_file_sha256(baseline_path):
        raise QualityReportError("threshold proposal baseline_sha256 mismatch")
    identity = baseline.run_identity.profile
    if identity is None or identity.id is not profile:
        raise QualityReportError("threshold proposal baseline profile mismatch")
    if (
        proposal.planned_morphology_source_semantics
        != identity.planned_morphology_source_semantics
        or proposal.planned_non_morphology_source_semantics
        != identity.planned_non_morphology_source_semantics
    ):
        raise QualityReportError("threshold proposal profile semantics mismatch")
    quality = proposal.quality
    comparisons = (
        ("minimum_precision", quality.minimum_precision, baseline.quality_precision),
        ("minimum_recall", quality.minimum_recall, baseline.quality_recall),
        ("minimum_f1", quality.minimum_f1, baseline.quality_f1),
        (
            "minimum_exact_span_accuracy",
            quality.minimum_exact_span_accuracy,
            baseline.quality_span_accuracy,
        ),
        (
            "minimum_exact_correction_accuracy",
            quality.minimum_exact_correction_accuracy,
            baseline.quality_correction_accuracy,
        ),
        (
            "maximum_false_alarm_rate",
            quality.maximum_false_alarm_rate,
            baseline.quality_false_alarm_rate,
        ),
    )
    for name, proposed, measured in comparisons:
        if proposed != measured:
            raise QualityReportError(f"threshold proposal {name} mismatch")
    _validate_performance(proposal.performance, baseline)


def _validate_performance(
    comparison: PerformanceComparison, baseline: QualityReport
) -> None:
    expected = (
        (
            "maximum_p95_latency_ns",
            comparison.maximum_p95_latency_ns,
            baseline.latency.p95_ns,
        ),
        (
            "minimum_throughput_cases_per_second",
            comparison.minimum_throughput_cases_per_second,
            baseline.throughput.cases_per_second,
        ),
        (
            "maximum_peak_rss_bytes",
            comparison.maximum_peak_rss_bytes,
            baseline.resources.peak_rss_bytes,
        ),
        (
            "required_warmup_repetitions",
            comparison.required_warmup_repetitions,
            baseline.warmup_repetitions,
        ),
        (
            "required_measured_repetitions",
            comparison.required_measured_repetitions,
            baseline.measured_repetitions,
        ),
        ("allowed_regression_fraction", comparison.allowed_regression_fraction, 0.0),
        (
            "required_environment_match",
            comparison.required_environment_match,
            _ENVIRONMENT_FIELDS,
        ),
    )
    for name, proposed, measured in expected:
        if proposed != measured:
            raise QualityReportError(f"threshold proposal {name} mismatch")
    fail_policies = (
        ("missing_metric", comparison.missing_metric),
        ("nondeterminism", comparison.nondeterminism),
        ("environment_mismatch", comparison.environment_mismatch),
        ("performance_regression", comparison.performance_regression),
    )
    for name, policy in fail_policies:
        if policy != _FAIL:
            raise QualityReportError(f"threshold proposal {name} must be fail")
    if not comparison.require_identical_repetition_hashes:
        raise QualityReportError(
            "threshold proposal require_identical_repetition_hashes mismatch"
        )
