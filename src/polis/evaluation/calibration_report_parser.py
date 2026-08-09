from __future__ import annotations

import json
import math
import re
from typing import Final, NoReturn

from polis.evaluation.calibration_denominators import denominator_for
from polis.evaluation.calibration_models import (
    CalibrationContractError,
    CalibrationCounts,
    CalibrationMetrics,
    CalibrationReport,
    CalibrationRunAggregates,
    CalibrationSourceIdentity,
    JsonObject,
    JsonValue,
    KeyOutcome,
)
from polis.evaluation.calibration_sources import SOURCE_ROWS, SOURCE_SNAPSHOT_SHA256

RAW_FIELDS: Final = {
    "schema_id",
    "schema_version",
    "experiment_id",
    "dataset_id",
    "source_snapshot_sha256",
    "repetition_hashes",
    "outcomes",
    "aggregates",
}
OUTCOME_FIELDS: Final = {
    "identity",
    "counts",
    "metrics",
    "observed_confidence",
    "minimum_confidence",
    "verdict",
}
IDENTITY_NAMES: Final = (
    "source",
    "category",
    "operation",
    "behavior_version",
    "source_policy_version",
    "emitted_confidence",
    "current_policy_state",
)
COUNT_NAMES: Final = (
    "error_cases",
    "correct_cases",
    "true_positive",
    "false_positive",
    "false_negative",
    "exact_span_matches",
    "exact_correction_matches",
    "correct_sentence_false_alarms",
)
METRIC_NAMES: Final = (
    "precision",
    "recall",
    "f1",
    "exact_span_accuracy",
    "exact_correction_accuracy",
    "correct_sentence_false_alarm_rate",
)
_AGGREGATE_FIELDS: Final = {"elapsed_seconds", "peak_memory_bytes"}


def _fail(message: str) -> NoReturn:
    raise CalibrationContractError(message)


def canonical_report_bytes(value: JsonValue) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode()
    except ValueError as error:
        raise CalibrationContractError("report contains non-finite data") from error


def _object(value: JsonValue, fields: set[str], label: str) -> JsonObject:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"{label} must contain exactly the required fields")
    return value


def _integer(value: JsonValue, label: str) -> int:
    if type(value) is not int or value < 0:
        _fail(f"{label} must be a non-negative integer")
    return value


