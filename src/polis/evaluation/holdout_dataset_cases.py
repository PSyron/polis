from __future__ import annotations

import re

from polis.evaluation.holdout_models import (
    HoldoutCase,
    HoldoutExpectedFinding,
    JsonObject,
    JsonValue,
)

_CASE_ID = re.compile(r"abv1-[0-9]{3}")
_ROLES = {"error", "correct", "abstain", "conflict"}
_FEATURES = {
    "abbreviation",
    "abstention_boundary",
    "agreement",
    "closed_fullmatch_negative",
    "identifier_boundary",
    "inflection",
    "morphology_ambiguous",
    "morphology_unknown",
    "multi_line",
    "multi_sentence",
    "novel_context",
    "number_boundary",
    "numeric_decimal",
    "overlap_conflict",
    "paired_close_negative",
    "proper_name",
    "punctuation",
    "quoted_context",
    "spelling",
    "syntax",
    "unicode",
    "version_number",
}


class HoldoutCaseError(RuntimeError):
    pass


def _object(value: JsonValue, fields: set[str], label: str) -> JsonObject:
    if not isinstance(value, dict) or set(value) != fields:
        raise HoldoutCaseError(f"{label} must contain exactly the required fields")
    return value


def _strings(value: JsonValue, allowed: set[str], label: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or item not in allowed for item in value)
    ):
        raise HoldoutCaseError(f"{label} is invalid")
    result = tuple(value)
    if len(set(result)) != len(result):
        raise HoldoutCaseError(f"{label} must be unique")
    return result


def _expected_findings(
    value: JsonValue,
    *,
    text: str,
    targets: tuple[str, ...],
    source_categories: dict[str, str],
) -> tuple[HoldoutExpectedFinding, ...]:
    if not isinstance(value, list):
        raise HoldoutCaseError("expected_findings must be a list")
    parsed: list[HoldoutExpectedFinding] = []
    for raw in value:
        finding = _object(
            raw,
            {"category", "start", "end", "original", "suggestion", "source"},
            "expected finding",
        )
        start, end = finding["start"], finding["end"]
        if (
            type(start) is not int
            or type(end) is not int
            or start < 0
            or end < start
            or end > len(text)
        ):
            raise HoldoutCaseError("expected finding range is invalid")
        original, suggestion = finding["original"], finding["suggestion"]
        source, category = finding["source"], finding["category"]
        if (
            not isinstance(original, str)
            or not isinstance(suggestion, str)
            or suggestion == original
            or original != text[start:end]
            or not isinstance(source, str)
            or source not in targets
            or not isinstance(category, str)
            or source_categories[source] != category
        ):
            raise HoldoutCaseError("expected finding identity is invalid")
        parsed.append(
            HoldoutExpectedFinding(category, start, end, original, suggestion, source)
        )
    return tuple(parsed)


def parse_case(
    value: JsonValue,
    *,
    source_categories: dict[str, str],
    seen_ids: set[str],
) -> HoldoutCase:
    item = _object(
        value,
        {
            "id",
            "license",
            "provenance",
            "role",
            "targets",
            "taxonomy",
            "text",
            "expected_findings",
        },
        "holdout case",
    )
    case_id = item["id"]
    if (
        not isinstance(case_id, str)
        or _CASE_ID.fullmatch(case_id) is None
        or case_id in seen_ids
    ):
        raise HoldoutCaseError("holdout case id is invalid or duplicated")
    seen_ids.add(case_id)
    if (
        item["license"] != "CC0-1.0"
        or item["provenance"] != "project-authored-independent-review"
    ):
        raise HoldoutCaseError("holdout case provenance is invalid")
    role = item["role"]
    if not isinstance(role, str) or role not in _ROLES:
        raise HoldoutCaseError("holdout case role is invalid")
    targets = _strings(item["targets"], set(source_categories), "case targets")
    taxonomy = _object(item["taxonomy"], {"features"}, "case taxonomy")
    features = _strings(taxonomy["features"], _FEATURES, "case features")
    text = item["text"]
    if not isinstance(text, str) or not text.strip():
        raise HoldoutCaseError("holdout case text is invalid")
    findings = _expected_findings(
        item["expected_findings"],
        text=text,
        targets=targets,
        source_categories=source_categories,
    )
    if role == "error" and not findings:
        raise HoldoutCaseError("error case requires an expected finding")
    if role in {"correct", "abstain"} and findings:
        raise HoldoutCaseError("no-change case cannot contain expected findings")
    if "paired_close_negative" in features and findings:
        raise HoldoutCaseError("paired close negative must not contain findings")
    if role == "conflict":
        claims = {
            (item.start, item.end, item.original, item.suggestion) for item in findings
        }
        if (
            len(findings) < 2
            or len(claims) != 1
            or len({item.source for item in findings}) < 2
        ):
            raise HoldoutCaseError("conflict case claims are invalid")
    return HoldoutCase(case_id, role, targets, features, text, findings)
