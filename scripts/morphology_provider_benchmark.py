from __future__ import annotations

import hashlib
import json
import platform
import resource
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Final

from scripts.morphology_provider_contract import QualificationDataset
from scripts.morphology_provider_json import JsonValue
from scripts.morphology_provider_morfeusz import CaseOutcome, MorfeuszProvider

EXPECTED_PACKAGE_VERSION: Final = "1.99.15"
EXPECTED_DICTIONARY_ID: Final = "pl.sgjp.sgjp-2026.06.01"
EXPECTED_NOTICE_SHA256: Final = (
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    report: dict[str, JsonValue]
    verdict: str


@dataclass(frozen=True, slots=True)
class UnsupportedPlatformError(Exception):
    platform_name: str

    def __str__(self) -> str:
        return f"unsupported ru_maxrss units on {self.platform_name}"


def _canonical_bytes(value: JsonValue) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()


def _sha256(value: JsonValue) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def normalized_digest(report: dict[str, JsonValue]) -> str:
    included = {
        key: report[key]
        for key in ("identity", "dataset", "outcomes", "quality", "gates", "verdict")
        if key in report
    }
    return _sha256(included)


def _outcome_json(outcome: CaseOutcome) -> dict[str, JsonValue]:
    return {
        "case_id": outcome.case_id,
        "kind": outcome.kind,
        "form": outcome.form,
        "reason": outcome.reason,
    }


def _quality(
    dataset: QualificationDataset, outcomes: tuple[CaseOutcome, ...]
) -> dict[str, JsonValue]:
    true_positives = 0
    false_positives = 0
    false_negatives = 0
    alarmed_negative_cases = 0
    negative_cases = 0
    for case, outcome in zip(dataset.cases, outcomes, strict=True):
        expected_suggestion = case.expected_form is not None
        actual_suggestion = outcome.kind == "suggest"
        exact = actual_suggestion and outcome.form == case.expected_form
        if expected_suggestion:
            true_positives += int(exact)
            false_positives += int(actual_suggestion and not exact)
            false_negatives += int(not exact)
        else:
            negative_cases += 1
            false_positives += int(actual_suggestion)
            alarmed_negative_cases += int(actual_suggestion)
    precision = true_positives / (true_positives + false_positives)
    recall = true_positives / (true_positives + false_negatives)
    correction_accuracy = true_positives / max(true_positives + false_positives, 1)
    false_alarm_rate = alarmed_negative_cases / negative_cases
    return {
        "true_positives": true_positives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "negative_cases": negative_cases,
        "alarmed_negative_cases": alarmed_negative_cases,
        "precision": precision,
        "recall": recall,
        "correction_accuracy": correction_accuracy,
        "false_alarm_rate": false_alarm_rate,
    }


def _percentile(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * percentile + 0.999) - 1))
    return ordered[index]


def _peak_rss_bytes() -> int:
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform == "darwin":
        return int(peak)
    if sys.platform.startswith("linux"):
        return int(peak * 1024)
    raise UnsupportedPlatformError(sys.platform)


def _evaluate_once(
    dataset: QualificationDataset, provider: MorfeuszProvider
) -> tuple[tuple[CaseOutcome, ...], list[int]]:
    outcomes: list[CaseOutcome] = []
    durations: list[int] = []
    for case in dataset.cases:
        started = time.perf_counter_ns()
        outcomes.append(provider.evaluate(case))
        durations.append(time.perf_counter_ns() - started)
    return tuple(outcomes), durations


def _gates(
    dataset: QualificationDataset,
    provider: MorfeuszProvider,
    quality: dict[str, JsonValue],
    stable: bool,
    outcomes: tuple[CaseOutcome, ...],
) -> dict[str, JsonValue]:
    by_id = {outcome.case_id: outcome for outcome in outcomes}
    identity = provider.identity
    thresholds = dataset.thresholds
    return {
        "package_version": identity.package_version == EXPECTED_PACKAGE_VERSION,
        "dictionary_id": identity.dictionary_id == EXPECTED_DICTIONARY_ID,
        "dictionary_notice_sha256": identity.dictionary_notice_sha256
        == EXPECTED_NOTICE_SHA256,
        "precision": quality["precision"] == thresholds.precision,
        "recall": quality["recall"] == thresholds.recall,
        "correction_accuracy": quality["correction_accuracy"]
        == thresholds.correction_accuracy,
        "false_alarm_rate": quality["false_alarm_rate"] == thresholds.false_alarm_rate,
        "ambiguity_abstention": by_id["ambiguity_nowy_without_source_filter"].kind
        == "abstain",
        "unknown_abstention": by_id["unknown_xyzzyq"].kind == "abstain",
        "stable_repetitions": stable,
    }


def run_benchmark(
    dataset: QualificationDataset,
    provider: MorfeuszProvider,
    *,
    startup_ns: int,
) -> BenchmarkResult:
    _evaluate_once(dataset, provider)
    repetitions: list[tuple[CaseOutcome, ...]] = []
    durations: list[int] = []
    hashes: list[str] = []
    for _ in range(dataset.thresholds.stable_repetitions):
        outcomes, measured = _evaluate_once(dataset, provider)
        repetitions.append(outcomes)
        durations.extend(measured)
        hashes.append(_sha256([_outcome_json(item) for item in outcomes]))
    final_outcomes = repetitions[-1]
    quality = _quality(dataset, final_outcomes)
    stable = len(set(hashes)) == 1
    gates = _gates(dataset, provider, quality, stable, final_outcomes)
    identity_ok = all(
        gates[key]
        for key in ("package_version", "dictionary_id", "dictionary_notice_sha256")
    )
    verdict = (
        "PASS" if all(gates.values()) else ("FAIL" if identity_ok else "INCONCLUSIVE")
    )
    total_ns = sum(durations)
    report: dict[str, JsonValue] = {
        "schema_id": "polis.morphology-provider-qualification-report",
        "schema_version": 1,
        "identity": {
            "provider": "morfeusz2",
            "package_version": provider.identity.package_version,
            "dictionary_id": provider.identity.dictionary_id,
            "dictionary_notice_sha256": provider.identity.dictionary_notice_sha256,
        },
        "dataset": {
            "dataset_id": dataset.identity.dataset_id,
            "dataset_version": dataset.identity.dataset_version,
            "canonical_sha256": dataset.identity.canonical_sha256,
        },
        "outcomes": [_outcome_json(item) for item in final_outcomes],
        "quality": quality,
        "gates": gates,
        "verdict": verdict,
        "reproducibility": {
            "measured_repetitions": len(repetitions),
            "stable_repetitions": stable,
            "repetition_hashes": hashes,
        },
        "performance": {
            "startup_ns": startup_ns,
            "min_ns": min(durations),
            "mean_ns": int(statistics.fmean(durations)),
            "p50_ns": _percentile(durations, 0.50),
            "p95_ns": _percentile(durations, 0.95),
            "max_ns": max(durations),
            "throughput_cases_per_second": len(durations) * 1_000_000_000 / total_ns,
            "peak_rss_bytes": _peak_rss_bytes(),
            "installed_size_delta_bytes": provider.identity.installed_bytes,
        },
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
        },
    }
    digest = normalized_digest(report)
    report["normalized_digest"] = digest
    return BenchmarkResult(report=report, verdict=verdict)
