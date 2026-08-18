"""Measurement and scoring primitives for the reviewed quality-development v4 set."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, fields
from typing import Final, cast

from polis.core import Finding
from polis.evaluation._quality_types import QualityCase, QualityCaseKind
from polis.evaluation.metrics import QualityCounts
from polis.evaluation.quality_dataset import QualityDataset
from polis.evaluation.quality_protocol import (
    LatencyMetrics,
    ResourceMetrics,
    RunIdentity,
    ThroughputMetrics,
    peak_rss_bytes,
)

_CATEGORIES: Final = ("agreement", "inflection", "punctuation", "spelling", "syntax")
_SHAPES: Final = (
    "simple-local",
    "sentence-internal",
    "multi-sentence",
    "repeated-occurrence",
    "unicode-and-case",
    "quotation-or-literal",
    "conflict-or-abstention",
)


@dataclass(frozen=True, slots=True)
class V4Measurement:
    """One deterministic v4 measurement, including public diagnostics."""

    run_identity: RunIdentity
    dataset: QualityDataset
    warmup_repetitions: int
    measured_repetitions: int
    repetition_hashes: tuple[str, ...]
    findings_by_case: tuple[tuple[Finding, ...], ...]
    aggregate: QualityCounts
    categories: dict[str, QualityCounts]
    strata: dict[str, dict[str, QualityCounts]]
    category_cases: dict[str, dict[str, int]]
    stratum_cases: dict[str, dict[str, dict[str, int]]]
    controls: dict[str, dict[str, object]]
    sources: tuple[dict[str, object], ...]
    latency: LatencyMetrics
    throughput: ThroughputMetrics
    resources: ResourceMetrics
    v4_diagnostics: dict[str, object]


def measure_v4(
    *,
    dataset: QualityDataset,
    analyzer: Callable[[str], Iterable[Finding]],
    run_identity: RunIdentity,
    warmup_repetitions: int,
    measured_repetitions: int,
) -> V4Measurement:
    """Warm, measure, and score v4 without retaining case text in the result."""

    if warmup_repetitions < 0 or measured_repetitions < 2:
        raise ValueError("invalid quality repetition counts")
    for _ in range(warmup_repetitions):
        for case in dataset.cases:
            tuple(analyzer(case.text))

    durations: list[int] = []
    repetition_hashes: list[str] = []
    first: tuple[tuple[Finding, ...], ...] | None = None
    import time

    for _repetition in range(measured_repetitions):
        current: list[tuple[Finding, ...]] = []
        for case in dataset.cases:
            started = time.perf_counter_ns()
            findings = tuple(analyzer(case.text))
            durations.append(time.perf_counter_ns() - started)
            current.append(findings)
        snapshot = tuple(current)
        digest = findings_snapshot_sha256(dataset, snapshot)
        repetition_hashes.append(digest)
        if first is None:
            first = snapshot
        elif digest != repetition_hashes[0]:
            raise ValueError("v4 findings changed between measured repetitions")

    assert first is not None
    diagnostics = score_v4(dataset, first, run_identity.profile.id, run_identity)
    total = sum(durations)
    measured_cases = len(dataset.cases) * measured_repetitions
    code_points = sum(len(case.text) for case in dataset.cases) * measured_repetitions
    ordered = sorted(durations)
    return V4Measurement(
        run_identity=run_identity,
        dataset=dataset,
        warmup_repetitions=warmup_repetitions,
        measured_repetitions=measured_repetitions,
        repetition_hashes=tuple(repetition_hashes),
        findings_by_case=first,
        aggregate=diagnostics.aggregate,
        categories=diagnostics.categories,
        strata=diagnostics.strata,
        category_cases=diagnostics.category_cases,
        stratum_cases=diagnostics.stratum_cases,
        controls=diagnostics.controls,
        sources=diagnostics.sources,
        latency=LatencyMetrics(
            sample_count=len(ordered),
            min_ns=ordered[0],
            mean_ns=total // len(ordered),
            p50_ns=ordered[(50 * len(ordered) + 99) // 100 - 1],
            p95_ns=ordered[(95 * len(ordered) + 99) // 100 - 1],
            max_ns=ordered[-1],
        ),
        throughput=ThroughputMetrics(
            measured_cases=measured_cases,
            measured_code_points=code_points,
            total_duration_ns=total,
            cases_per_second=measured_cases * 1_000_000_000 / total,
            code_points_per_second=code_points * 1_000_000_000 / total,
        ),
        resources=ResourceMetrics(peak_rss_bytes=peak_rss_bytes()),
        v4_diagnostics={
            "aggregate": counts_payload(diagnostics.aggregate),
            "category": {
                name: counts_payload(value)
                for name, value in diagnostics.categories.items()
            },
            "shape_strata": {
                category: {
                    shape: counts_payload(value) for shape, value in values.items()
                }
                for category, values in diagnostics.strata.items()
            },
            "category_cases": diagnostics.category_cases,
            "stratum_cases": diagnostics.stratum_cases,
            "source": list(diagnostics.sources),
            "controls": diagnostics.controls,
        },
    )


@dataclass(frozen=True, slots=True)
class _Diagnostics:
    aggregate: QualityCounts
    categories: dict[str, QualityCounts]
    strata: dict[str, dict[str, QualityCounts]]
    category_cases: dict[str, dict[str, int]]
    stratum_cases: dict[str, dict[str, dict[str, int]]]
    controls: dict[str, dict[str, object]]
    sources: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class _CaseScore:
    counts: QualityCounts
    exact_prediction_indices: frozenset[int]


def score_v4(
    dataset: QualityDataset,
    findings_by_case: tuple[tuple[Finding, ...], ...],
    profile_id: str,
    run_identity: RunIdentity,
) -> _Diagnostics:
    """Score exact edits while keeping conflict and abstention denominators out."""

    if len(findings_by_case) != len(dataset.cases):
        raise ValueError("v4 findings count does not match dataset cases")
    if profile_id not in {"default", "morphology"}:
        raise ValueError("unsupported v4 profile")

    category_scores = {category: QualityCounts() for category in _CATEGORIES}
    category_cases = {
        category: {"cases": 0, "eligible_cases": 0, "excluded_cases": 0}
        for category in _CATEGORIES
    }
    strata = {
        category: {shape: QualityCounts() for shape in _SHAPES}
        for category in _CATEGORIES
    }
    stratum_cases = {
        category: {
            shape: {"cases": 0, "eligible_cases": 0, "excluded_cases": 0}
            for shape in _SHAPES
        }
        for category in _CATEGORIES
    }
    conflict_ids: list[str] = []
    conflict_violations: list[str] = []
    abstention_ids: list[str] = []
    abstention_violations: list[str] = []
    source_accumulators: dict[str, dict[str, object]] = {}

    for case, findings in zip(dataset.cases, findings_by_case, strict=True):
        if case.kind is QualityCaseKind.CONFLICT:
            conflict_ids.append(case.id)
            if case.source_identity is not None:
                _source_case(
                    source_accumulators, case.source_identity, case.id, "control"
                )
            if findings:
                conflict_violations.append(case.id)
            continue
        provider_abstention = _is_provider_abstention(case, profile_id)
        if case.kind is QualityCaseKind.ABSTAIN or provider_abstention:
            if case.category in _CATEGORIES:
                category_cases[case.category]["cases"] += 1
                category_cases[case.category]["excluded_cases"] += 1
                for shape in case.shape_strata:
                    stratum_cases[case.category][shape]["cases"] += 1
                    stratum_cases[case.category][shape]["excluded_cases"] += 1
            abstention_ids.append(case.id)
            if case.source_identity is not None:
                _source_case(
                    source_accumulators,
                    case.source_identity,
                    case.id,
                    "abstained" if provider_abstention else "control",
                )
            if findings:
                abstention_violations.append(case.id)
            continue
        if case.category not in _CATEGORIES:
            raise ValueError("v4 determinate case has no supported category")

        category = case.category
        category_cases[category]["cases"] += 1
        category_cases[category]["eligible_cases"] += 1
        category_score = _score_case(case, findings)
        category_scores[category] = category_scores[category].plus(
            category_score.counts
        )
        for shape in case.shape_strata:
            stratum_cases[category][shape]["cases"] += 1
            stratum_cases[category][shape]["eligible_cases"] += 1
            strata[category][shape] = strata[category][shape].plus(
                category_score.counts
            )

        if case.source_identity is not None:
            _source_case(source_accumulators, case.source_identity, case.id, "measured")
            accumulator = source_accumulators[case.source_identity]
            accumulator["expected"] = cast(int, accumulator.get("expected", 0)) + len(
                case.findings
            )
            exact_indices = category_score.exact_prediction_indices
            for index, finding in enumerate(findings):
                source = str(finding.source)
                _source_case(source_accumulators, source, case.id, "measured")
                source_accumulator = source_accumulators[source]
                source_accumulator["predicted"] = (
                    cast(int, source_accumulator.get("predicted", 0)) + 1
                )
                if index in exact_indices:
                    source_accumulator["exact"] = (
                        cast(int, source_accumulator.get("exact", 0)) + 1
                    )
                else:
                    source_accumulator["false_positive"] = (
                        cast(int, source_accumulator.get("false_positive", 0)) + 1
                    )

    aggregate = QualityCounts()
    for category in _CATEGORIES:
        aggregate = aggregate.plus(category_scores[category])

    # Required shape strata must exist even when a future dataset is malformed;
    # the validator reports the missing/empty denominator instead of treating it
    # as a zero-quality pass.
    source_rows = _source_rows(dataset, source_accumulators, profile_id, run_identity)
    return _Diagnostics(
        aggregate=aggregate,
        categories=category_scores,
        strata=strata,
        category_cases=category_cases,
        stratum_cases=stratum_cases,
        controls={
            "conflict": {
                "case_count": len(conflict_ids),
                "case_ids": conflict_ids,
                "predicted_findings": sum(
                    len(findings_by_case[index])
                    for index, case in enumerate(dataset.cases)
                    if case.kind is QualityCaseKind.CONFLICT
                ),
                "violations": len(conflict_violations),
                "violation_case_ids": conflict_violations,
            },
            "abstention": {
                "case_count": len(abstention_ids),
                "case_ids": abstention_ids,
                "violations": len(abstention_violations),
                "violation_case_ids": abstention_violations,
            },
        },
        sources=source_rows,
    )


def findings_snapshot_sha256(
    dataset: QualityDataset,
    findings_by_case: tuple[tuple[Finding, ...], ...],
) -> str:
    snapshot = [
        {
            "case_id": case.id,
            "findings": [
                {
                    "id": finding.id,
                    "source": str(finding.source),
                    "start": finding.start,
                    "end": finding.end,
                    "category": finding.category.value,
                    "suggestion": finding.suggestion,
                }
                for finding in findings
            ],
        }
        for case, findings in zip(dataset.cases, findings_by_case, strict=True)
    ]
    encoded = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_snapshot_sha256(snapshot: tuple[object, ...]) -> str:
    encoded = json.dumps(
        snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def counts_payload(counts: QualityCounts) -> dict[str, object]:
    """Serialize all count fields and their contract-defined derived metrics."""

    values = {field.name: getattr(counts, field.name) for field in fields(counts)}
    values.update(
        {
            "exact_edit_precision": counts.exact_edit_precision,
            "exact_edit_recall": counts.exact_edit_recall,
            "exact_edit_f1": counts.exact_edit_f1,
            "span_accuracy": counts.span_accuracy,
            "suggestion_accuracy": counts.correction_accuracy,
            "false_discovery_proportion": counts.false_discovery_proportion,
            "correct_sentence_false_alarm_rate": (
                counts.correct_sentence_false_alarm_rate
            ),
        }
    )
    return values


def _score_case(case: QualityCase, findings: tuple[Finding, ...]) -> _CaseScore:
    expected = case.findings
    used = [False] * len(expected)
    exact: set[int] = set()
    for index, finding in enumerate(findings):
        for expected_index, reference in enumerate(expected):
            if used[expected_index]:
                continue
            if (
                finding.category.value == reference.category
                and finding.start == reference.start
                and finding.end == reference.end
                and finding.original == reference.original
                and finding.suggestion == reference.suggestion
            ):
                used[expected_index] = True
                exact.add(index)
                break
    span_used = [False] * len(expected)
    span_matches = 0
    for finding in findings:
        for expected_index, reference in enumerate(expected):
            if span_used[expected_index]:
                continue
            if (
                finding.category.value == reference.category
                and finding.start == reference.start
                and finding.end == reference.end
            ):
                span_used[expected_index] = True
                span_matches += 1
                break
    counts = QualityCounts(
        expected_findings=len(expected),
        predicted_findings=len(findings),
        true_positives=len(exact),
        false_positives=len(findings) - len(exact),
        false_negatives=len(expected) - len(exact),
        span_matches=span_matches,
        correction_matches=len(exact),
        correct_cases=int(case.kind is QualityCaseKind.CORRECT),
        alarmed_correct_cases=int(
            case.kind is QualityCaseKind.CORRECT and bool(findings)
        ),
    )
    return _CaseScore(counts, frozenset(exact))


def _is_provider_abstention(case: QualityCase, profile_id: str) -> bool:
    return (
        case.provider_requirement == "qualified_morphology" and profile_id == "default"
    )


def _source_category(source: str) -> str | None:
    if source.startswith("rule:agreement."):
        return "agreement"
    if source.startswith("rule:inflection."):
        return "inflection"
    if source.startswith("rule:spelling."):
        return "spelling"
    if source == "rule:punctuation.abbreviation_dot" or source in {
        "rule:syntax.comma_space",
        "rule:syntax.duplicate_comma",
        "rule:syntax.quote_space",
        "rule:syntax.sentence_space",
    }:
        return "punctuation"
    if source.startswith("rule:syntax."):
        return "syntax"
    return None


def _source_case(
    accumulators: dict[str, dict[str, object]],
    source: str,
    case_id: str,
    status: str,
) -> None:
    accumulator = accumulators.setdefault(source, {"case_ids": []})
    case_ids = cast(list[str], accumulator["case_ids"])
    if case_id not in case_ids:
        case_ids.append(case_id)
    previous = accumulator.get("status")
    if previous is None or previous == "unmeasured":
        accumulator["status"] = status
    elif previous != status and status == "measured":
        accumulator["status"] = "measured"


def _source_rows(
    dataset: QualityDataset,
    accumulators: dict[str, dict[str, object]],
    profile_id: str,
    run_identity: RunIdentity,
) -> tuple[dict[str, object], ...]:
    del dataset, profile_id
    snapshot = run_identity.source_snapshot
    if snapshot is None:
        raise ValueError("v4 source snapshot is required")
    rows: list[dict[str, object]] = []
    expected_sources = tuple(item["source"] for item in snapshot)
    if len(expected_sources) != 59 or len(set(expected_sources)) != 59:
        raise ValueError("v4 source snapshot must contain 59 unique ordered sources")
    for identity in snapshot:
        source = identity["source"]
        value = accumulators.get(source, {})
        case_ids = list(dict.fromkeys(cast(list[str], value.get("case_ids", []))))
        expected = cast(int, value.get("expected", 0))
        exact = cast(int, value.get("exact", 0))
        rows.append(
            {
                "source": source,
                "category": _source_category(source),
                "status": str(value.get("status", "unmeasured")),
                "operation": identity["operation"],
                "behavior_version": identity["behavior_version"],
                "profile": str(run_identity.profile.id)
                if run_identity.profile
                else None,
                "predicted_count": cast(int, value.get("predicted", 0)),
                "expected_count": expected,
                "exact_match_count": exact,
                "false_positive_count": cast(int, value.get("false_positive", 0)),
                "false_negative_count": max(0, expected - exact),
                "case_ids": case_ids,
            }
        )
    return tuple(rows)


__all__ = [
    "V4Measurement",
    "counts_payload",
    "findings_snapshot_sha256",
    "measure_v4",
    "score_v4",
    "source_snapshot_sha256",
]
