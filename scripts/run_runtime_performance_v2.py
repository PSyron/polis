from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Iterator
from functools import partial
from pathlib import Path
from typing import cast

from polis.core import Category, Confidence, Finding, Severity, Source
from polis.evaluation.metrics import evaluate_baseline
from polis.evaluation.quality_dataset import (
    QualityDatasetVersion,
    as_evaluation_dataset,
    load_quality_dataset,
    quality_dataset_paths,
)
from polis.evaluation.quality_protocol import peak_rss_bytes
from polis.runtime_performance_protocol import run_isolated_measurement


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finding(payload: dict[str, object]) -> Finding:
    return Finding(
        id=str(payload["id"]),
        category=Category(str(payload["category"])),
        severity=Severity(str(payload["severity"])),
        message=str(payload["message"]),
        explanation=str(payload["explanation"]),
        original=str(payload["original"]),
        suggestion=None
        if payload["suggestion"] is None
        else str(payload["suggestion"]),
        start=cast(int, payload["start"]),
        end=cast(int, payload["end"]),
        confidence=Confidence(cast(float, payload["confidence"])),
        source=Source.parse(str(payload["source"])),
    )


def ratio(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def next_findings(
    _text: str, *, iterator: Iterator[tuple[Finding, ...]]
) -> tuple[Finding, ...]:
    return next(iterator)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=("reference", "current"), required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--default-python", required=True)
    parser.add_argument("--morphology-python", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--protocol-overlay", action="store_true")
    parser.add_argument("--protocol-sha", required=True)
    parser.add_argument("--worker-sha", required=True)
    args = parser.parse_args()

    dataset = load_quality_dataset(version=QualityDatasetVersion.V3)
    evaluation = as_evaluation_dataset(dataset)
    _, manifest_path = quality_dataset_paths(QualityDatasetVersion.V3)
    texts = tuple(case.text for case in dataset.cases)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    for profile, python in (
        ("default", args.default_python),
        ("morphology", args.morphology_python),
    ):
        measurement = run_isolated_measurement(
            python=python,
            profile=profile,
            texts=texts,
            warmup_repetitions=1,
            measured_repetitions=5,
        )
        reconstructed = tuple(
            tuple(finding(item) for item in case_findings)
            for case_findings in measurement.findings_by_case
        )
        iterator = iter(reconstructed)
        baseline = evaluate_baseline(
            dataset=evaluation,
            analyzer=partial(next_findings, iterator=iterator),
            run_label="runtime-performance-protocol-v2",
            run_reference=args.source_sha,
            configuration="Analyzer(AnalyzerConfig())",
        )
        counts = baseline.aggregate
        durations = sorted(measurement.durations_ns)
        total_duration = sum(durations)
        sample_count = len(durations)
        measured_code_points = sum(len(text) for text in texts) * 5
        count_payload = {
            "expected_findings": counts.expected_findings,
            "predicted_findings": counts.predicted_findings,
            "true_positives": counts.true_positives,
            "false_positives": counts.false_positives,
            "false_negatives": counts.false_negatives,
            "span_matches": counts.span_matches,
            "correction_matches": counts.correction_matches,
            "correct_cases": counts.correct_cases,
            "alarmed_correct_cases": counts.alarmed_correct_cases,
        }
        quality = {
            "precision": ratio(
                counts.true_positives, counts.true_positives + counts.false_positives
            ),
            "recall": ratio(
                counts.true_positives, counts.true_positives + counts.false_negatives
            ),
            "f1": ratio(
                2 * counts.true_positives,
                2 * counts.true_positives
                + counts.false_positives
                + counts.false_negatives,
            ),
            "span_accuracy": ratio(counts.span_matches, counts.expected_findings),
            "correction_accuracy": ratio(
                counts.correction_matches, counts.span_matches
            ),
            "false_alarm_rate": ratio(
                counts.alarmed_correct_cases, counts.correct_cases
            ),
            "counts": count_payload,
        }
        payload = {
            "schema_id": "polis.runtime-performance-result",
            "schema_version": 1,
            "protocol_version": 2,
            "role": args.role,
            "profile": profile,
            "source": {"git_sha": args.source_sha},
            "artifact": {
                "wheel_filename": args.wheel.name,
                "wheel_sha256": sha256(args.wheel),
            },
            "protocol_implementation": {
                "overlay_applied": args.protocol_overlay,
                "runtime_performance_protocol_sha256": args.protocol_sha,
                "runtime_performance_worker_sha256": args.worker_sha,
            },
            "dataset": {
                "id": dataset.id,
                "schema_id": dataset.schema_id,
                "schema_version": dataset.schema_version,
                "sha256": dataset.canonical_sha256,
                "manifest_sha256": sha256(manifest_path),
                "cases": len(dataset.cases),
            },
            "environment": measurement.environment,
            "morphology_provider": measurement.morphology_provider,
            "rss": {
                "harness_peak_rss_bytes": peak_rss_bytes(),
                "worker_startup_rss_bytes": measurement.startup_rss_bytes,
                "worker_measurement_start_rss_bytes": (
                    measurement.measurement_start_rss_bytes
                ),
                "worker_peak_rss_bytes": measurement.peak_rss_bytes,
                "worker_measured_incremental_peak_rss_bytes": measurement.peak_rss_bytes
                - measurement.measurement_start_rss_bytes,
            },
            "performance": {
                "latency_ns": {
                    "sample_count": sample_count,
                    "min": durations[0],
                    "mean": total_duration // sample_count,
                    "p50": durations[(50 * sample_count + 99) // 100 - 1],
                    "p95": durations[(95 * sample_count + 99) // 100 - 1],
                    "max": durations[-1],
                },
                "throughput": {
                    "measured_cases": sample_count,
                    "measured_code_points": measured_code_points,
                    "total_duration_ns": total_duration,
                    "cases_per_second": sample_count * 1_000_000_000 / total_duration,
                    "code_points_per_second": measured_code_points
                    * 1_000_000_000
                    / total_duration,
                },
            },
            "quality": quality,
            "reproducibility": {
                "warmup_repetitions": 1,
                "measured_repetitions": 5,
                "stable_repetitions": 5,
                "findings_sha256": measurement.findings_sha256,
            },
        }
        output = args.output_dir / f"runtime-performance-v2-{args.role}-{profile}.json"
        output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(output)


if __name__ == "__main__":
    main()
