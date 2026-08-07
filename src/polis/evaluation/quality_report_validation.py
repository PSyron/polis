"""Strict parsing primitives for versioned quality artifacts."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Final

from polis.evaluation import quality_protocol
from polis.evaluation.metrics import QualityCounts
from polis.evaluation.quality_report_models import (
    JsonObject,
    JsonValue,
    QualityReport,
    QualityReportError,
)

_SCHEMA_VERSION: Final = 1
_SHA256_PATTERN: Final = re.compile(r"[0-9a-f]{64}")
_MEASUREMENT_ERROR: Final = "quality report measurement evidence is inconsistent"


@dataclass(frozen=True, slots=True)
class _MeasurementEvidence:
    dataset_cases: int
    counts: QualityCounts
    measured_repetitions: int
    stable_repetitions: int
    repetition_hashes: tuple[str, ...]
    latency: quality_protocol.LatencyMetrics
    throughput: quality_protocol.ThroughputMetrics


def validate_quality_protocol_measurements(
    result: quality_protocol.QualityProtocolResult,
) -> None:
    _validate_measurement_evidence(
        _MeasurementEvidence(
            dataset_cases=result.baseline.dataset_cases,
            counts=result.baseline.aggregate,
            measured_repetitions=result.measured_repetitions,
            stable_repetitions=len(result.repetition_hashes),
            repetition_hashes=result.repetition_hashes,
            latency=result.latency,
            throughput=result.throughput,
        )
    )


def validate_quality_report_measurements(
    report: QualityReport, stable_repetitions: int
) -> None:
    _validate_measurement_evidence(
        _MeasurementEvidence(
            dataset_cases=report.dataset_cases,
            counts=report.counts,
            measured_repetitions=report.measured_repetitions,
            stable_repetitions=stable_repetitions,
            repetition_hashes=report.repetition_hashes,
            latency=report.latency,
            throughput=report.throughput,
        )
    )


def _validate_measurement_evidence(evidence: _MeasurementEvidence) -> None:
    expected_cases = evidence.dataset_cases * evidence.measured_repetitions
    counts = evidence.counts
    if (
        counts.correct_cases < 0
        or counts.alarmed_correct_cases < 0
        or counts.alarmed_correct_cases > counts.correct_cases
        or counts.correct_cases > evidence.dataset_cases
    ):
        raise QualityReportError("quality report counts are inconsistent")
    latency = evidence.latency
    throughput = evidence.throughput
    expected_rates: tuple[float, float] | None
    actual_rates: tuple[float, float] | None
    try:
        expected_rates = (
            expected_cases * 1_000_000_000 / throughput.total_duration_ns,
            throughput.measured_code_points
            * 1_000_000_000
            / throughput.total_duration_ns,
        )
        actual_rates = throughput.cases_per_second, throughput.code_points_per_second
        rates_are_valid = all(math.isfinite(rate) for rate in actual_rates)
    except (OverflowError, ZeroDivisionError):
        rates_are_valid = False
        expected_rates = None
        actual_rates = None
    if (
        evidence.dataset_cases <= 0
        or evidence.measured_repetitions < 2
        or evidence.stable_repetitions != evidence.measured_repetitions
        or len(evidence.repetition_hashes) != evidence.measured_repetitions
        or len(set(evidence.repetition_hashes)) != 1
        or latency.sample_count != expected_cases
        or not latency.min_ns <= latency.p50_ns <= latency.p95_ns <= latency.max_ns
        or not latency.min_ns <= latency.mean_ns <= latency.max_ns
        or latency.mean_ns != throughput.total_duration_ns // latency.sample_count
        or throughput.measured_cases != expected_cases
        or throughput.measured_code_points <= 0
        or throughput.measured_code_points < throughput.measured_cases
        or throughput.measured_code_points % evidence.measured_repetitions != 0
        or throughput.total_duration_ns <= 0
        or not rates_are_valid
        or actual_rates != expected_rates
    ):
        raise QualityReportError(_MEASUREMENT_ERROR)


def _load_json_object(path: Path, label: str) -> JsonObject:
    try:
        raw: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise QualityReportError(f"cannot read {label}") from error
    return _require_object(raw, label)


def _require_object(value: JsonValue, label: str) -> JsonObject:
    if not isinstance(value, dict):
        raise QualityReportError(f"{label} must be an object")
    return value


def _exact(value: JsonObject, expected: set[str], label: str) -> None:
    actual = set(value)
    unexpected = sorted(actual - expected)
    missing = sorted(expected - actual)
    if unexpected:
        raise QualityReportError(f"{label} has unexpected fields: {unexpected}")
    if missing:
        raise QualityReportError(f"{label} is missing fields: {missing}")


def _nested(parent: JsonObject, key: str, fields: set[str]) -> JsonObject:
    nested = _require_object(parent[key], key)
    _exact(nested, fields, key)
    return nested


def _schema(root: JsonObject, schema_id: str, label: str) -> None:
    if _string(root, "schema_id", label) != schema_id:
        raise QualityReportError(f"{label} schema_id mismatch")
    if _integer(root, "schema_version", label) != _SCHEMA_VERSION:
        raise QualityReportError(f"{label} schema_version must be 1")


def _string(parent: JsonObject, key: str, label: str) -> str:
    value = parent[key]
    if not isinstance(value, str) or not value:
        raise QualityReportError(f"{label} {key} must be a non-empty string")
    return value


def _integer(parent: JsonObject, key: str, label: str) -> int:
    value = parent[key]
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise QualityReportError(f"{label} {key} must be a non-negative integer")
    return value


def _boolean(parent: JsonObject, key: str, label: str) -> bool:
    value = parent[key]
    if not isinstance(value, bool):
        raise QualityReportError(f"{label} {key} must be a boolean")
    return value


def _ratio(parent: JsonObject, key: str) -> float | None:
    value = parent[key]
    if value is None:
        return None
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise QualityReportError(f"{key} must be a number or null")
    try:
        ratio = float(value)
    except OverflowError:
        raise QualityReportError(f"{key} must be within the unit interval") from None
    if not 0.0 <= ratio <= 1.0:
        raise QualityReportError(f"{key} must be within the unit interval")
    return ratio


def _quality_ratio(
    parent: JsonObject,
    key: str,
    expected: float | None,
) -> float | None:
    ratio = _ratio(parent, key)
    if ratio != expected:
        raise QualityReportError(f"quality report {key} mismatch")
    return ratio


def _sha(parent: JsonObject, key: str, label: str) -> str:
    return _validated_sha(_string(parent, key, label), f"{label} {key}")


def _validated_sha(value: str, label: str) -> str:
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise QualityReportError(f"{label} must be a lowercase SHA-256")
    return value


def _string_tuple(parent: JsonObject, key: str) -> tuple[str, ...]:
    value = parent[key]
    if not isinstance(value, list) or not value:
        raise QualityReportError(f"{key} must be a non-empty list")
    if not all(isinstance(item, str) for item in value):
        raise QualityReportError(f"{key} must contain strings")
    return tuple(item for item in value if isinstance(item, str))


def _parse_counts(quality: JsonObject) -> QualityCounts:
    names = {field.name for field in fields(QualityCounts)}
    counts = _nested(quality, "counts", names)
    parsed = QualityCounts(
        expected_findings=_integer(counts, "expected_findings", "counts"),
        predicted_findings=_integer(counts, "predicted_findings", "counts"),
        true_positives=_integer(counts, "true_positives", "counts"),
        false_positives=_integer(counts, "false_positives", "counts"),
        false_negatives=_integer(counts, "false_negatives", "counts"),
        span_matches=_integer(counts, "span_matches", "counts"),
        correction_matches=_integer(counts, "correction_matches", "counts"),
        correct_cases=_integer(counts, "correct_cases", "counts"),
        alarmed_correct_cases=_integer(counts, "alarmed_correct_cases", "counts"),
    )
    if (
        parsed.expected_findings != parsed.true_positives + parsed.false_negatives
        or parsed.predicted_findings != parsed.true_positives + parsed.false_positives
        or parsed.correction_matches != parsed.true_positives
        or parsed.correction_matches > parsed.span_matches
        or parsed.span_matches
        > min(parsed.expected_findings, parsed.predicted_findings)
        or parsed.alarmed_correct_cases > parsed.correct_cases
    ):
        raise QualityReportError("quality report counts are inconsistent")
    return parsed


def _parse_latency(performance: JsonObject) -> quality_protocol.LatencyMetrics:
    latency = _nested(
        performance, "latency_ns", {"sample_count", "min", "mean", "p50", "p95", "max"}
    )
    return quality_protocol.LatencyMetrics(
        sample_count=_integer(latency, "sample_count", "latency_ns"),
        min_ns=_integer(latency, "min", "latency_ns"),
        mean_ns=_integer(latency, "mean", "latency_ns"),
        p50_ns=_integer(latency, "p50", "latency_ns"),
        p95_ns=_integer(latency, "p95", "latency_ns"),
        max_ns=_integer(latency, "max", "latency_ns"),
    )


def _parse_throughput(performance: JsonObject) -> quality_protocol.ThroughputMetrics:
    throughput = _nested(
        performance,
        "throughput",
        {
            "measured_cases",
            "measured_code_points",
            "total_duration_ns",
            "cases_per_second",
            "code_points_per_second",
        },
    )
    return quality_protocol.ThroughputMetrics(
        measured_cases=_integer(throughput, "measured_cases", "throughput"),
        measured_code_points=_integer(throughput, "measured_code_points", "throughput"),
        total_duration_ns=_integer(throughput, "total_duration_ns", "throughput"),
        cases_per_second=_number(throughput, "cases_per_second", "throughput"),
        code_points_per_second=_number(
            throughput, "code_points_per_second", "throughput"
        ),
    )


def _number(parent: JsonObject, key: str, label: str) -> float:
    value = parent[key]
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise QualityReportError(_MEASUREMENT_ERROR)
    try:
        number = float(value)
    except OverflowError:
        raise QualityReportError(_MEASUREMENT_ERROR) from None
    if not math.isfinite(number) or number < 0:
        raise QualityReportError(_MEASUREMENT_ERROR)
    return number
