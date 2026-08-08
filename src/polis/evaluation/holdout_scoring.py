from __future__ import annotations

import importlib.metadata
import platform

from polis import Finding
from polis.evaluation.holdout_admission import ExternalAdmission
from polis.evaluation.holdout_models import (
    HoldoutCase,
    HoldoutConfig,
    HoldoutDataset,
    JsonObject,
)

_NOTICE_SHA256 = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
_COUNT_NAMES = (
    "case_count",
    "expected_findings",
    "predicted_findings",
    "true_positives",
    "false_positives",
    "false_negatives",
    "span_matches",
    "correction_matches",
    "correct_cases",
    "alarmed_correct_cases",
)


def _score(
    cases: tuple[HoldoutCase, ...],
    findings_by_case: tuple[tuple[Finding, ...], ...],
    *,
    source: str | None = None,
) -> dict[str, int]:
    counts = dict.fromkeys(_COUNT_NAMES, 0)
    for case, predictions in zip(cases, findings_by_case, strict=True):
        if source is not None and source not in case.targets:
            continue
        expected = [
            item
            for item in case.expected_findings
            if source is None or item.source == source
        ]
        observed = [
            item for item in predictions if source is None or str(item.source) == source
        ]
        counts["case_count"] += 1
        counts["expected_findings"] += len(expected)
        counts["predicted_findings"] += len(observed)
        correct = case.role == "correct"
        counts["correct_cases"] += int(correct)
        counts["alarmed_correct_cases"] += int(correct and bool(observed))
        exact_used = [False] * len(expected)
        span_used = [False] * len(expected)
        for prediction in observed:
            exact_index = next(
                (
                    index
                    for index, item in enumerate(expected)
                    if not exact_used[index]
                    and str(prediction.source) == item.source
                    and prediction.category.value == item.category
                    and prediction.start == item.start
                    and prediction.end == item.end
                    and prediction.original == item.original
                    and prediction.suggestion == item.suggestion
                ),
                None,
            )
            if exact_index is not None:
                exact_used[exact_index] = True
                counts["true_positives"] += 1
                counts["correction_matches"] += 1
            span_index = next(
                (
                    index
                    for index, item in enumerate(expected)
                    if not span_used[index]
                    and str(prediction.source) == item.source
                    and prediction.category.value == item.category
                    and prediction.start == item.start
                    and prediction.end == item.end
                ),
                None,
            )
            if span_index is not None:
                span_used[span_index] = True
                counts["span_matches"] += 1
        counts["false_positives"] += len(observed) - sum(exact_used)
        counts["false_negatives"] += len(expected) - sum(exact_used)
    return counts


def _ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _quality(counts: dict[str, int]) -> JsonObject:
    true_positives = counts["true_positives"]
    false_positives = counts["false_positives"]
    false_negatives = counts["false_negatives"]
    return {
        "precision": _ratio(true_positives, true_positives + false_positives),
        "recall": _ratio(true_positives, true_positives + false_negatives),
        "f1": _ratio(
            2 * true_positives, 2 * true_positives + false_positives + false_negatives
        ),
        "exact_span_accuracy": _ratio(
            counts["span_matches"], counts["expected_findings"]
        ),
        "exact_correction_accuracy": _ratio(
            counts["correction_matches"], counts["span_matches"]
        ),
        "correct_sentence_false_alarm_rate": _ratio(
            counts["alarmed_correct_cases"], counts["correct_cases"]
        ),
    }


def _verdict(quality: JsonObject, config: HoldoutConfig, *, has_positive: bool) -> str:
    if not has_positive:
        return "insufficient_evidence"
    thresholds = config.thresholds
    minimums = {
        "precision": thresholds.precision,
        "recall": thresholds.recall,
        "f1": thresholds.f1,
        "exact_span_accuracy": thresholds.exact_span_accuracy,
        "exact_correction_accuracy": thresholds.exact_correction_accuracy,
    }
    for name, minimum in minimums.items():
        value = quality[name]
        if type(value) not in (int, float) or value < minimum:
            return "fail_threshold"
    false_alarm = quality["correct_sentence_false_alarm_rate"]
    if (
        type(false_alarm) not in (int, float)
        or false_alarm > thresholds.correct_sentence_false_alarm_rate
    ):
        return "fail_threshold"
    return "pass"


def _percentile(values: list[int], percentile: int) -> int:
    ordered = sorted(values)
    return ordered[((percentile * len(ordered) + 99) // 100) - 1]


def production_report(
    config: HoldoutConfig,
    admission: ExternalAdmission,
    dataset: HoldoutDataset,
    findings_by_case: tuple[tuple[Finding, ...], ...],
    durations: list[int],
    peak_rss: int,
) -> JsonObject:
    aggregate_counts = _score(dataset.cases, findings_by_case)
    aggregate_quality = _quality(aggregate_counts)
    outcomes: list[JsonObject] = []
    for identity in config.source_identities:
        counts = _score(dataset.cases, findings_by_case, source=identity.source)
        outcomes.append(
            {
                "identity": [
                    identity.source,
                    identity.category,
                    identity.operation,
                    identity.behavior_version,
                    identity.source_policy_version,
                ],
                **counts,
                "verdict": _verdict(
                    _quality(counts),
                    config,
                    has_positive=counts["expected_findings"] > 0,
                ),
            }
        )
    total_ns = sum(durations)
    measured_cases = len(dataset.cases) * config.measured_repetitions
    code_points = (
        sum(len(case.text) for case in dataset.cases) * config.measured_repetitions
    )
    return {
        "schema_id": "polis.a-b-one-shot.raw-report",
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "identities": {
            "config_sha256": admission.evidence.config_sha256,
            "dataset_sha256": dataset.sha256,
            "source_sha256": admission.evidence.source_sha256,
            "wheel_sha256": admission.wheel_sha256,
            "sdist_sha256": admission.sdist_sha256,
            "lock_sha256": admission.lock_sha256,
        },
        "quality": aggregate_quality,
        "performance": {
            "latency_ns": {
                "min": min(durations),
                "mean": total_ns // len(durations),
                "p50": _percentile(durations, 50),
                "p95": _percentile(durations, 95),
                "max": max(durations),
            },
            "throughput": {
                "cases_per_second": _ratio(measured_cases * 1_000_000_000, total_ns),
                "code_points_per_second": _ratio(code_points * 1_000_000_000, total_ns),
            },
            "peak_rss_bytes": peak_rss,
        },
        "environment": {
            "os": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "package": importlib.metadata.version("polis-nlp"),
            "morfeusz_dictionary": "pl.sgjp",
            "morfeusz_notice_sha256": _NOTICE_SHA256,
        },
        "per_source": outcomes,
        "verdict": _verdict(
            aggregate_quality,
            config,
            has_positive=aggregate_counts["expected_findings"] > 0,
        ),
    }
