from __future__ import annotations

from polis.evaluation.holdout_models import (
    HoldoutReportError,
    HoldoutSourceOutcome,
    JsonObject,
    JsonValue,
)
from polis.evaluation.holdout_sources import current_sources

_FIELDS = {
    "identity",
    "case_count",
    "expected_findings",
    "predicted_findings",
    "true_positives",
    "false_positives",
    "false_negatives",
    "span_matches",
    "correction_matches",
    "correct_cases",
    "alarmed_correct_cases",
    "verdict",
}
_COUNT_ORDER = (
    "case_count",
    "expected_findings",
    "predicted_findings",
    "true_positives",
    "false_positives",
    "false_negatives",
    "span_matches",
    "correction_matches",
    "correct_cases",
    "alarmed_correct_cases",
)
_VERDICTS = {"pass", "fail_threshold", "insufficient_evidence", "invalid"}


def parse_source_outcomes(value: JsonValue) -> tuple[HoldoutSourceOutcome, ...]:
    if not isinstance(value, list):
        raise HoldoutReportError("per_source must be a list")
    expected = tuple(
        (
            item.source,
            item.category,
            item.operation,
            item.behavior_version,
            item.source_policy_version,
        )
        for item in current_sources()
    )
    outcomes: list[HoldoutSourceOutcome] = []
    for value_item in value:
        if not isinstance(value_item, dict) or set(value_item) != _FIELDS:
            raise HoldoutReportError("source outcome has invalid fields")
        item: JsonObject = value_item
        identity_value = item["identity"]
        if (
            not isinstance(identity_value, list)
            or len(identity_value) != 5
            or any(not isinstance(part, str) for part in identity_value)
        ):
            raise HoldoutReportError("source identity is invalid")
        identity = (
            identity_value[0],
            identity_value[1],
            identity_value[2],
            identity_value[3],
            identity_value[4],
        )
        counts = tuple(_count(item[key], key) for key in _COUNT_ORDER)
        verdict = item["verdict"]
        if not isinstance(verdict, str) or verdict not in _VERDICTS:
            raise HoldoutReportError("source verdict is invalid")
        if counts[0] == 0 and verdict == "pass":
            raise HoldoutReportError("source coverage is insufficient")
        outcomes.append(HoldoutSourceOutcome(identity, *counts, verdict))
    if tuple(item.identity for item in outcomes) != expected:
        raise HoldoutReportError(
            "per-source identities must match the current composition root exactly"
        )
    return tuple(outcomes)


def _count(value: JsonValue, name: str) -> int:
    if type(value) is not int or value < 0:
        raise HoldoutReportError(f"{name} must be a non-negative integer")
    return value
