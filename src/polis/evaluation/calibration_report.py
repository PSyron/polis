from __future__ import annotations

from typing import Protocol

from polis.evaluation.calibration_models import (
    CalibrationReport,
    CalibrationRunAggregates,
    CalibrationRunResult,
    CalibrationSourceIdentity,
    JsonObject,
    JsonValue,
    KeyOutcome,
)
from polis.evaluation.calibration_report_parser import (
    COUNT_NAMES,
    IDENTITY_NAMES,
    METRIC_NAMES,
)
from polis.evaluation.calibration_report_parser import (
    canonical_report_bytes as _canonical_impl,
)
from polis.evaluation.calibration_report_parser import (
    parse_raw_report as _parse_impl,
)
from polis.evaluation.calibration_sources import SOURCE_SNAPSHOT_SHA256


class _CanonicalBytes(Protocol):
    def __call__(self, value: JsonValue, /) -> bytes: ...


class _ParseReport(Protocol):
    def __call__(self, raw_bytes: bytes, /) -> CalibrationReport: ...


_canonical: _CanonicalBytes = _canonical_impl
_parse: _ParseReport = _parse_impl


def parse_raw_report(raw_bytes: bytes) -> CalibrationReport:
    return _parse(raw_bytes)


def _identity_json(identity: CalibrationSourceIdentity) -> JsonObject:
    return dict(zip(IDENTITY_NAMES, identity.as_tuple(), strict=True))


def _outcome_json(outcome: KeyOutcome) -> JsonObject:
    return {
        "identity": _identity_json(outcome.identity),
        "counts": dict(zip(COUNT_NAMES, outcome.counts.as_tuple(), strict=True)),
        "metrics": dict(zip(METRIC_NAMES, outcome.metrics.as_tuple(), strict=True)),
        "observed_confidence": outcome.observed_confidence,
        "minimum_confidence": outcome.minimum_confidence,
        "verdict": outcome.verdict,
    }


def _report_object(result: CalibrationRunResult, *, normalized: bool) -> JsonObject:
    report_kind = "normalized" if normalized else "raw"
    report: JsonObject = {
        "schema_id": f"polis.a-b-calibration.{report_kind}-report",
        "schema_version": 1,
        "experiment_id": "polis-a-b-qualification-v2-v1",
        "dataset_id": "polis-a-b-calibration-v2-v1",
        "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
        "repetition_hashes": list(result.repetition_hashes),
        "outcomes": [_outcome_json(outcome) for outcome in result.outcomes],
    }
    if not normalized:
        report["aggregates"] = {
            "elapsed_seconds": result.aggregates.elapsed_seconds,
            "peak_memory_bytes": result.aggregates.peak_memory_bytes,
        }
    return report


def raw_report_bytes(result: CalibrationRunResult) -> bytes:
    raw = _canonical(_report_object(result, normalized=False))
    parse_raw_report(raw)
    return raw


def normalized_report_bytes(raw: CalibrationReport) -> bytes:
    placeholder = CalibrationRunAggregates(0.0, 0)
    result = CalibrationRunResult(raw.repetition_hashes, raw.outcomes, placeholder)
    normalized = _canonical(_report_object(result, normalized=True))
    parse_raw_report(normalized)
    return normalized


def threshold_selection_bytes(result: CalibrationRunResult) -> bytes:
    validated = parse_raw_report(raw_report_bytes(result))
    selections: list[JsonValue] = []
    for outcome in validated.outcomes:
        selections.append(
            {
                "identity": _identity_json(outcome.identity),
                "denominators": {
                    "error_cases": outcome.counts.error_cases,
                    "correct_cases": outcome.counts.correct_cases,
                },
                "metrics": dict(
                    zip(METRIC_NAMES, outcome.metrics.as_tuple(), strict=True)
                ),
                "verdict": outcome.verdict,
            }
        )
    return _canonical(
        {
            "schema_id": "polis.a-b-calibration.threshold-selection",
            "schema_version": 1,
            "experiment_id": "polis-a-b-qualification-v2-v1",
            "dataset_id": "polis-a-b-calibration-v2-v1",
            "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
            "authorization_status": "unsigned-non-authorizing",
            "selections": selections,
        }
    )
