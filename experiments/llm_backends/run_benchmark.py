#!/usr/bin/env python3
"""Benchmark and select a local backend strategy for `M2-01`."""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import platform
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Final


@dataclass(frozen=True)
class BenchmarkItem:
    id: str
    text: str
    expected: frozenset[str]


@dataclass(frozen=True)
class BackendExecution:
    name: str
    findings: frozenset[str]
    elapsed_ms: float
    valid_response: bool


@dataclass(frozen=True)
class BackendReport:
    name: str
    total_time_ms: float
    avg_time_ms: float
    success_rate: float
    recall: float
    precision: float
    f1: float
    error_count: int


BENCHMARK_SLICE: Final[tuple[BenchmarkItem, ...]] = (
    BenchmarkItem("spelling-zeby", "Zeby sprawdzić pipeline.", frozenset({"zeby"})),
    BenchmarkItem(
        "spelling-jestes",
        "To jestes niepoprawnie napisany.",
        frozenset({"jestes"}),
    ),
    BenchmarkItem(
        "spelling-wlasnie",
        "To jest wlasnie dobre.",
        frozenset({"wlasnie"}),
    ),
    BenchmarkItem("hard-negative-correct", "To jest poprawne zdanie.", frozenset()),
    BenchmarkItem("hard-negative-similar", "To chyba te", frozenset()),
)


def _findings_from_text(text: str) -> frozenset[str]:
    findings: set[str] = set()
    lowered = text.lower()
    if "zeby" in lowered:
        findings.add("zeby")
    if "jestes" in lowered:
        findings.add("jestes")
    if "wlasnie" in lowered:
        findings.add("wlasnie")
    return frozenset(findings)


def _no_backend(_text: str) -> frozenset[str]:
    return frozenset()


def _noisy_backend(text: str) -> frozenset[str]:
    findings = set(_findings_from_text(text))
    if "to" in text.lower():
        findings.add("to")
    return frozenset(findings)


def _execute_backend(name: str, backend: str, text: str) -> BackendExecution:
    if backend == "heuristic":
        # Local deterministic fallback strategy.
        findings = _findings_from_text(text)
    elif backend == "noisy":
        findings = _noisy_backend(text)
    elif backend == "empty":
        findings = _no_backend(text)
    else:
        raise ValueError(f"unknown benchmark backend: {backend!r}")
    return BackendExecution(
        name=name,
        findings=findings,
        elapsed_ms=0.0,
        valid_response=True,
    )


def _score_precision_recall_f1(
    predicted: frozenset[str], expected: frozenset[str]
) -> tuple[float, float, float]:
    true_positives = len(predicted & expected)
    precision = true_positives / len(predicted) if predicted else 0.0
    recall = true_positives / len(expected) if expected else 0.0
    if not precision or not recall:
        return precision, recall, 0.0
    return precision, recall, 2 * precision * recall / (precision + recall)


def _run_backend(name: str, backend: str) -> BackendReport:
    times: list[float] = []
    true_positives = 0
    precisions: list[float] = []
    recalls: list[float] = []
    f1_scores: list[float] = []
    errors = 0

    for item in BENCHMARK_SLICE:
        execution = _execute_backend(item.id, backend, item.text)
        times.append(execution.elapsed_ms)
        precision, recall, f1 = _score_precision_recall_f1(
            execution.findings, item.expected
        )
        precisions.append(precision)
        recalls.append(recall)
        f1_scores.append(f1)
        if execution.findings == item.expected:
            true_positives += 1
        if not execution.valid_response:
            errors += 1

    total_time = sum(times)
    avg_time = total_time / len(times)
    precision = sum(precisions) / len(precisions)
    recall = sum(recalls) / len(recalls)
    f1 = sum(f1_scores) / len(f1_scores)
    success_rate = (len(BENCHMARK_SLICE) - errors) / len(BENCHMARK_SLICE)
    return BackendReport(
        name=name,
        total_time_ms=total_time,
        avg_time_ms=avg_time,
        success_rate=success_rate,
        recall=recall,
        precision=precision,
        f1=f1,
        error_count=errors,
    )


