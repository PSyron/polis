from __future__ import annotations

import hashlib
import json
from pathlib import Path

from polis.evaluation.metrics import BaselineResult, QualityCounts
from polis.evaluation.quality_dataset import (
    QUALITY_MANIFEST_PATH,
    as_evaluation_dataset,
    load_quality_dataset,
)
from polis.evaluation.quality_protocol import (
    LatencyMetrics,
    QualityProtocolResult,
    ResourceMetrics,
    RunIdentity,
    ThroughputMetrics,
)
from polis.evaluation.quality_report import baseline_file_sha256

type JsonValue = str | int | float | bool | None | list["JsonValue"] | JsonObject
type JsonObject = dict[str, JsonValue]


def _result() -> QualityProtocolResult:
    active = load_quality_dataset()
    evaluated = as_evaluation_dataset(active)
    counts = QualityCounts(
        expected_findings=3,
        predicted_findings=2,
        true_positives=2,
        false_negatives=1,
        span_matches=2,
        correction_matches=2,
        correct_cases=2,
        alarmed_correct_cases=1,
    )
    baseline = BaselineResult(
        run_label="quality-baseline",
        run_reference="local",
        configuration="Analyzer(AnalyzerConfig())",
        dataset_id=active.id,
        dataset_schema_version=active.schema_version,
        dataset_cases=len(active.cases),
        dataset_source=evaluated.source,
        dataset_hash=active.canonical_sha256,
        incorrect_case_count=8,
        correct_case_count=8,
        aggregate=counts,
        by_category={},
        by_source={},
    )
    return QualityProtocolResult(
        run_identity=RunIdentity(
            analyzer="Analyzer(AnalyzerConfig())",
            artifact_sha256="b" * 64,
            package_version="0.2.0",
            python_version="3.13.5",
            platform_system="Darwin",
            platform_release="25.0.0",
            platform_machine="arm64",
            dataset_schema_id=active.schema_id,
            dataset_schema_version=active.schema_version,
            manifest_schema_id="polis.quality-development-manifest",
            manifest_schema_version=1,
            manifest_sha256=hashlib.sha256(
                QUALITY_MANIFEST_PATH.read_bytes()
            ).hexdigest(),
        ),
        dataset_id=baseline.dataset_id,
        dataset_sha256=baseline.dataset_hash,
        warmup_repetitions=1,
        measured_repetitions=2,
        repetition_hashes=("d" * 64, "d" * 64),
        baseline=baseline,
        latency=LatencyMetrics(
            sample_count=32,
            min_ns=10,
            mean_ns=20,
            p50_ns=20,
            p95_ns=30,
            max_ns=30,
        ),
        throughput=ThroughputMetrics(
            measured_cases=32,
            measured_code_points=320,
            total_duration_ns=640,
            cases_per_second=50_000_000.0,
            code_points_per_second=500_000_000.0,
        ),
        resources=ResourceMetrics(peak_rss_bytes=12_345),
    )


def _proposal_payload(baseline: Path) -> JsonObject:
    report = json.loads(baseline.read_text(encoding="utf-8"))
    quality = report["quality"]
    return {
        "baseline_path": str(baseline),
        "baseline_sha256": baseline_file_sha256(baseline),
        "dataset_sha256": report["dataset"]["sha256"],
        "enforced": False,
        "proposed_thresholds": {
            "minimum_correction_accuracy": quality["correction_accuracy"],
            "minimum_f1": quality["f1"],
            "minimum_precision": quality["precision"],
            "minimum_recall": quality["recall"],
            "minimum_span_accuracy": quality["span_accuracy"],
            "maximum_false_alarm_rate": quality["false_alarm_rate"],
        },
        "schema_id": "polis.quality-threshold-proposal",
        "schema_version": 1,
        "status": "pending_maintainer_approval",
    }


def _write_proposal(path: Path, payload: JsonObject) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
