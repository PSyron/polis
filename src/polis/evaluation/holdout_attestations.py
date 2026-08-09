from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from polis.evaluation.holdout_models import HoldoutAdmissionError, JsonObject


def metadata_object(path: Path) -> JsonObject:
    try:
        content = path.read_bytes()
    except OSError as error:
        raise HoldoutAdmissionError(
            f"required preflight evidence is unavailable or invalid: {path}"
        ) from error
    return metadata_bytes(content, str(path))


def metadata_bytes(content: bytes, label: str) -> JsonObject:
    def reject_constant(value: str) -> None:
        raise HoldoutAdmissionError(f"non-finite constant {value}")

    try:
        raw = json.loads(content, parse_constant=reject_constant)
    except (OSError, HoldoutAdmissionError, json.JSONDecodeError) as error:
        raise HoldoutAdmissionError(
            f"required preflight evidence is unavailable or invalid: {label}"
        ) from error
    if not isinstance(raw, dict):
        raise HoldoutAdmissionError(f"preflight evidence must be an object: {label}")
    return raw


def exact_fields(raw: JsonObject, expected: set[str], label: str) -> None:
    if set(raw) != expected:
        raise HoldoutAdmissionError(f"{label} must contain exactly the required fields")


def required_string(raw: JsonObject, field: str, label: str) -> str:
    value = raw[field]
    if not isinstance(value, str) or not value:
        raise HoldoutAdmissionError(f"{label} {field} must be a non-empty string")
    return value


def utc_timestamp(value: str, label: str) -> datetime:
    if not value.endswith("Z"):
        raise HoldoutAdmissionError(f"{label} must be a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise HoldoutAdmissionError(f"{label} must be a UTC timestamp") from error
    if parsed.tzinfo != UTC:
        raise HoldoutAdmissionError(f"{label} must be a UTC timestamp")
    return parsed
