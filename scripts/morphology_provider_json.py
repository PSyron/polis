from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypeGuard

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)


@dataclass(slots=True)
class ContractError(Exception):
    detail: str

    def __str__(self) -> str:
        return self.detail


def canonical_bytes(value: JsonValue) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _is_json_value(value: JsonValue | bytes) -> TypeGuard[JsonValue]:
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(_is_json_value(item) for item in value.values())
    return False


def read_json(path: Path) -> JsonValue:
    try:
        value: JsonValue | bytes = json.loads(path.read_text())
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read JSON {path}: {error}") from error
    if not _is_json_value(value):
        raise ContractError(f"JSON {path} contains unsupported values")
    return value


def mapping(value: JsonValue, context: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise ContractError(f"{context} must be an object")
    return value


def exact_fields(
    value: dict[str, JsonValue], expected: frozenset[str], context: str
) -> None:
    extras = set(value) - expected
    missing = expected - set(value)
    if extras:
        raise ContractError(f"{context} has unexpected fields: {sorted(extras)}")
    if missing:
        raise ContractError(f"{context} is missing fields: {sorted(missing)}")


def string(value: JsonValue, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContractError(f"{context} must be a non-empty string")
    return value


def optional_string(value: JsonValue, context: str) -> str | None:
    if value is None:
        return None
    return string(value, context)


def number(value: JsonValue, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{context} must be a number")
    return float(value)


def integer(value: JsonValue, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{context} must be an integer")
    return value


def boolean(value: JsonValue, context: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{context} must be a boolean")
    return value
