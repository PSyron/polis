"""Strict parsing helpers for quality-development dataset documents."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum

from polis.evaluation._quality_types import (
    JsonValue,
    QualityCase,
    QualityCaseKind,
    QualityDatasetError,
    QualityExpectedFinding,
    QualityFeature,
    QualityPhenomenon,
    QualityReview,
)

DATASET_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "id",
        "dataset_version",
        "license",
        "source",
        "cases",
    }
)
MANIFEST_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "dataset_id",
        "dataset_version",
        "canonical_sha256",
        "review",
    }
)
_REVIEW_FIELDS = frozenset(
    {
        "status",
        "reviewer_role",
        "checklist_version",
        "reviewed_case_ids",
        "canonical_sha256",
    }
)
_CASE_FIELDS = frozenset(
    {
        "id",
        "kind",
        "phenomenon",
        "pair_id",
        "features",
        "text",
        "expected_findings",
        "rationale",
    }
)
_FINDING_FIELDS = frozenset(
    {"category", "start", "end", "original", "suggestion", "rationale"}
)
_IDENTIFIER = re.compile(r"[a-z][a-z0-9_]*\Z")
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def parse_case(raw: JsonValue, seen_ids: set[str]) -> QualityCase:
    case = require_object(raw, "quality case")
    require_exact_fields(case, _CASE_FIELDS, "quality case")
    case_id = _require_identifier(case["id"], "quality case id")
    if case_id in seen_ids:
        raise QualityDatasetError(f"duplicate quality case id: {case_id}")
    seen_ids.add(case_id)
    kind = _require_enum(case["kind"], QualityCaseKind, "quality case kind")
    phenomenon = _optional_enum(
        case["phenomenon"], QualityPhenomenon, "quality case phenomenon"
    )
    pair_id = _optional_identifier(case["pair_id"], "quality case pair_id")
    text = case["text"]
    if not isinstance(text, str) or not text.strip():
        raise QualityDatasetError("quality case text must be a non-blank string")
    raw_features = case["features"]
    if not isinstance(raw_features, list):
        raise QualityDatasetError("quality case features must be a list")
    features = frozenset(
        _require_enum(item, QualityFeature, "quality case feature")
        for item in raw_features
    )
    if len(features) != len(raw_features):
        raise QualityDatasetError("quality case features must be unique")
    raw_findings = case["expected_findings"]
    if not isinstance(raw_findings, list):
        raise QualityDatasetError("quality case expected_findings must be a list")
    findings = tuple(_parse_finding(item, text) for item in raw_findings)
    rationale = case["rationale"]
    if rationale is not None and (
        not isinstance(rationale, str) or not rationale.strip()
    ):
        if kind is QualityCaseKind.ABSTAIN:
            raise QualityDatasetError("abstain case rationale must be non-blank")
        raise QualityDatasetError("quality case rationale must be null or non-blank")
    return QualityCase(
        case_id, kind, phenomenon, pair_id, features, text, findings, rationale
    )


def parse_review(raw: JsonValue, *, checklist_version: str) -> QualityReview:
    review = require_object(raw, "quality review")
    require_exact_fields(review, _REVIEW_FIELDS, "quality review")
    status = review["status"]
    if not isinstance(status, str) or status not in {
        "pending_maintainer_review",
        "maintainer-reviewed",
    }:
        raise QualityDatasetError("quality review status is unsupported")
    require_literal(review, "reviewer_role", "Polis maintainer", "quality review")
    require_literal(review, "checklist_version", checklist_version, "quality review")
    raw_ids = review["reviewed_case_ids"]
    if not isinstance(raw_ids, list):
        raise QualityDatasetError("reviewed_case_ids must be a list")
    reviewed_ids = tuple(
        _require_identifier(item, "reviewed case id") for item in raw_ids
    )
    if status == "pending_maintainer_review" and reviewed_ids:
        raise QualityDatasetError("pending review must not contain reviewed_case_ids")
    return QualityReview(
        status=status,
        reviewer_role="Polis maintainer",
        checklist_version=checklist_version,
        reviewed_case_ids=reviewed_ids,
        canonical_sha256=require_sha256(
            review["canonical_sha256"], "quality review canonical_sha256"
        ),
    )


def canonical_hash(raw: JsonValue) -> str:
    encoded = json.dumps(
        raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def require_object(raw: JsonValue, label: str) -> dict[str, JsonValue]:
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise QualityDatasetError(f"{label} must be a JSON object with string keys")
    return raw


def require_exact_fields(
    value: dict[str, JsonValue], expected: frozenset[str], label: str
) -> None:
    if set(value) != expected:
        raise QualityDatasetError(f"{label} must contain exactly the required fields")


def require_literal(
    value: dict[str, JsonValue], field: str, expected: JsonValue, label: str
) -> None:
    if value[field] != expected or type(value[field]) is not type(expected):
        raise QualityDatasetError(f"{label} {field} must be {expected!r}")


def require_sha256(value: JsonValue, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise QualityDatasetError(f"{label} must be a lowercase SHA-256")
    return value


def _parse_finding(raw: JsonValue, text: str) -> QualityExpectedFinding:
    finding = require_object(raw, "quality expected finding")
    require_exact_fields(finding, _FINDING_FIELDS, "quality expected finding")
    category = finding["category"]
    if not isinstance(category, str) or category not in {
        "inflection",
        "agreement",
        "spelling",
        "syntax",
        "punctuation",
    }:
        raise QualityDatasetError("quality finding category is unknown")
    start = _require_offset(finding["start"], "finding start")
    end = _require_offset(finding["end"], "finding end")
    if end < start or end > len(text):
        raise QualityDatasetError("finding range must be within the input text")
    original = finding["original"]
    suggestion = finding["suggestion"]
    rationale = finding["rationale"]
    if not isinstance(original, str) or text[start:end] != original:
        raise QualityDatasetError("finding original does not match text range")
    if not isinstance(suggestion, str) or suggestion == original:
        raise QualityDatasetError("finding suggestion must differ from original")
    if not isinstance(rationale, str) or not rationale.strip():
        raise QualityDatasetError("finding rationale must be a non-blank string")
    return QualityExpectedFinding(category, start, end, original, suggestion, rationale)


def _require_identifier(value: JsonValue, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise QualityDatasetError(f"{label} must use lowercase snake_case")
    return value


def _optional_identifier(value: JsonValue, label: str) -> str | None:
    return None if value is None else _require_identifier(value, label)


def _require_offset(value: JsonValue, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise QualityDatasetError(f"{label} must be a non-negative integer")
    return value


def _require_enum[T: StrEnum](value: JsonValue, enum_type: type[T], label: str) -> T:
    if not isinstance(value, str):
        raise QualityDatasetError(f"{label} is unknown")
    try:
        return enum_type(value)
    except (TypeError, ValueError) as error:
        raise QualityDatasetError(f"{label} is unknown") from error


def _optional_enum[T: StrEnum](
    value: JsonValue, enum_type: type[T], label: str
) -> T | None:
    return None if value is None else _require_enum(value, enum_type, label)
