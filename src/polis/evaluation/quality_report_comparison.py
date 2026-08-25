"""Repository-only parser for dual-profile quality comparison artifacts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from polis.evaluation.quality_report_models import JsonObject, QualityReportError
from polis.evaluation.quality_report_validation import (
    _boolean,
    _exact,
    _integer,
    _load_json_object,
    _nested,
    _sha,
    _string,
)

_SCHEMA_ID: Final = "polis.regression-comparison"
_LEGACY_SCHEMA_ID: Final = "polis.quality-comparison"
_SCHEMA_VERSION: Final = 1
_SOURCE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_SNAPSHOT_SHA: Final = re.compile(r"[0-9a-f]{64}")
_PROFILE_IDS: Final = ("default", "morphology")


@dataclass(frozen=True, slots=True)
class MetricDelta:
    metric: str
    baseline: float | int
    result: float | int
    delta: float | int
    higher_is_better: bool


@dataclass(frozen=True, slots=True)
class ComparisonGate:
    gate: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ProfileComparison:
    profile_id: str
    baseline_path: str
    baseline_sha256: str
    result_path: str
    result_sha256: str
    metric_deltas: tuple[MetricDelta, ...]
    gates: tuple[ComparisonGate, ...]
    verdict: str
    category_gates: tuple[ComparisonGate, ...] = ()
    stratum_gates: tuple[ComparisonGate, ...] = ()
    source_parity: JsonObject | None = None
    performance: JsonObject | None = None


@dataclass(frozen=True, slots=True)
class QualityComparison:
    proposal_path: str
    proposal_sha256: str
    dataset_sha256: str
    source_git_sha: str
    wheel_sha256: str
    sdist_sha256: str | None
    profiles: dict[str, ProfileComparison]
    aggregate_verdict: str
    v4: bool = False


def load_quality_comparison(path: Path) -> QualityComparison:
    """Parse and reject every unknown or malformed comparison field."""

    root = _load_json_object(path, "quality comparison")
    schema_version = _integer(root, "schema_version", "quality comparison")
    expected_fields = {
        "schema_id",
        "schema_version",
        "proposal_path",
        "proposal_sha256",
        "dataset_sha256",
        "source_git_sha",
        "artifacts",
        "environment_result",
        "environment_baseline",
        "profiles",
        "aggregate_verdict",
        "notes",
    }
    if schema_version == 4:
        expected_fields.update({"manifest_sha256"})
    _exact(root, expected_fields, "quality comparison")
    if _string(root, "schema_id", "quality comparison") not in {
        _SCHEMA_ID,
        _LEGACY_SCHEMA_ID,
    }:
        raise QualityReportError("quality comparison schema_id mismatch")
    if schema_version not in {_SCHEMA_VERSION, 4}:
        raise QualityReportError("quality comparison schema_version must be 1 or 4")
    source_git_sha = _string(root, "source_git_sha", "quality comparison")
    if _SOURCE_SHA.fullmatch(source_git_sha) is None:
        raise QualityReportError(
            "quality comparison source_git_sha must be a commit SHA"
        )
    artifacts = _nested(
        root,
        "artifacts",
        {"wheel_sha256", "sdist_sha256", "wheel_filename", "sdist_filename"},
    )
    if schema_version == 4 and (
        artifacts["sdist_sha256"] is not None or artifacts["sdist_filename"] is not None
    ):
        raise QualityReportError("v4 comparison must not claim an unmeasured sdist")
    profiles_root = _nested(root, "profiles", set(_PROFILE_IDS))
    profile_fields = _PROFILE_FIELDS_V4 if schema_version == 4 else _PROFILE_FIELDS
    profiles = {
        profile_id: _parse_profile(
            profile_id,
            _nested(profiles_root, profile_id, profile_fields),
            v4=schema_version == 4,
        )
        for profile_id in _PROFILE_IDS
    }
    if schema_version == 4:
        for profile in profiles.values():
            _validate_v4_profile_details(profile)
    aggregate = _string(root, "aggregate_verdict", "quality comparison")
    if aggregate not in {"pass", "fail"}:
        raise QualityReportError(
            "quality comparison aggregate_verdict must be pass|fail"
        )
    expected_aggregate = (
        "pass"
        if all(profile.verdict == "pass" for profile in profiles.values())
        else "fail"
    )
    if aggregate != expected_aggregate:
        raise QualityReportError("quality comparison aggregate_verdict is inconsistent")
    notes = root["notes"]
    if not isinstance(notes, list) or not all(isinstance(item, str) for item in notes):
        raise QualityReportError("quality comparison notes must be a string list")
    _nested(root, "environment_result", set(_PROFILE_IDS))
    _nested(root, "environment_baseline", set(_PROFILE_IDS))
    if schema_version == 4:
        manifest_sha = _sha(root, "manifest_sha256", "quality comparison")
        if manifest_sha == "0" * 64:
            raise QualityReportError(
                "quality v4 manifest hash must not be a placeholder"
            )
        for profile in profiles.values():
            if profile.source_parity is None:
                raise QualityReportError("quality v4 source parity details are missing")
        if not manifest_sha:
            raise QualityReportError("quality v4 manifest identity is missing")
    return QualityComparison(
        proposal_path=_string(root, "proposal_path", "quality comparison"),
        proposal_sha256=_sha(root, "proposal_sha256", "quality comparison"),
        dataset_sha256=_sha(root, "dataset_sha256", "quality comparison"),
        source_git_sha=source_git_sha,
        wheel_sha256=_sha(artifacts, "wheel_sha256", "artifacts"),
        sdist_sha256=(
            None
            if artifacts["sdist_sha256"] is None
            else _sha(artifacts, "sdist_sha256", "artifacts")
        ),
        profiles=profiles,
        aggregate_verdict=aggregate,
        v4=schema_version == 4,
    )


_PROFILE_FIELDS: Final = {
    "profile_id",
    "baseline_path",
    "baseline_sha256",
    "result_path",
    "result_sha256",
    "quality_counts_baseline",
    "quality_counts_result",
    "metric_deltas",
    "gates",
    "verdict",
}
_PROFILE_FIELDS_V4: Final = _PROFILE_FIELDS | {
    "category_gates",
    "stratum_gates",
    "source_parity",
    "performance",
}


def _validate_v4_profile_details(profile: ProfileComparison) -> None:
    if profile.profile_id not in _PROFILE_IDS:
        raise QualityReportError("quality v4 comparison profile is unknown")
    # v4 writers include the complete category, shape, and source diagnostics.
    # The parser intentionally checks their presence before accepting a verdict.
    # They are retained as the profile's gate list in the common typed facade.
    gates = {
        gate.gate
        for gate in (*profile.gates, *profile.category_gates, *profile.stratum_gates)
    }
    if (
        not any(gate.startswith("category:") for gate in gates)
        or not any(gate.startswith("stratum:") for gate in gates)
        or not any(gate.startswith("performance.") for gate in gates)
    ):
        raise QualityReportError(
            "quality v4 comparison category/stratum gates are missing"
        )


def _parse_profile(
    profile_id: str, value: JsonObject, *, v4: bool = False
) -> ProfileComparison:
    if _string(value, "profile_id", "profile comparison") != profile_id:
        raise QualityReportError("quality comparison profile_id mismatch")
    verdict = _string(value, "verdict", "profile comparison")
    if verdict not in {"pass", "fail"}:
        raise QualityReportError("quality comparison profile verdict must be pass|fail")
    deltas_raw = value["metric_deltas"]
    gates_raw = value["gates"]
    if not isinstance(deltas_raw, list) or not deltas_raw:
        raise QualityReportError(
            "quality comparison metric_deltas must be a non-empty list"
        )
    if not isinstance(gates_raw, list) or not gates_raw:
        raise QualityReportError("quality comparison gates must be a non-empty list")
    deltas = tuple(_parse_delta(item) for item in deltas_raw)
    gates = tuple(_parse_gate(item) for item in gates_raw)
    category_gates = tuple(
        _parse_gate(item) for item in value.get("category_gates", [])
    )
    stratum_gates = tuple(_parse_gate(item) for item in value.get("stratum_gates", []))
    if v4 and (not category_gates or not stratum_gates):
        raise QualityReportError(
            "quality v4 comparison category/stratum gates are missing"
        )
    if v4 and not any(gate.gate == "source:exact-ordered-59-parity" for gate in gates):
        raise QualityReportError("quality v4 source parity gate is missing")
    if v4:
        performance = value.get("performance")
        if not isinstance(performance, dict) or set(performance) != {
            "baseline",
            "result",
        }:
            raise QualityReportError("quality v4 performance details are missing")
        source_parity = value.get("source_parity")
        if not isinstance(source_parity, dict):
            raise QualityReportError("quality v4 source parity details are missing")
        snapshot_sha = source_parity.get("snapshot_sha256")
        if (
            not isinstance(snapshot_sha, str)
            or _SNAPSHOT_SHA.fullmatch(snapshot_sha) is None
        ):
            raise QualityReportError("quality v4 source snapshot digest is invalid")
        if source_parity.get("row_count") != 59:
            raise QualityReportError("quality v4 source parity row count is invalid")
    expected_verdict = (
        "pass"
        if all(gate.passed for gate in (*gates, *category_gates, *stratum_gates))
        and (not v4 or isinstance(value.get("source_parity"), dict))
        else "fail"
    )
    if verdict != expected_verdict:
        raise QualityReportError("quality comparison profile verdict is inconsistent")
    _nested(
        value,
        "quality_counts_baseline",
        {
            "alarmed_correct_cases",
            "correct_cases",
            "correction_matches",
            "expected_findings",
            "false_negatives",
            "false_positives",
            "predicted_findings",
            "span_matches",
            "true_positives",
        },
    )
    _nested(
        value,
        "quality_counts_result",
        {
            "alarmed_correct_cases",
            "correct_cases",
            "correction_matches",
            "expected_findings",
            "false_negatives",
            "false_positives",
            "predicted_findings",
            "span_matches",
            "true_positives",
        },
    )
    return ProfileComparison(
        profile_id=profile_id,
        baseline_path=_string(value, "baseline_path", "profile comparison"),
        baseline_sha256=_sha(value, "baseline_sha256", "profile comparison"),
        result_path=_string(value, "result_path", "profile comparison"),
        result_sha256=_sha(value, "result_sha256", "profile comparison"),
        metric_deltas=deltas,
        gates=gates,
        verdict=verdict,
        category_gates=category_gates,
        stratum_gates=stratum_gates,
        source_parity=(
            value.get("source_parity")
            if isinstance(value.get("source_parity"), dict)
            else None
        ),
        performance=(
            value.get("performance")
            if isinstance(value.get("performance"), dict)
            else None
        ),
    )


def _parse_delta(value: object) -> MetricDelta:
    if not isinstance(value, dict):
        raise QualityReportError("quality comparison metric delta must be an object")
    _exact(
        value,
        {"metric", "baseline", "result", "delta", "higher_is_better"},
        "metric delta",
    )
    baseline = value["baseline"]
    result = value["result"]
    delta = value["delta"]
    if not isinstance(baseline, int | float) or isinstance(baseline, bool):
        raise QualityReportError("metric delta baseline must be numeric")
    if not isinstance(result, int | float) or isinstance(result, bool):
        raise QualityReportError("metric delta result must be numeric")
    if not isinstance(delta, int | float) or isinstance(delta, bool):
        raise QualityReportError("metric delta delta must be numeric")
    if abs((result - baseline) - delta) > 1e-12:
        raise QualityReportError("metric delta is inconsistent")
    return MetricDelta(
        metric=_string(value, "metric", "metric delta"),
        baseline=baseline,
        result=result,
        delta=delta,
        higher_is_better=_boolean(value, "higher_is_better", "metric delta"),
    )


def _parse_gate(value: object) -> ComparisonGate:
    if not isinstance(value, dict):
        raise QualityReportError("quality comparison gate must be an object")
    _exact(value, {"gate", "pass", "detail"}, "comparison gate")
    return ComparisonGate(
        gate=_string(value, "gate", "comparison gate"),
        passed=_boolean(value, "pass", "comparison gate"),
        detail=_string(value, "detail", "comparison gate"),
    )


__all__ = [
    "ComparisonGate",
    "MetricDelta",
    "ProfileComparison",
    "QualityComparison",
    "load_quality_comparison",
]
