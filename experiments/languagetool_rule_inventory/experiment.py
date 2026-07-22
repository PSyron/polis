"""Gold-isolated normalization and scoring for LanguageTool rule inspection."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from polis.evaluation.correction_corpus import (
    load_correction_corpus_json,
    select_cases_for_purpose,
)
from polis.llm import TextEdit

Split = Literal["development", "holdout"]


@dataclass(frozen=True, slots=True)
class InspectionInput:
    source: str


@dataclass(frozen=True, slots=True)
class InventoryCase:
    case_id: str
    split: Split
    protected_negative: bool
    inspection_input: InspectionInput
    expected_output: str
    gold_edits: tuple[TextEdit, ...]


@dataclass(frozen=True, slots=True)
class RuleObservation:
    rule_id: str
    upstream_category: str
    edit: TextEdit


@dataclass(frozen=True, slots=True)
class RuleMetrics:
    rule_id: str
    upstream_categories: tuple[str, ...]
    true_positive_edits: int
    false_positive_edits: int
    false_negative_edits: int
    protected_negative_changes: int
    cases_with_edits: int

    @property
    def precision(self) -> float:
        denominator = self.true_positive_edits + self.false_positive_edits
        return self.true_positive_edits / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positive_edits + self.false_negative_edits
        return self.true_positive_edits / denominator if denominator else 0.0


ObservationMap = Mapping[
    str,
    tuple[
        bool,
        tuple[TextEdit, ...],
        tuple[RuleObservation, ...],
    ],
]


def load_sentence_cases(path: Path, *, split: Split) -> tuple[InventoryCase, ...]:
    """Load reviewed sentences with source-only inspection inputs."""

    corpus = load_correction_corpus_json(path)
    purpose = "benchmark" if split == "development" else "quality_gate"
    selected = select_cases_for_purpose(corpus, purpose=purpose)
    return tuple(
        InventoryCase(
            case_id=case.id,
            split=split,
            protected_negative=case.stratum == "hard_negative",
            inspection_input=InspectionInput(case.input),
            expected_output=case.expected_output,
            gold_edits=tuple(
                TextEdit(edit.start, edit.end, edit.original, edit.suggestion)
                for edit in case.edits
            ),
        )
        for case in selected
        if case.split == split and case.unit == "sentence"
    )


def normalize_inspection_response(
    source: str, payload: object
) -> tuple[RuleObservation, ...]:
    """Normalize every offered replacement; never choose one using gold."""

    root = _mapping(payload, "inspection response")
    if root.get("operation") != "inspect":
        raise ValueError("inspection response operation mismatch")
    software = _mapping(root.get("software"), "software")
    if software.get("name") != "LanguageTool" or software.get("version") != "6.8":
        raise ValueError("inspection response identity mismatch")
    matches = root.get("matches")
    if not isinstance(matches, list):
        raise ValueError("inspection response must contain matches")
    observations: set[RuleObservation] = set()
    for raw_match in matches:
        match = _mapping(raw_match, "match")
        rule = _mapping(match.get("rule"), "rule")
        category = _mapping(rule.get("category"), "rule category")
        rule_id = _string(rule.get("id"), "rule id")
        category_id = _string(category.get("id"), "category id")
        offset = _non_negative_int(match.get("offset"), "offset")
        length = _non_negative_int(match.get("length"), "length")
        start = _utf16_to_codepoint(source, offset)
        end = _utf16_to_codepoint(source, offset + length)
        replacements = match.get("replacements")
        if not isinstance(replacements, list):
            raise ValueError("match replacements must be a list")
        for raw_replacement in replacements:
            replacement = _mapping(raw_replacement, "replacement")
            value = _string(replacement.get("value"), "replacement value")
            edit = _minimal_edit(start, source[start:end], value)
            if edit is not None:
                observations.add(RuleObservation(rule_id, category_id, edit))
    return tuple(
        sorted(
            observations,
            key=lambda item: (
                item.rule_id,
                item.edit.start,
                item.edit.end,
                item.edit.suggestion,
            ),
        )
    )


def score_rules(observations: ObservationMap) -> dict[str, RuleMetrics]:
    """Score each rule against all cases and all replacements it offered."""

    rule_ids = sorted(
        {
            observation.rule_id
            for _, _, case_observations in observations.values()
            for observation in case_observations
        }
    )
    result: dict[str, RuleMetrics] = {}
    for rule_id in rule_ids:
        true_positives = 0
        false_positives = 0
        false_negatives = 0
        protected_changes = 0
        cases_with_edits = 0
        categories: set[str] = set()
        for protected, expected, case_observations in observations.values():
            relevant = tuple(
                item for item in case_observations if item.rule_id == rule_id
            )
            actual = {item.edit for item in relevant}
            gold = set(expected)
            categories.update(item.upstream_category for item in relevant)
            true_positives += len(actual & gold)
            false_positives += len(actual - gold)
            false_negatives += len(gold - actual)
            cases_with_edits += bool(actual)
            protected_changes += protected and bool(actual)
        result[rule_id] = RuleMetrics(
            rule_id,
            tuple(sorted(categories)),
            true_positives,
            false_positives,
            false_negatives,
            protected_changes,
            cases_with_edits,
        )
    return result


def select_rule_allowlist(metrics: Mapping[str, RuleMetrics]) -> tuple[str, ...]:
    """Select useful rules with exact development precision and safety."""

    return tuple(
        sorted(
            rule_id
            for rule_id, item in metrics.items()
            if item.true_positive_edits > 0
            and item.precision == 1.0
            and item.protected_negative_changes == 0
        )
    )


def disqualify_conflicting_rules(
    observations: ObservationMap, candidates: tuple[str, ...]
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Remove every rule involved in a conflicting combined suggestion."""

    candidate_set = set(candidates)
    conflicting: set[str] = set()
    for _, _, case_observations in observations.values():
        relevant = tuple(
            item for item in case_observations if item.rule_id in candidate_set
        )
        for index, left in enumerate(relevant):
            for right in relevant[index + 1 :]:
                if left.rule_id != right.rule_id and _edits_conflict(
                    left.edit, right.edit
                ):
                    conflicting.update((left.rule_id, right.rule_id))
    return (
        tuple(rule_id for rule_id in candidates if rule_id not in conflicting),
        tuple(sorted(conflicting)),
    )


