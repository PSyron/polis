"""Quality baseline utilities for deterministic evaluation runs."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from polis.core import Category, Finding
from polis.core.models import SourceKind
from polis.evaluation.dataset import DATASET_PATH, EvaluationDataset, ExpectedFinding

DEFAULT_DATASET_PATH: Final[Path] = DATASET_PATH


@dataclass(frozen=True, slots=True)
class QualityCounts:
    """Counting state for one metric group."""

    expected_findings: int = 0
    predicted_findings: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    span_matches: int = 0
    correction_matches: int = 0

    @property
    def precision(self) -> float:
        return _safe_ratio(
            self.true_positives, self.true_positives + self.false_positives
        )

    @property
    def recall(self) -> float:
        return _safe_ratio(
            self.true_positives, self.true_positives + self.false_negatives
        )

    @property
    def f1(self) -> float:
        precision = self.precision
        recall = self.recall
        denominator = precision + recall
        if denominator == 0:
            return 0.0
        return 2 * precision * recall / denominator

    @property
    def span_accuracy(self) -> float:
        return _safe_ratio(self.span_matches, self.expected_findings)

    @property
    def correction_accuracy(self) -> float:
        return _safe_ratio(self.correction_matches, self.span_matches)

    @property
    def false_positive_rate(self) -> float:
        return _safe_ratio(self.false_positives, self.predicted_findings)

    def plus(self, other: QualityCounts) -> QualityCounts:
        return QualityCounts(
            expected_findings=self.expected_findings + other.expected_findings,
            predicted_findings=self.predicted_findings + other.predicted_findings,
            true_positives=self.true_positives + other.true_positives,
            false_positives=self.false_positives + other.false_positives,
            false_negatives=self.false_negatives + other.false_negatives,
            span_matches=self.span_matches + other.span_matches,
            correction_matches=self.correction_matches + other.correction_matches,
        )


@dataclass(frozen=True, slots=True)
class BaselineResult:
    """Structured result for one reproducible baseline run."""

    run_label: str
    run_reference: str
    configuration: str
    dataset_id: str
    dataset_schema_version: int
    dataset_cases: int
    dataset_path: str
    dataset_hash: str
    incorrect_case_count: int
    correct_case_count: int
    aggregate: QualityCounts
    by_category: Mapping[Category, QualityCounts]
    by_source: Mapping[SourceKind, QualityCounts]


def evaluate_baseline(
    *,
    dataset: EvaluationDataset,
    analyzer: Callable[[str], tuple[Finding, ...]],
    run_label: str,
    run_reference: str,
    configuration: str,
) -> BaselineResult:
    """Run the provided analyzer on the dataset and return a deterministic snapshot."""

    aggregate = QualityCounts()
    by_category = {category: QualityCounts() for category in Category}
    by_source = {kind: QualityCounts() for kind in SourceKind}

    incorrect_case_count = 0
    correct_case_count = 0

    for case in dataset.cases:
        findings = tuple(analyzer(case.text))
        if case.outcome == "correct":
            correct_case_count += 1
        else:
            incorrect_case_count += 1

        aggregate = aggregate.plus(_score_case(case.findings, findings))

        for category in by_category:
            expected_for_category = tuple(
                item for item in case.findings if Category(item.category) == category
            )
            findings_for_category = tuple(
                item for item in findings if item.category == category
            )
            by_category[category] = by_category[category].plus(
                _score_case(expected_for_category, findings_for_category)
            )

        for source in by_source:
            findings_for_source = tuple(
                item for item in findings if item.source.kind == source
            )
            by_source[source] = by_source[source].plus(
                _score_case(case.findings, findings_for_source)
            )

    return BaselineResult(
        run_label=run_label,
        run_reference=run_reference,
        configuration=configuration,
        dataset_id=dataset.id,
        dataset_schema_version=dataset.schema_version,
        dataset_cases=len(dataset.cases),
        dataset_path=str(DEFAULT_DATASET_PATH),
        dataset_hash=_dataset_hash(DEFAULT_DATASET_PATH),
        incorrect_case_count=incorrect_case_count,
        correct_case_count=correct_case_count,
        aggregate=aggregate,
        by_category=by_category,
        by_source=by_source,
    )


def findings_snapshot_for_run(dataset_path: Path = DEFAULT_DATASET_PATH) -> str:
    """Return the SHA-256 hash identifying one concrete dataset revision."""

    return hashlib.sha256(dataset_path.read_bytes()).hexdigest()


def _score_case(
    expected: tuple[ExpectedFinding, ...],
    findings: tuple[Finding, ...],
) -> QualityCounts:
    expected_items = list(expected)
    counts = QualityCounts(expected_findings=len(expected_items))

    if not expected_items:
        return counts.plus(
            QualityCounts(
                predicted_findings=len(findings), false_positives=len(findings)
            )
        )

    used = [False] * len(expected_items)
    for predicted in findings:
        counts = counts.plus(QualityCounts(predicted_findings=1))
        exact_match = _find_exact_match(predicted, expected_items, used)
        if exact_match is not None:
            counts = counts.plus(
                QualityCounts(
                    true_positives=1,
                    span_matches=1,
                    correction_matches=1,
                )
            )
            used[exact_match] = True
            continue

        span_match = _find_span_match(predicted, expected_items, used)
        if span_match is not None:
            counts = counts.plus(QualityCounts(span_matches=1, false_positives=1))
            used[span_match] = True
            continue

        counts = counts.plus(QualityCounts(false_positives=1))

    false_negatives = sum(1 for found in used if not found)
    return counts.plus(QualityCounts(false_negatives=false_negatives))


def _find_exact_match(
    finding: Finding,
    expected: list[ExpectedFinding],
    used: list[bool],
) -> int | None:
    for index, reference in enumerate(expected):
        if used[index]:
            continue
        if (
            finding.start == reference.start
            and finding.end == reference.end
            and finding.category.value == reference.category
            and finding.original == reference.original
            and finding.suggestion == reference.suggestion
        ):
            return index
    return None


def _find_span_match(
    finding: Finding,
    expected: list[ExpectedFinding],
    used: list[bool],
) -> int | None:
    for index, reference in enumerate(expected):
        if used[index]:
            continue
        if (
            finding.start == reference.start
            and finding.end == reference.end
            and finding.category.value == reference.category
        ):
            return index
    return None


def _dataset_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        if numerator == 0:
            return 1.0
        return 0.0
    return numerator / denominator


__all__ = [
    "QualityCounts",
    "BaselineResult",
    "evaluate_baseline",
    "findings_snapshot_for_run",
    "DEFAULT_DATASET_PATH",
]
