from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from typing import NoReturn

from polis.evaluation.holdout_models import (
    HoldoutContractError,
    JsonObject,
    JsonValue,
    RawReport,
)


def fail(message: str) -> NoReturn:
    raise HoldoutContractError(message)


def canonical_sha256(raw: JsonObject) -> str:
    try:
        payload = json.dumps(
            raw,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except ValueError as error:
        raise HoldoutContractError("config contains a non-finite number") from error
    return hashlib.sha256(payload.encode()).hexdigest()


def object_value(value: JsonValue, fields: set[str], name: str) -> JsonObject:
    if not isinstance(value, dict) or set(value) != fields:
        fail(f"{name} must contain exactly the required fields")
    return value


def string_value(value: JsonValue, name: str) -> str:
    if not isinstance(value, str) or not value:
        fail(f"{name} must be a non-empty string")
    return value


def integer_value(value: JsonValue, name: str) -> int:
    if type(value) is not int:
        fail(f"{name} must be an integer")
    return value


def number_value(value: JsonValue, name: str) -> float:
    if type(value) not in (int, float):
        fail(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        fail(f"{name} must be finite")
    return number


def strings_value(value: JsonValue, name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        fail(f"{name} must be a string list")
    return tuple(value)


def normalized_report_bytes(report: RawReport) -> bytes:
    normalized = {
        "schema_id": "polis.a-b-one-shot.normalized-report",
        "schema_version": 1,
        "experiment_id": report.experiment_id,
        "identities": report.identities,
        "quality": asdict(report.quality),
        "per_source": [asdict(item) for item in report.per_source],
        "verdict": report.verdict,
    }
    return (
        json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode()
