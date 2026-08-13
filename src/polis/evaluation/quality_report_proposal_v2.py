"""Dual-profile parsing and baseline binding for v2 threshold proposals."""

from __future__ import annotations

import re
from typing import Final

from polis.evaluation.quality_report_models import (
    JsonObject,
    PerformanceComparison,
    ProfileThresholdProposal,
    QualityFloors,
    QualityReportError,
    ThresholdProposalV2,
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


def parse_threshold_proposal_v2(root: JsonObject) -> ThresholdProposalV2:
    """Parse the strict v2 proposal shape into immutable values."""

    _exact(
        root,
        {
            "schema_id",
            "schema_version",
            "dataset_sha256",
            "measurement_identity",
            "profiles",
            "status",
            "enforced",
        },
        "threshold proposal",
    )
    identity = _nested(
        root, "measurement_identity", {"artifact_sha256", "source_git_sha"}
    )
    source_git_sha = _string(identity, "source_git_sha", "measurement_identity")
    if _SOURCE_SHA.fullmatch(source_git_sha) is None:
        raise QualityReportError(
            "threshold proposal source_git_sha must be a commit SHA"
        )
    profiles = _nested(root, "profiles", {"default", "morphology"})
    return ThresholdProposalV2(
        dataset_sha256=_sha(root, "dataset_sha256", "threshold proposal"),
        artifact_sha256=_sha(identity, "artifact_sha256", "measurement_identity"),
        source_git_sha=source_git_sha,
        default=_parse_profile(_nested(profiles, "default", _PROFILE_FIELDS)),
        morphology=_parse_profile(_nested(profiles, "morphology", _PROFILE_FIELDS)),
        status=_string(root, "status", "threshold proposal"),
        enforced=_boolean(root, "enforced", "threshold proposal"),
    )


_PROFILE_FIELDS: Final = {
    "baseline_path",
    "baseline_sha256",
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


def _parse_profile(value: JsonObject) -> ProfileThresholdProposal:
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
    return ProfileThresholdProposal(
        baseline_path=_string(value, "baseline_path", "profile proposal"),
        baseline_sha256=_sha(value, "baseline_sha256", "profile proposal"),
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
