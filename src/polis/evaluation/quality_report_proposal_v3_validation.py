"""Exact validation of dual-profile v3 threshold proposals."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

from polis.evaluation.quality_protocol import InstallationProfile
from polis.evaluation.quality_report_baseline import (
    baseline_file_sha256,
    load_quality_report,
)
from polis.evaluation.quality_report_models import (
    PerformanceComparison,
    ProfileThresholdProposalV3,
    QualityReport,
    QualityReportError,
    ThresholdProposalV3,
)
from polis.evaluation.quality_report_result import load_quality_result

_FAIL: Final = "fail"
_ENVIRONMENT_FIELDS: Final = (
    "python_version",
    "platform_system",
    "platform_release",
    "platform_machine",
)


def validate_threshold_proposal_v3(
    proposal: ThresholdProposalV3,
    default_baseline_path: Path,
    morphology_baseline_path: Path | None,
) -> None:
    """Bind quality floors to v3 baselines and performance to wave0 results."""

    if morphology_baseline_path is None:
        raise QualityReportError("v3 threshold proposal requires both baselines")
    if proposal.status != "pending_maintainer_approval":
        raise QualityReportError(
            "threshold proposal status must be pending_maintainer_approval"
        )
    if proposal.enforced:
        raise QualityReportError("threshold proposal must not be enforced")

    default_baseline = load_quality_report(default_baseline_path)
    morphology_baseline = load_quality_report(morphology_baseline_path)
    default_result = load_quality_result(Path(proposal.default.performance_result_path))
    morphology_result = load_quality_result(
        Path(proposal.morphology.performance_result_path)
    )

    _validate_quality_binding(
        proposal.default,
        default_baseline,
        default_baseline_path,
        InstallationProfile.DEFAULT,
    )
    _validate_quality_binding(
        proposal.morphology,
        morphology_baseline,
        morphology_baseline_path,
        InstallationProfile.MORPHOLOGY,
    )
    _validate_performance_binding(
        proposal.default, default_result, Path(proposal.default.performance_result_path)
    )
    _validate_performance_binding(
        proposal.morphology,
        morphology_result,
        Path(proposal.morphology.performance_result_path),
    )

    if proposal.dataset_sha256 != default_baseline.dataset_sha256:
        raise QualityReportError("threshold proposal dataset_sha256 mismatch")
    if default_baseline.dataset_sha256 != morphology_baseline.dataset_sha256:
        raise QualityReportError("threshold proposal baselines dataset mismatch")
    if {
        default_baseline.artifact_sha256,
        morphology_baseline.artifact_sha256,
    } != {proposal.quality_artifact_sha256}:
        raise QualityReportError("threshold proposal quality artifact_sha256 mismatch")
    if {
        default_baseline.run_identity.source_sha,
        morphology_baseline.run_identity.source_sha,
    } != {proposal.quality_source_git_sha}:
        raise QualityReportError("threshold proposal quality source_git_sha mismatch")
    if {
        default_result.artifact_sha256,
        morphology_result.artifact_sha256,
    } != {proposal.performance_artifact_sha256}:
        raise QualityReportError(
            "threshold proposal performance artifact_sha256 mismatch"
        )
    if {
        default_result.run_identity.source_sha,
        morphology_result.run_identity.source_sha,
    } != {proposal.performance_source_git_sha}:
        raise QualityReportError(
            "threshold proposal performance source_git_sha mismatch"
        )
    for field in _ENVIRONMENT_FIELDS:
        if getattr(default_baseline.run_identity, field) != getattr(
            morphology_baseline.run_identity, field
        ):
            raise QualityReportError(
                "threshold proposal baselines environment mismatch"
            )
        if getattr(default_result.run_identity, field) != getattr(
            morphology_result.run_identity, field
        ):
            raise QualityReportError(
                "threshold proposal performance results environment mismatch"
            )


def _validate_quality_binding(
    proposal: ProfileThresholdProposalV3,
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


def _validate_performance_binding(
    proposal: ProfileThresholdProposalV3,
    result: QualityReport,
    result_path: Path,
) -> None:
    if proposal.performance_result_path != str(result_path):
        raise QualityReportError("threshold proposal performance_result_path mismatch")
    digest = hashlib.sha256(result_path.read_bytes()).hexdigest()
    if proposal.performance_result_sha256 != digest:
        raise QualityReportError(
            "threshold proposal performance_result_sha256 mismatch"
        )
    _validate_performance(proposal.performance, result)


def _validate_performance(
    comparison: PerformanceComparison, measured: QualityReport
) -> None:
    expected = (
        (
            "maximum_p95_latency_ns",
            comparison.maximum_p95_latency_ns,
            measured.latency.p95_ns,
        ),
        (
            "minimum_throughput_cases_per_second",
            comparison.minimum_throughput_cases_per_second,
            measured.throughput.cases_per_second,
        ),
        (
            "maximum_peak_rss_bytes",
            comparison.maximum_peak_rss_bytes,
            measured.resources.peak_rss_bytes,
        ),
        (
            "required_warmup_repetitions",
            comparison.required_warmup_repetitions,
            measured.warmup_repetitions,
        ),
        (
            "required_measured_repetitions",
            comparison.required_measured_repetitions,
            measured.measured_repetitions,
        ),
        ("allowed_regression_fraction", comparison.allowed_regression_fraction, 0.0),
        (
            "required_environment_match",
            comparison.required_environment_match,
            _ENVIRONMENT_FIELDS,
        ),
    )
    for name, proposed, value in expected:
        if proposed != value:
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