def _edits_conflict(left: TextEdit, right: TextEdit) -> bool:
    if left == right:
        return False
    if left.start == left.end and right.start == right.end:
        return bool(left.start == right.start)
    if left.start == left.end:
        return bool(right.start <= left.start <= right.end)
    if right.start == right.end:
        return bool(left.start <= right.start <= left.end)
    return bool(max(left.start, right.start) < min(left.end, right.end))


def validate_privacy_safe_report(raw: object) -> dict[str, Any]:
    """Reject committed evidence containing analyzed text or raw responses."""

    report = _mapping(raw, "report")
    required = {
        "schema_version",
        "experiment_id",
        "configuration_sha256",
        "decision",
        "environment",
        "summary",
        "rules",
        "case_evidence",
        "holdout",
    }
    if set(report) != required:
        raise ValueError("report fields are not closed")
    forbidden = {
        "source",
        "source_text",
        "input",
        "expected_output",
        "raw_response",
        "replacement",
        "suggestion",
        "original",
    }
    if _contains_key(report, forbidden):
        raise ValueError("report cannot contain raw analyzed text or responses")
    return report


def _contains_key(raw: object, forbidden: set[str]) -> bool:
    if isinstance(raw, dict):
        return any(
            key in forbidden or _contains_key(value, forbidden)
            for key, value in raw.items()
        )
    if isinstance(raw, list | tuple):
        return any(_contains_key(value, forbidden) for value in raw)
    return False


def _minimal_edit(start: int, original: str, replacement: str) -> TextEdit | None:
    prefix = 0
    while (
        prefix < len(original)
        and prefix < len(replacement)
        and original[prefix] == replacement[prefix]
    ):
        prefix += 1
    original_tail = len(original)
    replacement_tail = len(replacement)
    while (
        original_tail > prefix
        and replacement_tail > prefix
        and original[original_tail - 1] == replacement[replacement_tail - 1]
    ):
        original_tail -= 1
        replacement_tail -= 1
    suggestion = replacement[prefix:replacement_tail]
    selected_original = original[prefix:original_tail]
    if selected_original == suggestion:
        return None
    return TextEdit(
        start + prefix,
        start + original_tail,
        selected_original,
        suggestion,
    )


def _utf16_to_codepoint(source: str, offset: int) -> int:
    units = 0
    for index, character in enumerate(source):
        if units == offset:
            return index
        width = 2 if ord(character) > 0xFFFF else 1
        if units < offset < units + width:
            raise ValueError("LanguageTool offset splits a surrogate pair")
        units += width
    if units == offset:
        return len(source)
    raise ValueError("LanguageTool offset is outside the source")


def _mapping(raw: object, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be an object")
    return raw


def _string(raw: object, label: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} must be a non-empty string")
    return raw


def _non_negative_int(raw: object, label: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return raw


__all__ = [
    "InspectionInput",
    "InventoryCase",
    "RuleMetrics",
    "RuleObservation",
    "load_sentence_cases",
    "normalize_inspection_response",
    "score_rules",
    "select_rule_allowlist",
    "validate_privacy_safe_report",
]
