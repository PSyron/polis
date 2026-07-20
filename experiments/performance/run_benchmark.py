#!/usr/bin/env python3
"""Latency, throughput, and memory benchmark for deterministic analysis runs.

The benchmark is intentionally small and repository-local. It is designed to be
repeatable and produce machine-readable output suitable for an evidence trail.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import statistics
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from polis.analysis.pipeline import analyze_text
from polis.core import AnalysisOptions, Category
from polis.evaluation import findings_snapshot_for_run, load_dataset
from polis.evaluation.dataset import EvaluationCase
from polis.llm import MockHeuristicBackend, create_default_local_backend
from polis.rules import (
    DeterministicRuleRegistry,
    RuleRegistration,
    SyntaxCommaSpacingRule,
    SyntaxListSpacingRule,
    SyntaxQuoteSpacingRule,
)
from polis.rules.agreement import AgreementCopulaRule
from polis.rules.spelling import (
    SpellingJestesRule,
    SpellingWlasnieRule,
    SpellingZebyRule,
)

BENCHMARK_NAME: Final[str] = "m3-03-v1"
DEFAULT_REPETITIONS: Final[int] = 5
DEFAULT_WARMUP: Final[int] = 2


@dataclass(frozen=True)
class _Distribution:
    minimum: float
    maximum: float
    mean: float
    median: float
    p50: float
    p95: float

    def to_payload(self, count: int) -> dict[str, float]:
        return {
            "count": count,
            "min_ms": self.minimum,
            "max_ms": self.maximum,
            "mean_ms": self.mean,
            "median_ms": self.median,
            "p50_ms": self.p50,
            "p95_ms": self.p95,
        }


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = fraction * (len(sorted_values) - 1)
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _distribution(values: list[float]) -> _Distribution:
    return _Distribution(
        minimum=min(values),
        maximum=max(values),
        mean=statistics.fmean(values),
        median=statistics.median(values),
        p50=_percentile(values, 0.50),
        p95=_percentile(values, 0.95),
    )


def _collect_environment() -> dict[str, object]:
    return {
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "architecture": platform.architecture(),
            "python_bits": platform.architecture()[0],
        },
        "software": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "min_supported_python": "3.12",
            "max_supported_python": "3.14",
        },
        "run": {
            "created_at_utc": datetime.datetime.now(datetime.UTC).isoformat() + "Z",
            "script": "experiments/performance/run_benchmark.py",
            "seed": BENCHMARK_NAME,
        },
    }


def _build_analyzer(*, use_local_backend: bool) -> Callable[[str], tuple[object, ...]]:
    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(rule=SpellingZebyRule(), categories={Category.SPELLING}),
            RuleRegistration(
                rule=SpellingWlasnieRule(), categories={Category.SPELLING}
            ),
            RuleRegistration(rule=SpellingJestesRule(), categories={Category.SPELLING}),
            RuleRegistration(
                rule=AgreementCopulaRule(), categories={Category.AGREEMENT}
            ),
            RuleRegistration(
                rule=SyntaxListSpacingRule(), categories={Category.SYNTAX}
            ),
            RuleRegistration(
                rule=SyntaxCommaSpacingRule(), categories={Category.PUNCTUATION}
            ),
            RuleRegistration(
                rule=SyntaxQuoteSpacingRule(), categories={Category.PUNCTUATION}
            ),
        )
    )
    backend: MockHeuristicBackend | None = (
        create_default_local_backend() if use_local_backend else None
    )

    def _analyze(text: str) -> tuple[object, ...]:
        return cast(
            "tuple[object, ...]",
            analyze_text(
                text,
                registry=registry,
                local_backend=backend,
                options=AnalysisOptions(),
            ),
        )

    return _analyze


def _run_configuration(
    *,
    name: str,
    analyzer: Callable[[str], tuple[object, ...]],
    repetitions: int,
    warmup_repetitions: int,
    dataset_cases: tuple[EvaluationCase, ...],
) -> dict[str, object]:
    case_payloads: list[dict[str, object]] = []
    latencies_ms: list[float] = []
    total_input_chars = 0
    total_peak_bytes = 0

    tracemalloc.start()
    try:
        for _ in range(max(0, warmup_repetitions)):
            for case in dataset_cases:
                analyzer(case.text)

        for case in dataset_cases:
            case_latencies: list[float] = []
            case_chars = len(case.text)
            total_input_chars += case_chars
            for _ in range(max(1, repetitions)):
                start = time.perf_counter()
                analyzer(case.text)
                elapsed = (time.perf_counter() - start) * 1000.0
                case_latencies.append(elapsed)
                latencies_ms.append(elapsed)
                _, peak = tracemalloc.get_traced_memory()
                total_peak_bytes = max(total_peak_bytes, peak)
            case_payloads.append(
                {
                    "case_id": case.id,
                    "input_chars": case_chars,
                    "latency_ms": _distribution(case_latencies).to_payload(
                        len(case_latencies)
                    ),
                }
            )
    finally:
        _, peak = tracemalloc.get_traced_memory()
        total_peak_bytes = max(total_peak_bytes, peak)
        tracemalloc.stop()

    total_elapsed_seconds = sum(latencies_ms) / 1000.0
    latency_distribution = _distribution(latencies_ms)

    return {
        "name": name,
        "repetitions": repetitions,
        "warmup_repetitions": warmup_repetitions,
        "case_count": len(dataset_cases),
        "input_chars": total_input_chars,
        "latency_ms": latency_distribution.to_payload(len(latencies_ms)),
        "throughput_chars_per_sec": (
            float(total_input_chars) / total_elapsed_seconds
            if total_elapsed_seconds
            else 0.0
        ),
        "throughput_case_per_sec": (
            float(len(dataset_cases) * max(1, repetitions)) / total_elapsed_seconds
            if total_elapsed_seconds
            else 0.0
        ),
        "memory_peak_bytes": total_peak_bytes,
        "per_case": case_payloads,
    }


def run_benchmark(
    *,
    repetitions: int = DEFAULT_REPETITIONS,
    warmup_repetitions: int = DEFAULT_WARMUP,
) -> dict[str, object]:
    """Run the small benchmark and return a serialized report payload."""

    dataset = load_dataset()
    runs: list[dict[str, object]] = []

    config_definitions = (
        ("rules-only", False),
        ("rules+mock-llm", True),
    )
    dataset_path = "src/polis/evaluation/datasets/v1/cases.json"

    for name, use_local_backend in config_definitions:
        runs.append(
            _run_configuration(
                name=name,
                analyzer=_build_analyzer(use_local_backend=use_local_backend),
                repetitions=repetitions,
                warmup_repetitions=warmup_repetitions,
                dataset_cases=dataset.cases,
            )
        )

    return {
        "schema_version": 1,
        "benchmark_id": BENCHMARK_NAME,
        "settings": {
            "repetitions": repetitions,
            "warmup_repetitions": warmup_repetitions,
            "dataset": {
                "id": dataset.id,
                "schema_version": dataset.schema_version,
                "cases": len(dataset.cases),
                "path": dataset_path,
                "snapshot_sha256": findings_snapshot_for_run(),
            },
        },
        "environment": _collect_environment(),
        "runs": runs,
    }


def _validate(payload: object) -> None:
    if not isinstance(payload, dict):
        raise TypeError("payload must be a JSON object")
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported schema version")
    settings = payload.get("settings")
    environment = payload.get("environment")
    runs = payload.get("runs")
    if not isinstance(settings, dict):
        raise TypeError("settings must be a mapping")
    if not isinstance(environment, dict):
        raise TypeError("environment must be a mapping")
    if not isinstance(runs, list) or not runs:
        raise ValueError("runs must be a non-empty list")
    for run in runs:
        if not isinstance(run, dict):
            raise TypeError("run entry must be a mapping")
        for key in (
            "name",
            "repetitions",
            "case_count",
            "latency_ms",
            "throughput_chars_per_sec",
        ):
            if key not in run:
                raise ValueError(f"run entry missing {key!r}")
        if not isinstance(run["per_case"], list):
            raise TypeError("per_case must be a list")


def _serialize(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate", type=Path)
    parsed = parser.parse_args()

    if parsed.validate is not None:
        payload = json.loads(parsed.validate.read_text(encoding="utf-8"))
        _validate(payload)
        return 0

    payload = run_benchmark(
        repetitions=parsed.repetitions,
        warmup_repetitions=parsed.warmup,
    )
    if parsed.output is not None:
        parsed.output.write_text(_serialize(payload), encoding="utf-8")
    run_count = len(cast("list[object]", payload["runs"]))
    print(f"Benchmark {BENCHMARK_NAME} finished for {run_count} configs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
