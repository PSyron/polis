"""Quality baseline utilities for deterministic evaluation runs."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from polis.core import Category, Finding
from polis.core.models import SourceKind
from polis.evaluation.dataset import (
    DATASET_PATH,
    EvaluationDataset,
    ExpectedFinding,
    load_dataset,
)

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
    correct_cases: int = 0
    alarmed_correct_cases: int = 0

    @property
    def exact_edit_precision(self) -> float | None:
        """Return exact-edit TP / (TP + FP), or ``None`` with no predictions."""

        return _ratio_or_none(
            self.true_positives, self.true_positives + self.false_positives
        )

    @property
    def exact_edit_recall(self) -> float | None:
        """Return exact-edit TP / (TP + FN), or ``None`` with no gold edits."""

        return _ratio_or_none(
            self.true_positives, self.true_positives + self.false_negatives
        )

    @property
    def exact_edit_f1(self) -> float | None:
        """Return 2TP / (2TP + FP + FN), or ``None`` without scored edits."""

        return _ratio_or_none(
            2 * self.true_positives,
            2 * self.true_positives + self.false_positives + self.false_negatives,
        )

    @property
    def span_accuracy(self) -> float | None:
        """Return matched gold spans / gold edits, or ``None`` without gold edits."""

        return _ratio_or_none(self.span_matches, self.expected_findings)

    @property
    def correction_accuracy(self) -> float | None:
        """Return exact corrections / matched spans, or ``None`` without a span."""

        return _ratio_or_none(self.correction_matches, self.span_matches)

    @property
    def false_discovery_proportion(self) -> float | None:
        """Return false discoveries / predictions, or ``None`` without predictions."""

        return _ratio_or_none(self.false_positives, self.predicted_findings)

    @property
    def correct_sentence_false_alarm_rate(self) -> float | None:
        """Return alarmed correct cases / correct cases, or ``None`` without them."""

        return _ratio_or_none(self.alarmed_correct_cases, self.correct_cases)

    def plus(self, other: QualityCounts) -> QualityCounts:
        return QualityCounts(
            expected_findings=self.expected_findings + other.expected_findings,
            predicted_findings=self.predicted_findings + other.predicted_findings,
            true_positives=self.true_positives + other.true_positives,
            false_positives=self.false_positives + other.false_positives,
            false_negatives=self.false_negatives + other.false_negatives,
            span_matches=self.span_matches + other.span_matches,
            correction_matches=self.correction_matches + other.correction_matches,
            correct_cases=self.correct_cases + other.correct_cases,
            alarmed_correct_cases=(
                self.alarmed_correct_cases + other.alarmed_correct_cases
            ),
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
    dataset_source: str
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

        correct_case = case.outcome == "correct"
        aggregate = aggregate.plus(
            _score_case(case.findings, findings, correct_case=correct_case)
        )

        for category in by_category:
            expected_for_category = tuple(
                item for item in case.findings if Category(item.category) == category
            )
            findings_for_category = tuple(
                item for item in findings if item.category == category
            )
            by_category[category] = by_category[category].plus(
                _score_case(
                    expected_for_category,
                    findings_for_category,
                    correct_case=correct_case,
                )
            )

        for source in by_source:
            findings_for_source = tuple(
                item for item in findings if item.source.kind == source
            )
            by_source[source] = by_source[source].plus(
                _score_case(
                    case.findings,
                    findings_for_source,
                    correct_case=correct_case,
                )
            )

    return BaselineResult(
        run_label=run_label,
        run_reference=run_reference,
        configuration=configuration,
        dataset_id=dataset.id,
        dataset_schema_version=dataset.schema_version,
        dataset_cases=len(dataset.cases),
        dataset_source=dataset.source,
        dataset_hash=dataset.canonical_hash,
        incorrect_case_count=incorrect_case_count,
        correct_case_count=correct_case_count,
        aggregate=aggregate,
        by_category=by_category,
        by_source=by_source,
    )


def findings_snapshot_for_run(dataset_path: Path = DEFAULT_DATASET_PATH) -> str:
    """Return the SHA-256 hash identifying one concrete dataset revision."""

    return cast("str", load_dataset(dataset_path).canonical_hash)


def _score_case(
    expected: tuple[ExpectedFinding, ...],
    findings: tuple[Finding, ...],
    *,
    correct_case: bool,
) -> QualityCounts:
    expected_items = list(expected)
    counts = QualityCounts(
        expected_findings=len(expected_items),
        predicted_findings=len(findings),
        correct_cases=int(correct_case),
        alarmed_correct_cases=int(correct_case and bool(findings)),
    )

    exact_used = [False] * len(expected_items)
    exact_predictions = [False] * len(findings)
    for prediction_index, predicted in enumerate(findings):
        exact_match = _find_exact_match(predicted, expected_items, exact_used)
        if exact_match is not None:
            counts = counts.plus(QualityCounts(true_positives=1))
            exact_used[exact_match] = True
            exact_predictions[prediction_index] = True

    span_used = [False] * len(expected_items)
    span_matches = 0
    for predicted in findings:
        span_match = _find_span_match(predicted, expected_items, span_used)
        if span_match is not None:
            span_matches += 1
            span_used[span_match] = True

    return counts.plus(
        QualityCounts(
            false_positives=sum(1 for matched in exact_predictions if not matched),
            false_negatives=sum(1 for matched in exact_used if not matched),
            span_matches=span_matches,
            correction_matches=counts.true_positives,
        )
    )


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


def _ratio_or_none(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


__all__ = [
    "QualityCounts",
    "BaselineResult",
    "evaluate_baseline",
    "findings_snapshot_for_run",
    "DEFAULT_DATASET_PATH",
]