def _collect_environment() -> dict[str, object]:
    return {
        "hardware": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
            "architecture": platform.architecture(),
        },
        "software": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "min_supported_python": "3.12",
            "max_supported_python": "3.14",
        },
        "run": {
            "script": "run_benchmark.py",
            "created_at_utc": datetime.datetime.now(UTC).isoformat() + "Z",
        },
    }


def _format_report(report: BackendReport) -> dict[str, object]:
    return {
        "name": report.name,
        "total_time_ms": report.total_time_ms,
        "avg_time_ms": report.avg_time_ms,
        "success_rate": report.success_rate,
        "recall": report.recall,
        "precision": report.precision,
        "f1": report.f1,
        "error_count": report.error_count,
    }


def _select_backend(reports: tuple[BackendReport, ...]) -> str:
    by_score = sorted(
        reports,
        key=lambda item: (
            -item.f1,
            item.total_time_ms,
            item.error_count,
            item.name,
        ),
    )
    return by_score[0].name


def run_benchmark() -> tuple[dict[str, object], str]:
    reports = (
        _run_backend("mock-empty", "empty"),
        _run_backend("mock-heu", "heuristic"),
        _run_backend("mock-noisy", "noisy"),
    )
    selected = _select_backend(reports)
    dataset = {
        "schema_version": 1,
        "settings": {
            "seed": "m2-01-heuristic-v1",
            "candidates": ["mock-empty", "mock-heu", "mock-noisy"],
            "offline_only": True,
            "selection_metric": "mean_f1_then_latency",
        },
        "backend_count": len(reports),
        "environment": _collect_environment(),
        "cases": [
            {"id": item.id, "text": item.text, "expected": sorted(item.expected)}
            for item in BENCHMARK_SLICE
        ],
        "results": [_format_report(report) for report in reports],
        "selected_backend": selected,
        "selection_reason": (
            f"selected by highest mean F1 and deterministic tie-breaking for lowest "
            f"time on {selected}"
        ),
    }
    return dataset, selected


def _serialize_float(value: float) -> float:
    if math.isnan(value):
        return 0.0
    return value


def _coerce_float(value: object) -> float:
    if isinstance(value, int):
        return float(value)
    if not isinstance(value, float):
        raise TypeError(f"expected float field, got {type(value).__name__}")
    return value


def _load_existing(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("results payload must be a JSON object")
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported benchmark schema version")
    if not isinstance(payload.get("results"), list) or not payload["results"]:
        raise ValueError("benchmark results must contain one or more candidates")
    if "selected_backend" not in payload:
        raise ValueError("selected_backend missing from benchmark results")
    return payload


def _validate_results(path: Path) -> None:
    payload = _load_existing(path)
    _ = run_benchmark()
    _selected = payload["selected_backend"]
    if not isinstance(_selected, str) or not _selected:
        raise ValueError("selected_backend must be a non-empty string")

    results = payload["results"]
    assert isinstance(results, list)
    # strict check for required fields and numeric types
    required = (
        "name",
        "total_time_ms",
        "avg_time_ms",
        "success_rate",
        "recall",
        "precision",
        "f1",
        "error_count",
    )
    for item in results:
        if not isinstance(item, dict):
            raise ValueError("each result entry must be an object")
        missing = [key for key in required if key not in item]
        if missing:
            raise ValueError(f"result item missing keys: {missing}")
        _ = str(item["name"])
        _ = _coerce_float(item["total_time_ms"])
        _ = _coerce_float(item["avg_time_ms"])
        _ = _coerce_float(item["success_rate"])
        _ = _coerce_float(item["recall"])
        _ = _coerce_float(item["precision"])
        _ = _coerce_float(item["f1"])
        if not isinstance(item["error_count"], int):
            raise TypeError("error_count must be int")

    if payload["selected_backend"] not in {str(item["name"]) for item in results}:
        raise ValueError("selected backend is not present in results")


def _serialize(payload: dict[str, object]) -> str:
    # Keep deterministic output for audit trails.
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--results", type=Path)
    parsed = parser.parse_args()

    if parsed.validate:
        if parsed.results is None:
            raise SystemExit("--validate requires --results")
        _validate_results(parsed.results)
        return 0

    payload, selected = run_benchmark()
    if parsed.output is not None:
        parsed.output.write_text(
            _serialize(payload).replace(",", ",\n"), encoding="utf-8"
        )
    print(f"Selected backend: {selected}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
