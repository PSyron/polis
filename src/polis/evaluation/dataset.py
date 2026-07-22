"""Strictly validate the versioned, project-authored evaluation dataset."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from polis.core import Category

DATASET_PATH = Path(__file__).parent / "datasets" / "v1" / "cases.json"
_CASE_ID = re.compile(r"[a-z][a-z0-9_]*\Z")
_PROVENANCE_FIELDS = frozenset(
    {"source", "license", "created", "review_status", "notes"}
)
_CASE_FIELDS = frozenset({"id", "outcome", "text", "provenance", "expected_findings"})
_FINDING_FIELDS = frozenset(
    {"category", "start", "end", "original", "suggestion", "rationale"}
)


@dataclass(frozen=True, slots=True)
class ExpectedFinding:
    """One gold minimal correction for an intentionally incorrect case."""

    category: str
    start: int
    end: int
    original: str
    suggestion: str
    rationale: str


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """A reviewed input and its expected findings or explicit negative result."""

    id: str
    outcome: str
    text: str
    findings: tuple[ExpectedFinding, ...]


@dataclass(frozen=True, slots=True)
class EvaluationDataset:
    """A schema-versioned collection of evaluation cases."""

    schema_version: int
    id: str
    cases: tuple[EvaluationCase, ...]
    source: str
    canonical_hash: str


def load_dataset(path: Path = DATASET_PATH) -> EvaluationDataset:
    """Load and validate a UTF-8 evaluation dataset from ``path``."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid dataset JSON: {path}") from error
    return validate_dataset(raw, source=str(path))


def validate_dataset(raw: object, *, source: str = "memory") -> EvaluationDataset:
    """Return validated records from one exact schema-version-1 JSON object."""

    dataset = _require_object(raw, "dataset")
    _require_exact_fields(
        dataset, {"schema_version", "id", "provenance", "cases"}, "dataset"
    )
    if dataset["schema_version"] != 1:
        raise ValueError("dataset schema_version must be 1")
    dataset_id = _require_case_id(dataset["id"], "dataset id")
    _validate_provenance(dataset["provenance"], "dataset provenance")
    raw_cases = dataset["cases"]
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("dataset cases must be a non-empty list")

    seen_ids: set[str] = set()
    cases = tuple(_validate_case(case, seen_ids) for case in raw_cases)
    return EvaluationDataset(
        schema_version=1,
        id=dataset_id,
        cases=cases,
        source=source,
        canonical_hash=_canonical_hash(raw),
    )


def _canonical_hash(raw: object) -> str:
    canonical = json.dumps(
        raw,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _validate_case(raw: object, seen_ids: set[str]) -> EvaluationCase:
    case = _require_object(raw, "case")
    _require_exact_fields(case, _CASE_FIELDS, "case")
    case_id = _require_case_id(case["id"], "case id")
    if case_id in seen_ids:
        raise ValueError(f"duplicate case id: {case_id}")
    seen_ids.add(case_id)
    outcome = case["outcome"]
    if outcome not in {"correct", "incorrect"}:
        raise ValueError("case outcome must be 'correct' or 'incorrect'")
    text = case["text"]
    if not isinstance(text, str) or not text.strip():
        raise ValueError("case text must be a non-blank string")
    _validate_provenance(case["provenance"], f"case {case_id} provenance")
    expected = case["expected_findings"]
    if outcome == "correct" and expected != []:
        raise ValueError("correct case must explicitly contain no expected findings")
    if outcome == "incorrect" and (not isinstance(expected, list) or not expected):
        raise ValueError("incorrect case must contain at least one expected finding")
    if not isinstance(expected, list):
        raise ValueError("expected_findings must be a list")
    findings = tuple(_validate_finding(item, text, case_id) for item in expected)
    _validate_non_overlapping(findings, case_id)
    return EvaluationCase(
        id=case_id,
        outcome=cast(str, outcome),
        text=text,
        findings=findings,
    )


def _validate_finding(raw: object, text: str, case_id: str) -> ExpectedFinding:
    finding = _require_object(raw, f"case {case_id} finding")
    _require_exact_fields(finding, _FINDING_FIELDS, "expected finding")
    category = finding["category"]
    if not isinstance(category, str) or category not in {
        item.value for item in Category
    }:
        raise ValueError(f"unknown category: {category!r}")
    start = _require_offset(finding["start"], "finding start")
    end = _require_offset(finding["end"], "finding end")
    if end < start or end > len(text):
        raise ValueError("finding range must be within the input text")
    original = finding["original"]
    suggestion = finding["suggestion"]
    rationale = finding["rationale"]
    if not isinstance(original, str) or not isinstance(suggestion, str):
        raise ValueError("finding original and suggestion must be strings")
    if text[start:end] != original:
        raise ValueError("finding original does not match text range")
    if suggestion == original:
        raise ValueError("finding suggestion must differ from original")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("finding rationale must be a non-blank string")
    return ExpectedFinding(
        category=category,
        start=start,
        end=end,
        original=original,
        suggestion=suggestion,
        rationale=rationale,
    )


def _validate_non_overlapping(
    findings: tuple[ExpectedFinding, ...], case_id: str
) -> None:
    replacements = sorted(
        (item.start, item.end) for item in findings if item.start != item.end
    )
    for (_, previous_end), (start, _) in zip(
        replacements, replacements[1:], strict=False
    ):
        if start < previous_end:
            raise ValueError(f"case {case_id} has overlapping expected findings")

    insertion_offsets = [item.start for item in findings if item.start == item.end]
    if len(insertion_offsets) != len(set(insertion_offsets)):
        raise ValueError(f"case {case_id} has duplicate insertions at one offset")
    for insertion in insertion_offsets:
        if any(start <= insertion < end for start, end in replacements):
            raise ValueError(f"case {case_id} has colliding expected findings")


def _validate_provenance(raw: object, label: str) -> None:
    provenance = _require_object(raw, label)
    _require_exact_fields(provenance, _PROVENANCE_FIELDS, label)
    if provenance["license"] != "CC0-1.0":
        raise ValueError(f"{label} license must be CC0-1.0")
    for field in ("source", "created", "review_status", "notes"):
        value = provenance[field]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} {field} must be a non-blank string")
    if provenance["review_status"] != "human-reviewed":
        raise ValueError(f"{label} review_status must be human-reviewed")


def _require_object(raw: object, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{label} must be a JSON object with string keys")
    return cast(dict[str, Any], raw)


def _require_exact_fields(
    value: dict[str, Any], expected: set[str] | frozenset[str], label: str
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        detail = []
        if missing:
            detail.append(f"missing fields: {', '.join(missing)}")
        if unknown:
            detail.append(f"unknown fields: {', '.join(unknown)}")
        raise ValueError(
            f"{label} must contain exactly the required fields ({'; '.join(detail)})"
        )


def _require_case_id(value: object, label: str) -> str:
    if not isinstance(value, str) or _CASE_ID.fullmatch(value) is None:
        raise ValueError(f"{label} must use lowercase snake_case")
    return value


def _require_offset(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value
