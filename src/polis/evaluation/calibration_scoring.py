from __future__ import annotations

from collections.abc import Mapping

from polis.core import Category, Finding, Source
from polis.evaluation.calibration_models import (
    CalibrationCase,
    CalibrationConfig,
    CalibrationCounts,
    CalibrationDataset,
    CalibrationMetrics,
    CalibrationSourceIdentity,
    ExpectedFinding,
    KeyOutcome,
    KeyVerdict,
)


def _exact(prediction: Finding, expected: ExpectedFinding) -> bool:
    return bool(
        prediction.source == Source.parse(expected.source)
        and prediction.category == Category(expected.category)
        and prediction.start == expected.start
        and prediction.end == expected.end
        and prediction.original == expected.original
        and prediction.suggestion == expected.suggestion
    )


def _span(prediction: Finding, expected: ExpectedFinding) -> bool:
    return bool(
        prediction.source == Source.parse(expected.source)
        and prediction.category == Category(expected.category)
        and prediction.start == expected.start
        and prediction.end == expected.end
        and prediction.original == expected.original
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _metrics(counts: CalibrationCounts) -> CalibrationMetrics:
    precision = _ratio(
        counts.true_positive,
        counts.true_positive + counts.false_positive,
    )
    recall = _ratio(
        counts.true_positive,
        counts.true_positive + counts.false_negative,
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall > 0
        else None
    )
    gold_count = counts.true_positive + counts.false_negative
    return CalibrationMetrics(
        precision,
        recall,
        f1,
        _ratio(counts.exact_span_matches, gold_count),
        _ratio(counts.exact_correction_matches, counts.exact_span_matches),
        _ratio(counts.correct_sentence_false_alarms, counts.correct_cases),
    )


def _case_counts(
    case: CalibrationCase,
    identity: CalibrationSourceIdentity,
    predictions: tuple[Finding, ...],
) -> tuple[int, int, int, int, int, int]:
    expected = tuple(
        item for item in case.expected_findings if item.source == identity.source
    )
    source_predictions = tuple(
        item for item in predictions if str(item.source) == identity.source
    )
    unmatched = set(range(len(expected)))
    matched = 0
    for prediction in source_predictions:
        match_index = next(
            (index for index in unmatched if _exact(prediction, expected[index])),
            None,
        )
        if match_index is not None:
            unmatched.remove(match_index)
            matched += 1
    span_matches = sum(
        any(_span(prediction, item) for prediction in source_predictions)
        for item in expected
    )
    correction_matches = sum(
        any(_exact(prediction, item) for prediction in source_predictions)
        for item in expected
    )
    false_alarms = len(source_predictions) if case.role == "correct" else 0
    return (
        matched,
        len(source_predictions) - matched,
        len(expected) - matched,
        span_matches,
        correction_matches,
        false_alarms,
    )


def _verdict(
    identity: CalibrationSourceIdentity,
    counts: CalibrationCounts,
    metrics: CalibrationMetrics,
    confidences: set[float],
    config: CalibrationConfig,
) -> tuple[float | None, KeyVerdict]:
    observed = next(iter(confidences)) if len(confidences) == 1 else None
    complete = (
        counts.error_cases >= config.minimum_error_cases_per_key
        and counts.correct_cases >= config.minimum_correct_cases_per_key
    )
    if not complete or observed is None or observed != identity.emitted_confidence:
        return observed, "insufficient_evidence"
    thresholds = config.thresholds
    passed = (
        metrics.precision is not None
        and metrics.precision >= thresholds.precision
        and metrics.recall is not None
        and metrics.recall >= thresholds.recall
        and metrics.f1 is not None
        and metrics.f1 >= thresholds.f1
        and metrics.exact_span_accuracy is not None
        and metrics.exact_span_accuracy >= thresholds.exact_span_accuracy
        and metrics.exact_correction_accuracy is not None
        and metrics.exact_correction_accuracy >= thresholds.exact_correction_accuracy
        and metrics.correct_sentence_false_alarm_rate is not None
        and metrics.correct_sentence_false_alarm_rate
        <= thresholds.correct_sentence_false_alarm_rate
    )
    return observed, "candidate" if passed else "fail_threshold"


def score_calibration(
    dataset: CalibrationDataset,
    findings_by_case: Mapping[str, tuple[Finding, ...]],
    config: CalibrationConfig,
) -> tuple[KeyOutcome, ...]:
    outcomes: list[KeyOutcome] = []
    for identity in config.source_rows:
        totals = [0, 0, 0, 0, 0, 0]
        error_cases = 0
        correct_cases = 0
        confidences: set[float] = set()
        for case in dataset.cases:
            if case.primary_source_identity == identity.source:
                if case.role == "error":
                    error_cases += 1
                else:
                    correct_cases += 1
            predictions = findings_by_case.get(case.id, ())
            for prediction in predictions:
                if str(prediction.source) == identity.source:
                    confidences.add(prediction.confidence.value)
            values = _case_counts(case, identity, predictions)
            for index, value in enumerate(values):
                totals[index] += value
        counts = CalibrationCounts(
            error_cases,
            correct_cases,
            totals[0],
            totals[1],
            totals[2],
            totals[3],
            totals[4],
            totals[5],
        )
        metrics = _metrics(counts)
        observed, verdict = _verdict(identity, counts, metrics, confidences, config)
        outcomes.append(
            KeyOutcome(
                identity,
                counts,
                metrics,
                observed,
                identity.emitted_confidence if verdict == "candidate" else None,
                verdict,
            )
        )
    return tuple(outcomes)
