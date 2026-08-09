from __future__ import annotations

import hashlib
import json
import math
from typing import Final

from polis.evaluation.calibration_models import (
    CalibrationContractError,
    CalibrationSourceIdentity,
    CurrentPolicyState,
    JsonValue,
)
from polis.evaluation.calibration_source_rows import SOURCE_ROWS as _SOURCE_ROWS
from polis.evaluation.holdout_models import SourceIdentity
from polis.evaluation.holdout_sources import current_sources

SOURCE_SNAPSHOT_SHA256: Final = (
    "92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92"
)
SOURCE_ROWS: Final[tuple[CalibrationSourceIdentity, ...]] = _SOURCE_ROWS


def _policy_state(value: str) -> CurrentPolicyState:
    if value == "automatic":
        return "automatic"
    if value == "review-only":
        return "review-only"
    raise CalibrationContractError("current policy state is invalid")


def _parse_row(value: JsonValue) -> CalibrationSourceIdentity:
    if not isinstance(value, list) or len(value) != 7:
        raise CalibrationContractError("source row must contain exactly seven fields")
    source, category, operation, behavior, policy, confidence, state = value
    strings = (source, category, operation, behavior, policy, state)
    if any(not isinstance(item, str) for item in strings):
        raise CalibrationContractError("source row string fields must be strings")
    if type(confidence) not in (int, float) or not math.isfinite(confidence):
        raise CalibrationContractError("emitted confidence must be a finite number")
    if not 0.0 <= confidence <= 1.0:
        raise CalibrationContractError("emitted confidence must be within zero and one")
    if state not in ("automatic", "review-only"):
        raise CalibrationContractError("current policy state is invalid")
    return CalibrationSourceIdentity(
        source=source,
        category=category,
        operation=operation,
        behavior_version=behavior,
        source_policy_version=policy,
        emitted_confidence=float(confidence),
        current_policy_state=_policy_state(state),
    )


def parse_source_rows(value: JsonValue) -> tuple[CalibrationSourceIdentity, ...]:
    if not isinstance(value, list):
        raise CalibrationContractError("source rows must be a list")
    parsed = tuple(_parse_row(row) for row in value)
    if parsed != SOURCE_ROWS:
        raise CalibrationContractError("source rows must match the approved snapshot")
    return parsed


def canonical_source_bytes(
    rows: tuple[CalibrationSourceIdentity, ...] = SOURCE_ROWS,
) -> bytes:
    payload = [row.as_tuple() for row in rows]
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return (serialized + "\n").encode()


def _runtime_identity(row: CalibrationSourceIdentity) -> SourceIdentity:
    return SourceIdentity(
        source=row.source,
        category=row.category,
        operation=row.operation,
        behavior_version=row.behavior_version,
        source_policy_version=row.source_policy_version,
    )


def validate_live_sources() -> tuple[CalibrationSourceIdentity, ...]:
    try:
        observed = current_sources()
    except Exception as error:  # noqa: BLE001  # noqa: BROAD_EXCEPT_OK
        raise CalibrationContractError(
            "current calibration source snapshot is unavailable"
        ) from error
    expected = tuple(_runtime_identity(row) for row in SOURCE_ROWS)
    if observed != expected:
        raise CalibrationContractError(
            "current calibration source snapshot does not match the approved snapshot"
        )
    digest = hashlib.sha256(canonical_source_bytes()).hexdigest()
    if digest != SOURCE_SNAPSHOT_SHA256:
        raise CalibrationContractError("calibration source snapshot digest drifted")
    return SOURCE_ROWS