def _number(value: JsonValue, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        _fail(f"{label} must be finite and non-negative")
    return float(value)


def _optional_number(value: JsonValue, label: str) -> float | None:
    if value is None:
        return None
    number = _number(value, label)
    if not 0.0 <= number <= 1.0:
        _fail(f"{label} must be between zero and one")
    return number


def _identity(value: JsonValue, expected: CalibrationSourceIdentity) -> None:
    raw = _object(value, set(IDENTITY_NAMES), "report identity")
    if tuple(raw[name] for name in IDENTITY_NAMES) != expected.as_tuple():
        _fail("report identity does not match the frozen source row")


def _candidate_metrics_pass(metrics: CalibrationMetrics) -> bool:
    return (
        metrics.precision is not None
        and metrics.precision >= 1.0
        and metrics.recall is not None
        and metrics.recall >= 0.7142857142857143
        and metrics.f1 is not None
        and metrics.f1 >= 0.8333333333333334
        and metrics.exact_span_accuracy is not None
        and metrics.exact_span_accuracy >= 0.7142857142857143
        and metrics.exact_correction_accuracy is not None
        and metrics.exact_correction_accuracy >= 1.0
        and metrics.correct_sentence_false_alarm_rate is not None
        and metrics.correct_sentence_false_alarm_rate <= 0.0
    )


def _outcome(value: JsonValue, expected: CalibrationSourceIdentity) -> KeyOutcome:
    raw = _object(value, OUTCOME_FIELDS, "report outcome")
    _identity(raw["identity"], expected)
    counts_raw = _object(raw["counts"], set(COUNT_NAMES), "report counts")
    counts = CalibrationCounts(
        *(_integer(counts_raw[name], name) for name in COUNT_NAMES)
    )
    policy = denominator_for(expected.source)
    if (counts.error_cases, counts.correct_cases) != (
        policy.calibration_error_cases,
        policy.calibration_correct_cases,
    ):
        _fail("report denominators do not match the approved per-source contract")
    metrics_raw = _object(raw["metrics"], set(METRIC_NAMES), "report metrics")
    metrics = CalibrationMetrics(
        *(_optional_number(metrics_raw[name], name) for name in METRIC_NAMES)
    )
    observed = _optional_number(raw["observed_confidence"], "observed confidence")
    minimum = _optional_number(raw["minimum_confidence"], "minimum confidence")
    match raw["verdict"]:
        case "candidate":
            if (
                policy.preregistered_verdict is not None
                or observed != expected.emitted_confidence
                or minimum != expected.emitted_confidence
                or not _candidate_metrics_pass(metrics)
            ):
                _fail("candidate row does not satisfy the frozen baseline")
            return KeyOutcome(expected, counts, metrics, observed, minimum, "candidate")
        case "fail_threshold":
            if policy.preregistered_verdict is not None or minimum is not None:
                _fail("non-candidate row must not carry minimum confidence")
            return KeyOutcome(
                expected, counts, metrics, observed, minimum, "fail_threshold"
            )
        case "insufficient_evidence":
            if minimum is not None:
                _fail("non-candidate row must not carry minimum confidence")
            return KeyOutcome(
                expected, counts, metrics, observed, minimum, "insufficient_evidence"
            )
        case _:
            _fail("report verdict is invalid")


def parse_raw_report(raw_bytes: bytes) -> CalibrationReport:
    def reject_constant(value: str) -> NoReturn:
        _fail(f"report contains non-finite constant {value}")

    try:
        value = json.loads(raw_bytes, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationContractError("report is invalid JSON") from error
    if not isinstance(value, dict) or raw_bytes != canonical_report_bytes(value):
        _fail("report must be a canonical JSON object")
    fields = set(value)
    normalized_fields = RAW_FIELDS - {"aggregates"}
    if fields not in (RAW_FIELDS, normalized_fields):
        _fail("report must contain exactly the required top-level fields")
    expected_schema = (
        "polis.a-b-calibration.raw-report"
        if fields == RAW_FIELDS
        else "polis.a-b-calibration.normalized-report"
    )
    schema_version = _integer(value["schema_version"], "report schema version")
    if (
        value["schema_id"],
        schema_version,
        value["experiment_id"],
        value["dataset_id"],
        value["source_snapshot_sha256"],
    ) != (
        expected_schema,
        1,
        "polis-a-b-qualification-v2-v1",
        "polis-a-b-calibration-v2-v1",
        SOURCE_SNAPSHOT_SHA256,
    ):
        _fail("report identity is invalid")
    hashes = value["repetition_hashes"]
    if (
        not isinstance(hashes, list)
        or len(hashes) != 5
        or any(
            not isinstance(item, str) or re.fullmatch(r"[0-9a-f]{64}", item) is None
            for item in hashes
        )
        or len(set(hashes)) != 1
    ):
        _fail("report must contain five identical repetition hashes")
    outcomes_raw = value["outcomes"]
    if not isinstance(outcomes_raw, list) or len(outcomes_raw) != len(SOURCE_ROWS):
        _fail("report must contain exactly 20 outcomes")
    outcomes = tuple(
        _outcome(raw, expected)
        for raw, expected in zip(outcomes_raw, SOURCE_ROWS, strict=True)
    )
    aggregates: CalibrationRunAggregates | None = None
    if fields == RAW_FIELDS:
        raw = _object(value["aggregates"], _AGGREGATE_FIELDS, "report aggregates")
        aggregates = CalibrationRunAggregates(
            _number(raw["elapsed_seconds"], "elapsed seconds"),
            _integer(raw["peak_memory_bytes"], "peak memory bytes"),
        )
    return CalibrationReport(tuple(hashes), outcomes, aggregates)
