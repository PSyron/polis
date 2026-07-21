"""Strict, experiment-only scoring for a local LanguageTool server."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_VERIFICATIONS = frozenset({"rules", "llm_planned", "negative"})
_CATEGORY_MAPPING_VERSION = 1
_SCORING_VERSION = 1


@dataclass(frozen=True, slots=True)
class GoldEdit:
    category: str
    start: int
    end: int
    original: str
    suggestion: str


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    case_id: str
    source: str
    expected_output: str
    verification: str
    expected_edits: tuple[GoldEdit, ...]


@dataclass(frozen=True, slots=True)
class LanguageToolMatch:
    start: int
    end: int
    original: str
    replacements: tuple[str, ...]
    rule_id: str
    category: str


@dataclass(frozen=True, slots=True)
class CategoryCounts:
    category: str
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0


@dataclass(frozen=True, slots=True)
class CaseScore:
    case_id: str
    verification: str
    true_positives: int
    false_positives: int
    false_negatives: int
    top_output_exact: bool
    gold_reachable: bool
    negative_changed: bool
    skipped_conflicts: int
    match_count: int
    latency_ms: float
    category_counts: tuple[CategoryCounts, ...]


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    tool_version: str
    corpus_sha256: str
    startup_ms: float | None
    rss_kib: int | None
    runtime: RuntimeConfig
    scores: tuple[CaseScore, ...]


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    language: str
    timeout_seconds: float
    endpoint_policy: str
    runtime_command: str
    artifact: str
    artifact_sha256: str
    java_version: str


def utf16_offset_to_codepoint(text: str, offset: int) -> int:
    """Convert one Java UTF-16 code-unit boundary to a Python string offset."""

    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("UTF-16 offset must be a non-negative integer")
    units = 0
    for index, character in enumerate(text):
        if units == offset:
            return index
        width = 2 if ord(character) > 0xFFFF else 1
        if units < offset < units + width:
            raise ValueError("UTF-16 offset falls inside a surrogate pair")
        units += width
    if units == offset:
        return len(text)
    raise ValueError("UTF-16 offset is outside the source text")


def parse_response(
    source_text: str, payload: Mapping[str, object]
) -> tuple[LanguageToolMatch, ...]:
    """Validate and normalize one `/v2/check` response."""

    raw_matches = payload.get("matches")
    if not isinstance(raw_matches, list):
        raise ValueError("LanguageTool response must contain a matches list")
    normalized: list[LanguageToolMatch] = []
    for raw_match in raw_matches:
        if not isinstance(raw_match, dict):
            raise ValueError("LanguageTool match must be an object")
        offset = _integer(raw_match.get("offset"), "match offset")
        length = _integer(raw_match.get("length"), "match length")
        start = utf16_offset_to_codepoint(source_text, offset)
        end = utf16_offset_to_codepoint(source_text, offset + length)
        rule = raw_match.get("rule")
        if not isinstance(rule, dict):
            raise ValueError("LanguageTool match must contain rule metadata")
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise ValueError("LanguageTool rule id must be non-empty")
        replacements = _replacement_values(raw_match.get("replacements"))
        normalized.append(
            LanguageToolMatch(
                start=start,
                end=end,
                original=source_text[start:end],
                replacements=replacements,
                rule_id=rule_id,
                category=_map_category(rule),
            )
        )
    return tuple(normalized)


def load_cases(path: Path) -> tuple[BenchmarkCase, ...]:
    """Load every versioned E2E case and its explicit gold edits."""

    raw: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("cases"), list):
        raise ValueError("corpus must contain a cases list")
    cases: list[BenchmarkCase] = []
    for item in raw["cases"]:
        if not isinstance(item, dict):
            raise ValueError("corpus case must be an object")
        case_id = item.get("id")
        source = item.get("input")
        expected = item.get("expected_output")
        verification = item.get("verification")
        edits = item.get("expected_findings")
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("case id must be non-empty")
        if not isinstance(source, str) or not isinstance(expected, str):
            raise ValueError("case text fields must be strings")
        if verification not in _VERIFICATIONS:
            raise ValueError("case verification is invalid")
        if not isinstance(edits, list):
            raise ValueError("case expected_findings must be a list")
        expected_edits = tuple(_load_gold_edit(edit, source) for edit in edits)
        if verification == "negative" and expected_edits:
            raise ValueError("negative case must not contain gold edits")
        if verification != "negative" and not expected_edits:
            raise ValueError("positive case must contain gold edits")
        if _apply_gold(source, expected_edits) != expected:
            raise ValueError("gold edits must reconstruct expected output")
        cases.append(
            BenchmarkCase(
                case_id, source, expected, verification, expected_edits
            )
        )
    return tuple(cases)


def score_case(
    case: BenchmarkCase,
    matches: Sequence[LanguageToolMatch],
    *,
    latency_ms: float,
) -> CaseScore:
    """Score exact edits and deterministic top-replacement output."""

    used: set[int] = set()
    matched_gold: set[int] = set()
    category_totals: dict[str, list[int]] = {}
    for gold_index, gold in enumerate(case.expected_edits):
        prediction_index = next(
            (
                index
                for index, match in enumerate(matches)
                if index not in used
                and match.category == gold.category
                and match.start == gold.start
                and match.end == gold.end
                and match.original == gold.original
                and gold.suggestion in match.replacements
            ),
            None,
        )
        if prediction_index is None:
            _category_increment(category_totals, gold.category, 2)
            continue
        used.add(prediction_index)
        matched_gold.add(gold_index)
        _category_increment(category_totals, gold.category, 0)

    for index, match in enumerate(matches):
        if index not in used:
            _category_increment(category_totals, match.category, 1)

    top_output, skipped_conflicts = _top_replacement_output(case.source, matches)
    negative_changed = case.verification == "negative" and any(
        replacement != match.original
        for match in matches
        for replacement in match.replacements
    )
    return CaseScore(
        case_id=case.case_id,
        verification=case.verification,
        true_positives=len(used),
        false_positives=len(matches) - len(used),
        false_negatives=len(case.expected_edits) - len(matched_gold),
        top_output_exact=top_output == case.expected_output,
        gold_reachable=_gold_output_reachable(
            case.source, case.expected_output, matches
        ),
        negative_changed=negative_changed,
        skipped_conflicts=skipped_conflicts,
        match_count=len(matches),
        latency_ms=float(latency_ms),
        category_counts=tuple(
            CategoryCounts(category, *values)
            for category, values in sorted(category_totals.items())
        ),
    )


def summarize(
    scores: Sequence[CaseScore],
    *,
    tool_version: str,
    corpus_sha256: str,
    startup_ms: float | None,
    rss_kib: int | None,
    runtime: RuntimeConfig,
) -> BenchmarkReport:
    """Build a report with reproducibility metadata and no analyzed text."""

    if not scores:
        raise ValueError("benchmark report requires at least one score")
    if not tool_version:
        raise ValueError("tool version must be non-empty")
    _validate_sha256(corpus_sha256, "corpus SHA-256")
    if startup_ms is not None:
        _non_negative_finite(startup_ms, "startup_ms")
    if isinstance(rss_kib, bool) or (
        rss_kib is not None and (not isinstance(rss_kib, int) or rss_kib < 0)
    ):
        raise ValueError("rss_kib must be a non-negative integer or None")
    _non_negative_finite(runtime.timeout_seconds, "timeout_seconds")
    if runtime.timeout_seconds == 0:
        raise ValueError("timeout_seconds must be positive")
    if runtime.language != "pl-PL":
        raise ValueError("runtime language must be pl-PL")
    for label, value in (
        ("endpoint_policy", runtime.endpoint_policy),
        ("runtime_command", runtime.runtime_command),
        ("artifact", runtime.artifact),
        ("java_version", runtime.java_version),
    ):
        if not value.strip():
            raise ValueError(f"{label} must be non-empty")
    _validate_sha256(runtime.artifact_sha256, "artifact SHA-256")
    for score in scores:
        _non_negative_finite(score.latency_ms, "latency_ms")
    return BenchmarkReport(
        tool_version,
        corpus_sha256,
        startup_ms,
        rss_kib,
        runtime,
        tuple(scores),
    )


def report_as_json(report: BenchmarkReport) -> str:
    """Serialize a deterministic report that excludes source and response text."""

    latencies = sorted(score.latency_ms for score in report.scores)
    by_category: dict[str, list[int]] = {}
    by_verification: dict[str, list[int]] = {}
    for score in report.scores:
        verification = by_verification.setdefault(score.verification, [0, 0, 0])
        verification[0] += score.true_positives
        verification[1] += score.false_positives
        verification[2] += score.false_negatives
        for counts in score.category_counts:
            category = by_category.setdefault(counts.category, [0, 0, 0])
            category[0] += counts.true_positives
            category[1] += counts.false_positives
            category[2] += counts.false_negatives
    aggregate = [
        sum(score.true_positives for score in report.scores),
        sum(score.false_positives for score in report.scores),
        sum(score.false_negatives for score in report.scores),
    ]
    payload = {
        "cases": [
            {
                "case_id": score.case_id,
                "false_negatives": score.false_negatives,
                "false_positives": score.false_positives,
                "gold_reachable": score.gold_reachable,
                "latency_ms": score.latency_ms,
                "match_count": score.match_count,
                "negative_changed": score.negative_changed,
                "skipped_conflicts": score.skipped_conflicts,
                "top_output_exact": score.top_output_exact,
                "true_positives": score.true_positives,
                "verification": score.verification,
            }
            for score in report.scores
        ],
        "corpus": {"sha256": report.corpus_sha256},
        "scoring": {
            "category_mapping_version": _CATEGORY_MAPPING_VERSION,
            "offset_unit": "python_codepoint",
            "version": _SCORING_VERSION,
        },
        "runtime": {
            "artifact": report.runtime.artifact,
            "artifact_sha256": report.runtime.artifact_sha256,
            "endpoint_policy": report.runtime.endpoint_policy,
            "java_version": report.runtime.java_version,
            "language": report.runtime.language,
            "runtime_command": report.runtime.runtime_command,
            "timeout_seconds": report.runtime.timeout_seconds,
        },
        "summary": {
            "all": _metric_payload(aggregate),
            "by_category": {
                key: _metric_payload(value) for key, value in sorted(by_category.items())
            },
            "by_verification": {
                key: _metric_payload(value)
                for key, value in sorted(by_verification.items())
            },
            "exact_output_cases": sum(score.top_output_exact for score in report.scores),
            "gold_reachable_cases": sum(score.gold_reachable for score in report.scores),
            "latency_p50_ms": _nearest_rank(latencies, 0.50),
            "latency_p95_ms": _nearest_rank(latencies, 0.95),
            "negative_cases_changed": sum(
                score.negative_changed for score in report.scores
            ),
            "total_cases": len(report.scores),
        },
        "tool": {
            "local_only": True,
            "name": "LanguageTool",
            "rss_kib": report.rss_kib,
            "startup_ms": report.startup_ms,
            "version": report.tool_version,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def corpus_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_gold_edit(raw: object, source: str) -> GoldEdit:
    if not isinstance(raw, dict):
        raise ValueError("gold edit must be an object")
    category = raw.get("category")
    start = _integer(raw.get("start"), "gold start")
    end = _integer(raw.get("end"), "gold end")
    original = raw.get("original")
    suggestion = raw.get("suggestion")
    if not isinstance(category, str) or not category:
        raise ValueError("gold category must be non-empty")
    if not isinstance(original, str) or not isinstance(suggestion, str):
        raise ValueError("gold edit text fields must be strings")
    if end < start or end > len(source) or source[start:end] != original:
        raise ValueError("gold edit span must match source text")
    return GoldEdit(category, start, end, original, suggestion)


def _replacement_values(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, list):
        raise ValueError("LanguageTool replacements must be a list")
    values: list[str] = []
    for replacement in raw:
        if not isinstance(replacement, dict) or not isinstance(
            replacement.get("value"), str
        ):
            raise ValueError("LanguageTool replacement must contain a string value")
        value = replacement["value"]
        if value not in values:
            values.append(value)
    return tuple(values)


def _map_category(rule: Mapping[str, object]) -> str:
    issue_type = rule.get("issueType")
    raw_category = rule.get("category")
    category_id = raw_category.get("id") if isinstance(raw_category, dict) else None
    issue = issue_type.upper() if isinstance(issue_type, str) else ""
    category = category_id.upper() if isinstance(category_id, str) else ""
    if issue == "MISSPELLING" or category in {"TYPOS", "CASING", "COMPOUNDING"}:
        return "spelling"
    if issue == "PUNCTUATION" or category == "PUNCTUATION":
        return "punctuation"
    if category in {"GRAMMAR", "SYNTAX", "WORD_ORDER"}:
        return "syntax"
    if issue in {"STYLE", "REGISTER"} or category == "STYLE":
        return "style"
    return "unmapped"


def _top_replacement_output(
    source: str, matches: Sequence[LanguageToolMatch]
) -> tuple[str, int]:
    accepted: list[tuple[int, int, str]] = []
    skipped = 0
    for match in sorted(matches, key=lambda item: (item.start, item.end, item.rule_id)):
        replacement = next(
            (value for value in match.replacements if value != match.original), None
        )
        if replacement is None:
            continue
        if any(_conflicts(match.start, match.end, start, end) for start, end, _ in accepted):
            skipped += 1
            continue
        accepted.append((match.start, match.end, replacement))
    output = source
    for start, end, replacement in sorted(accepted, reverse=True):
        output = output[:start] + replacement + output[end:]
    return output, skipped


def _conflicts(start: int, end: int, other_start: int, other_end: int) -> bool:
    if start == end and other_start == other_end:
        return start == other_start
    if start == end:
        return other_start <= start <= other_end
    if other_start == other_end:
        return start <= other_start <= end
    return start < other_end and other_start < end


def _apply_gold(source: str, edits: Sequence[GoldEdit]) -> str:
    output = source
    for edit in sorted(edits, key=lambda item: (item.start, item.end), reverse=True):
        output = output[: edit.start] + edit.suggestion + output[edit.end :]
    return output


def _gold_output_reachable(
    source: str, expected: str, matches: Sequence[LanguageToolMatch]
) -> bool:
    ordered = sorted(matches, key=lambda item: (item.start, item.end, item.rule_id))

    def visit(
        index: int,
        cursor: int,
        prefix: str,
        accepted: tuple[tuple[int, int], ...],
    ) -> bool:
        if index == len(ordered):
            return prefix + source[cursor:] == expected
        match = ordered[index]
        if visit(index + 1, cursor, prefix, accepted):
            return True
        if match.start < cursor or any(
            _conflicts(match.start, match.end, start, end)
            for start, end in accepted
        ):
            return False
        unchanged = source[cursor : match.start]
        return any(
            visit(
                index + 1,
                match.end,
                prefix + unchanged + replacement,
                (*accepted, (match.start, match.end)),
            )
            for replacement in match.replacements
        )

    return visit(0, 0, "", ())


def _category_increment(
    totals: dict[str, list[int]], category: str, index: int
) -> None:
    totals.setdefault(category, [0, 0, 0])[index] += 1


def _metric_payload(values: Sequence[int]) -> dict[str, float | int]:
    true_positives, false_positives, false_negatives = values
    precision = _ratio(true_positives, true_positives + false_positives)
    recall = _ratio(true_positives, true_positives + false_negatives)
    f1 = _ratio(2 * precision * recall, precision + recall)
    return {
        "f1": f1,
        "false_negatives": false_negatives,
        "false_positives": false_positives,
        "precision": precision,
        "recall": recall,
        "true_positives": true_positives,
    }


def _nearest_rank(values: Sequence[float], quantile: float) -> float:
    index = max(math.ceil(quantile * len(values)) - 1, 0)
    return values[index]


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _validate_sha256(value: str, label: str) -> None:
    if re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{label} must contain 64 lowercase hexadecimal characters")


def _non_negative_finite(value: float, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be finite and non-negative")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and non-negative")


__all__ = [
    "BenchmarkCase",
    "BenchmarkReport",
    "CaseScore",
    "CategoryCounts",
    "GoldEdit",
    "LanguageToolMatch",
    "RuntimeConfig",
    "corpus_sha256",
    "load_cases",
    "parse_response",
    "report_as_json",
    "score_case",
    "summarize",
    "utf16_offset_to_codepoint",
]
