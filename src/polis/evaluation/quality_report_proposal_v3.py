"""Dual-profile parsing for v3 threshold proposals (quality + wave0 performance)."""

from __future__ import annotations

import re
from typing import Final

from polis.evaluation.quality_report_models import (
    JsonObject,
    PerformanceComparison,
    ProfileThresholdProposalV3,
    QualityFloors,
    QualityReportError,
    ThresholdProposalV3,
)
from polis.evaluation.quality_report_validation import (
    _boolean,
    _exact,
    _integer,
    _nested,
    _ratio,
    _sha,
    _string,
    _string_tuple,
)

_SOURCE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_PROFILE_FIELDS: Final = {
    "baseline_path",
    "baseline_sha256",
    "performance_result_path",
    "performance_result_sha256",
    "planned_morphology_source_semantics",
    "planned_non_morphology_source_semantics",
    "quality_floors",
    "performance_comparison",
}
_QUALITY_FIELDS: Final = {
    "minimum_precision",
    "minimum_recall",
    "minimum_f1",
    "minimum_exact_span_accuracy",
    "minimum_exact_correction_accuracy",
    "maximum_false_alarm_rate",
}
_PERFORMANCE_FIELDS: Final = {
    "maximum_p95_latency_ns",
    "minimum_throughput_cases_per_second",
    "maximum_peak_rss_bytes",
    "required_warmup_repetitions",
    "required_measured_repetitions",
    "require_identical_repetition_hashes",
    "required_environment_match",
    "allowed_regression_fraction",
    "missing_metric",
    "nondeterminism",
    "environment_mismatch",
    "performance_regression",
}


def parse_threshold_proposal_v3(root: JsonObject) -> ThresholdProposalV3:
    """Parse the strict v3 proposal shape into immutable values."""

    _exact(
        root,
        {
            "schema_id",
            "schema_version",
            "dataset_sha256",
            "quality_measurement_identity",
            "performance_measurement_identity",
            "profiles",
            "status",
            "enforced",
        },
        "threshold proposal",
    )
    quality_identity = _nested(
        root,
        "quality_measurement_identity",
        {"artifact_sha256", "source_git_sha"},
    )
    performance_identity = _nested(
        root,
        "performance_measurement_identity",
        {"artifact_sha256", "source_git_sha"},
    )
    quality_source = _string(
        quality_identity, "source_git_sha", "quality_measurement_identity"
    )
    performance_source = _string(
        performance_identity, "source_git_sha", "performance_measurement_identity"
    )
    if _SOURCE_SHA.fullmatch(quality_source) is None:
        raise QualityReportError(
            "threshold proposal quality source_git_sha must be a commit SHA"
        )
    if _SOURCE_SHA.fullmatch(performance_source) is None:
        raise QualityReportError(
            "threshold proposal performance source_git_sha must be a commit SHA"
        )
    profiles = _nested(root, "profiles", {"default", "morphology"})
    return ThresholdProposalV3(
        dataset_sha256=_sha(root, "dataset_sha256", "threshold proposal"),
        quality_artifact_sha256=_sha(
            quality_identity, "artifact_sha256", "quality_measurement_identity"
        ),
        quality_source_git_sha=quality_source,
        performance_artifact_sha256=_sha(
            performance_identity,
            "artifact_sha256",
            "performance_measurement_identity",
        ),
        performance_source_git_sha=performance_source,
        default=_parse_profile(_nested(profiles, "default", _PROFILE_FIELDS)),
        morphology=_parse_profile(_nested(profiles, "morphology", _PROFILE_FIELDS)),
        status=_string(root, "status", "threshold proposal"),
        enforced=_boolean(root, "enforced", "threshold proposal"),
    )


def _parse_profile(value: JsonObject) -> ProfileThresholdProposalV3:
    quality = _nested(value, "quality_floors", _QUALITY_FIELDS)
    performance = _nested(value, "performance_comparison", _PERFORMANCE_FIELDS)
    throughput = performance["minimum_throughput_cases_per_second"]
    if (
        not isinstance(throughput, int | float)
        or isinstance(throughput, bool)
        or throughput <= 0
    ):
        raise QualityReportError(
            "minimum_throughput_cases_per_second must be a positive number"
        )
    allowed_regression_fraction = _ratio(performance, "allowed_regression_fraction")
    if allowed_regression_fraction is None:
        raise QualityReportError(
            "allowed_regression_fraction must be within the unit interval"
        )
    return ProfileThresholdProposalV3(
        baseline_path=_string(value, "baseline_path", "profile proposal"),
        baseline_sha256=_sha(value, "baseline_sha256", "profile proposal"),
        performance_result_path=_string(
            value, "performance_result_path", "profile proposal"
        ),
        performance_result_sha256=_sha(
            value, "performance_result_sha256", "profile proposal"
        ),
        planned_morphology_source_semantics=_string(
            value, "planned_morphology_source_semantics", "profile proposal"
        ),
        planned_non_morphology_source_semantics=_string(
            value, "planned_non_morphology_source_semantics", "profile proposal"
        ),
        quality=QualityFloors(
            minimum_precision=_ratio(quality, "minimum_precision"),
            minimum_recall=_ratio(quality, "minimum_recall"),
            minimum_f1=_ratio(quality, "minimum_f1"),
            minimum_exact_span_accuracy=_ratio(quality, "minimum_exact_span_accuracy"),
            minimum_exact_correction_accuracy=_ratio(
                quality, "minimum_exact_correction_accuracy"
            ),
            maximum_false_alarm_rate=_ratio(quality, "maximum_false_alarm_rate"),
        ),
        performance=PerformanceComparison(
            maximum_p95_latency_ns=_integer(
                performance, "maximum_p95_latency_ns", "performance_comparison"
            ),
            minimum_throughput_cases_per_second=float(throughput),
            maximum_peak_rss_bytes=_integer(
                performance, "maximum_peak_rss_bytes", "performance_comparison"
            ),
            required_warmup_repetitions=_integer(
                performance,
                "required_warmup_repetitions",
                "performance_comparison",
            ),
            required_measured_repetitions=_integer(
                performance,
                "required_measured_repetitions",
                "performance_comparison",
            ),
            require_identical_repetition_hashes=_boolean(
                performance,
                "require_identical_repetition_hashes",
                "performance_comparison",
            ),
            required_environment_match=_string_tuple(
                performance, "required_environment_match"
            ),
            allowed_regression_fraction=allowed_regression_fraction,
            missing_metric=_string(
                performance, "missing_metric", "performance_comparison"
            ),
            nondeterminism=_string(
                performance, "nondeterminism", "performance_comparison"
            ),
            environment_mismatch=_string(
                performance, "environment_mismatch", "performance_comparison"
            ),
            performance_regression=_string(
                performance, "performance_regression", "performance_comparison"
            ),
        ),
    )
