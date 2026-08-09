from __future__ import annotations

import json
import math
import re
from typing import NoReturn

from polis.evaluation.calibration_models import (
    CalibrationContractError,
    JsonObject,
    JsonValue,
)


def fail(message: str) -> NoReturn:
    raise CalibrationContractError(message)


def canonical_bytes(value: JsonValue) -> bytes:
    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except ValueError as error:
        raise CalibrationContractError("document contains non-finite data") from error
    return (serialized + "\n").encode()


def document(raw_bytes: bytes, label: str) -> JsonObject:
    def reject_constant(value: str) -> NoReturn:
        fail(f"{label} contains non-finite constant {value}")

    try:
        value: JsonValue = json.loads(raw_bytes, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationContractError(f"{label} is invalid JSON") from error
    if not isinstance(value, dict) or raw_bytes != canonical_bytes(value):
        fail(f"{label} must be a canonical JSON object")
    return value


def exact_object(value: JsonValue, fields: frozenset[str], label: str) -> JsonObject:
    if not isinstance(value, dict) or set(value) != fields:
        fail(f"{label} must contain exactly the required fields")
    return value


def strict_string(value: JsonValue, label: str) -> str:
    if not isinstance(value, str) or not value:
        fail(f"{label} must be a non-empty string")
    return value


def strict_integer(value: JsonValue, label: str) -> int:
    if type(value) is not int:
        fail(f"{label} must be an integer")
    return value


def strict_number(value: JsonValue, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        fail(f"{label} must be a finite number")
    return float(value)


def strict_digest(value: JsonValue, label: str) -> str:
    digest = strict_string(value, label)
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        fail(f"{label} must be a lowercase SHA-256 digest")
    return digest


def strict_string_list(value: JsonValue, label: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        fail(f"{label} must be a list")
    return tuple(strict_string(item, label) for item in value)
