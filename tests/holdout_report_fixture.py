from __future__ import annotations

import importlib
from typing import Protocol, runtime_checkable

from tests.holdout_test_helpers import (
    ARTIFACT_SHA256,
    CONFIG_SHA256,
    DATASET_SHA256,
    NOTICE_SHA256,
    SOURCE_IDENTITIES,
    SOURCE_SHA256,
    JsonObject,
    JsonValue,
)


class QualityView(Protocol):
    precision: float


class PerformanceView(Protocol):
    peak_rss_bytes: int


class SourceOutcomeView(Protocol):
    verdict: str


class RawReportView(Protocol):
    quality: QualityView
    performance: PerformanceView
    per_source: tuple[SourceOutcomeView, ...]
    verdict: str


@runtime_checkable
class ReportApi(Protocol):
    HoldoutReportError: type[Exception]

    def parse_raw_report(self, raw: JsonObject) -> RawReportView: ...

    def normalized_report_bytes(self, report: RawReportView) -> bytes: ...


def report_api() -> ReportApi:
    module = importlib.import_module("polis.evaluation.holdout_report")
    if not isinstance(module, ReportApi):
        raise AssertionError("planned privacy-safe report API is incomplete")
    return module


def _source_outcome(identity: tuple[str, str, str, str, str]) -> JsonObject:
    return {
        "identity": list(identity),
        "case_count": 1,
        "expected_findings": 1,
        "predicted_findings": 1,
        "true_positives": 1,
        "false_positives": 0,
        "false_negatives": 0,
        "span_matches": 1,
        "correction_matches": 1,
        "correct_cases": 0,
        "alarmed_correct_cases": 0,
        "verdict": "pass",
    }


def raw_report() -> JsonObject:
    per_source: list[JsonValue] = [
        _source_outcome(identity) for identity in SOURCE_IDENTITIES
    ]
    last = _source_outcome(SOURCE_IDENTITIES[-1])
    last.update(
        {
            "case_count": 0,
            "expected_findings": 0,
            "predicted_findings": 0,
            "true_positives": 0,
            "span_matches": 0,
            "correction_matches": 0,
            "verdict": "insufficient_evidence",
        }
    )
    per_source[-1] = last
    return {
        "schema_id": "polis.a-b-one-shot.raw-report",
        "schema_version": 1,
        "experiment_id": "polis-a-b-one-shot-v1",
        "identities": {
            "config_sha256": CONFIG_SHA256,
            "dataset_sha256": DATASET_SHA256,
            "source_sha256": SOURCE_SHA256,
            "wheel_sha256": ARTIFACT_SHA256,
            "sdist_sha256": "e" * 64,
            "lock_sha256": "f" * 64,
        },
        "quality": {
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
            "exact_span_accuracy": 1.0,
            "exact_correction_accuracy": 1.0,
            "correct_sentence_false_alarm_rate": 0.0,
        },
        "performance": {
            "latency_ns": {
                "min": 10,
                "mean": 20,
                "p50": 20,
                "p95": 30,
                "max": 30,
            },
            "throughput": {
                "cases_per_second": 123.4,
                "code_points_per_second": 999.1,
            },
            "peak_rss_bytes": 123456,
        },
        "environment": {
            "os": "Darwin",
            "release": "25.0",
            "machine": "arm64",
            "python": "3.14.3",
            "package": "0.2.0",
            "morfeusz_dictionary": "pl.sgjp",
            "morfeusz_notice_sha256": NOTICE_SHA256,
        },
        "per_source": per_source,
        "verdict": "fail_threshold",
    }
