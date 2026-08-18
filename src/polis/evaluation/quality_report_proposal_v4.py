"""Strict parser for the pending dual-profile v4 quality gate proposal."""

from __future__ import annotations

import re
from typing import Final

from polis.evaluation.quality_report_models import (
    JsonObject,
    PerformanceArtifactBinding,
    PerformanceComparison,
    ProfileThresholdProposalV4,
    ProposalGate,
    QualityFloors,
    QualityReportError,
    ThresholdProposalV4,
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
    "quality_floors",
    "category_floors",
    "stratum_floors",
    "performance_comparison",
    "performance_artifact",
    "performance_result_artifact",
    "gates",
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
    "maximum_worker_incremental_peak_rss_bytes",
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
_CATEGORIES = {"agreement", "inflection", "punctuation", "spelling", "syntax"}
_SHAPES = {
    "simple-local",
    "sentence-internal",
    "multi-sentence",
    "repeated-occurrence",
    "unicode-and-case",
    "quotation-or-literal",
    "conflict-or-abstention",
}


def parse_threshold_proposal_v4(root: JsonObject) -> ThresholdProposalV4:
    _exact(
        root,
        {
            "schema_id",
            "schema_version",
            "dataset_sha256",
            "manifest_sha256",
            "source_git_sha",
            "wheel_sha256",
            "wheel_filename",
            "source_snapshot",
            "profiles",
            "status",
            "enforced",
            "decision",
            "effective_schema_version",
        },
        "threshold proposal",
    )
    if (
        _string(root, "schema_id", "threshold proposal")
        != "polis.quality-threshold-proposal"
    ):
        raise QualityReportError("threshold proposal schema_id mismatch")
    if _integer(root, "schema_version", "threshold proposal") != 4:
        raise QualityReportError("threshold proposal schema_version must be 4")
    if _integer(root, "effective_schema_version", "threshold proposal") != 4:
        raise QualityReportError(
            "threshold proposal effective_schema_version must be 4"
        )
    source_sha = _string(root, "source_git_sha", "threshold proposal")
    if _SOURCE_SHA.fullmatch(source_sha) is None:
        raise QualityReportError(
            "threshold proposal source_git_sha must be a commit SHA"
        )
    raw_snapshot = root["source_snapshot"]
    if not isinstance(raw_snapshot, list) or len(raw_snapshot) != 59:
        raise QualityReportError(
            "threshold proposal source_snapshot must contain 59 entries"
        )
    snapshot: list[dict[str, str]] = []
    for item in raw_snapshot:
        if not isinstance(item, dict) or set(item) != {
            "source",
            "operation",
            "behavior_version",
        }:
            raise QualityReportError(
                "threshold proposal source_snapshot entry is malformed"
            )
        if not all(isinstance(value, str) for value in item.values()):
            raise QualityReportError(
                "threshold proposal source_snapshot values must be strings"
            )
        snapshot.append({key: str(item[key]) for key in item})
    if len({item["source"] for item in snapshot}) != 59:
        raise QualityReportError("threshold proposal source_snapshot has duplicates")
    profiles = _nested(root, "profiles", {"default", "morphology"})
    return ThresholdProposalV4(
        dataset_sha256=_sha(root, "dataset_sha256", "threshold proposal"),
        manifest_sha256=_sha(root, "manifest_sha256", "threshold proposal"),
        source_git_sha=source_sha,
        wheel_sha256=_sha(root, "wheel_sha256", "threshold proposal"),
        wheel_filename=_string(root, "wheel_filename", "threshold proposal"),
        source_snapshot=tuple(snapshot),
        effective_schema_version=_integer(
            root, "effective_schema_version", "threshold proposal"
        ),
        default=_parse_profile(_nested(profiles, "default", _PROFILE_FIELDS)),
        morphology=_parse_profile(_nested(profiles, "morphology", _PROFILE_FIELDS)),
        status=_string(root, "status", "threshold proposal"),
        enforced=_boolean(root, "enforced", "threshold proposal"),
        decision=_parse_decision(root["decision"]),
    )


def _parse_decision(raw: object) -> JsonObject | None:
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != {
        "status",
        "enforced",
        "approved_by",
        "approved_at",
        "rationale",
    }:
        raise QualityReportError("threshold proposal decision is malformed")
    if not isinstance(raw["status"], str) or not isinstance(raw["enforced"], bool):
        raise QualityReportError("threshold proposal decision values are malformed")
    if not all(
        isinstance(raw[key], str) and raw[key]
        for key in {"status", "approved_by", "approved_at", "rationale"}
    ):
        raise QualityReportError("threshold proposal decision values are malformed")
    return {key: raw[key] for key in raw}


def _parse_profile(root: JsonObject) -> ProfileThresholdProposalV4:
    return ProfileThresholdProposalV4(
        baseline_path=_string(root, "baseline_path", "profile proposal"),
        baseline_sha256=_sha(root, "baseline_sha256", "profile proposal"),
        quality=_parse_floors(_nested(root, "quality_floors", _QUALITY_FIELDS)),
        category_quality=_parse_floor_map(root["category_floors"], _CATEGORIES),
        stratum_quality=_parse_nested_floor_map(
            root["stratum_floors"], _CATEGORIES, _SHAPES
        ),
        performance=_parse_performance(
            _nested(root, "performance_comparison", _PERFORMANCE_FIELDS)
        ),
        performance_baseline=_parse_performance_artifact(
            _nested(
                root,
                "performance_artifact",
                {
                    "path",
                    "sha256",
                    "protocol_version",
                    "protocol_sha256",
                    "worker_sha256",
                },
            )
        ),
        performance_result=_parse_performance_artifact(
            _nested(
                root,
                "performance_result_artifact",
                {
                    "path",
                    "sha256",
                    "protocol_version",
                    "protocol_sha256",
                    "worker_sha256",
                },
            )
        ),
        gates=_parse_gates(root["gates"]),
    )


def _parse_floor_map(raw: object, names: set[str]) -> dict[str, QualityFloors]:
    if not isinstance(raw, dict) or set(raw) != names:
        raise QualityReportError("v4 category floors coverage mismatch")
    return {name: _parse_floors(_nested(raw, name, _QUALITY_FIELDS)) for name in names}


def _parse_nested_floor_map(
    raw: object, outer: set[str], inner: set[str]
) -> dict[str, dict[str, QualityFloors]]:
    if not isinstance(raw, dict) or set(raw) != outer:
        raise QualityReportError("v4 stratum floors category coverage mismatch")
    return {name: _parse_floor_map(raw[name], inner) for name in outer}


def _parse_performance_artifact(root: JsonObject) -> PerformanceArtifactBinding:
    protocol_version = _integer(root, "protocol_version", "performance_artifact")
    if protocol_version != 2:
        raise QualityReportError("v4 performance artifact protocol_version must be 2")
    return PerformanceArtifactBinding(
        path=_string(root, "path", "performance_artifact"),
        sha256=_sha(root, "sha256", "performance_artifact"),
        protocol_version=protocol_version,
        protocol_sha256=_sha(root, "protocol_sha256", "performance_artifact"),
        worker_sha256=_sha(root, "worker_sha256", "performance_artifact"),
    )


def _parse_gates(raw: object) -> tuple[ProposalGate, ...]:
    if not isinstance(raw, list) or not raw:
        raise QualityReportError("v4 proposal gates must be a non-empty list")
    gates: list[ProposalGate] = []
    fields = {
        "scope",
        "metric",
        "measured_baseline",
        "proposed_threshold",
        "rationale",
        "allowed_variation",
        "regression_risk",
        "maintainer_decision",
        "effective_schema_version",
    }
    for item in raw:
        if not isinstance(item, dict) or set(item) != fields:
            raise QualityReportError("v4 proposal gate is malformed")
        variation = item["allowed_variation"]
        if variation is not None and (
            not isinstance(variation, int | float)
            or isinstance(variation, bool)
            or not 0.0 <= float(variation) <= 1.0
        ):
            raise QualityReportError("v4 proposal gate allowed_variation is invalid")
        decision = item["maintainer_decision"]
        if decision is not None and not isinstance(decision, dict):
            raise QualityReportError("v4 proposal gate decision is malformed")
        gates.append(
            ProposalGate(
                scope=_string(item, "scope", "proposal gate"),
                metric=_string(item, "metric", "proposal gate"),
                measured_baseline=item["measured_baseline"],
                proposed_threshold=item["proposed_threshold"],
                rationale=_string(item, "rationale", "proposal gate"),
                allowed_variation=None if variation is None else float(variation),
                regression_risk=_string(item, "regression_risk", "proposal gate"),
                maintainer_decision=decision,
                effective_schema_version=_integer(
                    item, "effective_schema_version", "proposal gate"
                ),
            )
        )
    return tuple(gates)


def _parse_floors(root: JsonObject) -> QualityFloors:
    return QualityFloors(
        minimum_precision=_ratio(root, "minimum_precision"),
        minimum_recall=_ratio(root, "minimum_recall"),
        minimum_f1=_ratio(root, "minimum_f1"),
        minimum_exact_span_accuracy=_ratio(root, "minimum_exact_span_accuracy"),
        minimum_exact_correction_accuracy=_ratio(
            root, "minimum_exact_correction_accuracy"
        ),
        maximum_false_alarm_rate=_ratio(root, "maximum_false_alarm_rate"),
    )


def _parse_performance(root: JsonObject) -> PerformanceComparison:
    throughput = root["minimum_throughput_cases_per_second"]
    regression = root["allowed_regression_fraction"]
    if (
        not isinstance(throughput, int | float)
        or isinstance(throughput, bool)
        or throughput < 0
        or not isinstance(regression, int | float)
        or isinstance(regression, bool)
        or not 0.0 <= float(regression) <= 1.0
    ):
        raise QualityReportError("v4 performance numeric fields are invalid")
    return PerformanceComparison(
        maximum_p95_latency_ns=_integer(root, "maximum_p95_latency_ns", "performance"),
        minimum_throughput_cases_per_second=float(throughput),
        maximum_peak_rss_bytes=_integer(root, "maximum_peak_rss_bytes", "performance"),
        maximum_worker_incremental_peak_rss_bytes=_integer(
            root, "maximum_worker_incremental_peak_rss_bytes", "performance"
        ),
        required_warmup_repetitions=_integer(
            root, "required_warmup_repetitions", "performance"
        ),
        required_measured_repetitions=_integer(
            root, "required_measured_repetitions", "performance"
        ),
        require_identical_repetition_hashes=_boolean(
            root, "require_identical_repetition_hashes", "performance"
        ),
        required_environment_match=_string_tuple(root, "required_environment_match"),
        allowed_regression_fraction=float(regression),
        missing_metric=_string(root, "missing_metric", "performance"),
        nondeterminism=_string(root, "nondeterminism", "performance"),
        environment_mismatch=_string(root, "environment_mismatch", "performance"),
        performance_regression=_string(root, "performance_regression", "performance"),
    )
