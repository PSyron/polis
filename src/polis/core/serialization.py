"""Strict, deterministic JSON serialization for public analysis models."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import cast

from polis.core.models import (
    AnalysisOptions,
    AnalysisResult,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
)

ANALYSIS_SCHEMA_VERSION = 1

_RESULT_FIELDS = frozenset({"schema_version", "text", "options", "issues"})
_OPTIONS_FIELDS = frozenset({"categories", "minimum_confidence"})
_FINDING_FIELDS = frozenset(
    {
        "id",
        "category",
        "severity",
        "message",
        "explanation",
        "original",
        "suggestion",
        "start",
        "end",
        "confidence",
        "source",
    }
)


def analysis_result_to_json(result: AnalysisResult) -> str:
    """Encode an analysis result as canonical schema-version-1 JSON."""

    if not isinstance(result, AnalysisResult):
        raise TypeError("result must be an AnalysisResult")
    payload = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "text": result.text,
        "options": {
            "categories": (
                None
                if result.options.categories is None
                else sorted(category.value for category in result.options.categories)
            ),
            "minimum_confidence": result.options.minimum_confidence.value,
        },
        "issues": [
            {
                "id": issue.id,
                "category": issue.category.value,
                "severity": issue.severity.value,
                "message": issue.message,
                "explanation": issue.explanation,
                "original": issue.original,
                "suggestion": issue.suggestion,
                "start": issue.start,
                "end": issue.end,
                "confidence": issue.confidence.value,
                "source": str(issue.source),
            }
            for issue in result.issues
        ],
    }
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def analysis_result_from_json(value: str) -> AnalysisResult:
    """Decode strict schema-version-1 JSON and validate every public invariant."""

    if not isinstance(value, str):
        raise TypeError("JSON input must be a string")
    try:
        loaded: object = json.loads(
            value,
            object_pairs_hook=_object_without_duplicate_keys,
            parse_constant=_reject_non_finite_constant,
        )
    except json.JSONDecodeError as error:
        raise ValueError("invalid analysis-result JSON") from error

    payload = _object(loaded, _RESULT_FIELDS, "analysis result")
    version = _integer(payload["schema_version"], "schema_version")
    if version != ANALYSIS_SCHEMA_VERSION:
        raise ValueError(f"unsupported analysis schema version: {version}")

    options_payload = _object(payload["options"], _OPTIONS_FIELDS, "options")
    raw_categories = options_payload["categories"]
    categories: list[Category] | None
    if raw_categories is None:
        categories = None
    else:
        category_values = _array(raw_categories, "options.categories")
        categories = [
            _enum(Category, item, "options.categories") for item in category_values
        ]
        if len(categories) != len(set(categories)):
            raise ValueError("options.categories contains duplicate values")
    options = AnalysisOptions(
        categories=categories,
        minimum_confidence=Confidence(
            _number(options_payload["minimum_confidence"], "minimum_confidence")
        ),
    )

    raw_issues = _array(payload["issues"], "issues")
    issues = tuple(_finding(item, index) for index, item in enumerate(raw_issues))
    return AnalysisResult(
        text=_text(payload["text"], "text"), issues=issues, options=options
    )


def _finding(value: object, index: int) -> Finding:
    context = f"issues[{index}]"
    payload = _object(value, _FINDING_FIELDS, context)
    suggestion_value = payload["suggestion"]
    suggestion = (
        None
        if suggestion_value is None
        else _text(suggestion_value, f"{context}.suggestion")
    )
    return Finding(
        id=_text(payload["id"], f"{context}.id"),
        category=_enum(Category, payload["category"], f"{context}.category"),
        severity=_enum(Severity, payload["severity"], f"{context}.severity"),
        message=_text(payload["message"], f"{context}.message"),
        explanation=_text(payload["explanation"], f"{context}.explanation"),
        original=_text(payload["original"], f"{context}.original"),
        suggestion=suggestion,
        start=_integer(payload["start"], f"{context}.start"),
        end=_integer(payload["end"], f"{context}.end"),
        confidence=Confidence(_number(payload["confidence"], f"{context}.confidence")),
        source=Source.parse(_text(payload["source"], f"{context}.source")),
    )


def _object_without_duplicate_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _reject_non_finite_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON number is not supported: {value}")


def _object(
    value: object, expected_fields: frozenset[str], context: str
) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(f"{context} must be a JSON object")
    payload = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in payload):
        raise TypeError(f"{context} object keys must be strings")
    typed = cast(dict[str, object], payload)
    actual_fields = frozenset(typed)
    if actual_fields != expected_fields:
        missing = sorted(expected_fields - actual_fields)
        unknown = sorted(actual_fields - expected_fields)
        raise ValueError(
            f"{context} fields do not match schema; "
            f"missing={missing}, unknown={unknown}"
        )
    return typed


def _array(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"{context} must be a JSON array")
    return cast(list[object], value)


def _text(value: object, context: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{context} must be a string")
    return value


def _integer(value: object, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{context} must be an integer, not a boolean")
    return value


def _number(value: object, context: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{context} must be a number, not a boolean")
    try:
        return float(value)
    except OverflowError as error:
        raise ValueError(f"{context} must be a finite number") from error


def _enum[EnumType: StrEnum](
    enum_type: type[EnumType], value: object, context: str
) -> EnumType:
    raw = _text(value, context)
    try:
        return enum_type(raw)
    except ValueError as error:
        raise ValueError(f"unknown {context} value: {raw!r}") from error
