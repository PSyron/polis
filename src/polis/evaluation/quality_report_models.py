"""Typed models shared by quality baseline and threshold artifacts."""

from __future__ import annotations

from dataclasses import dataclass

from polis.evaluation.metrics import QualityCounts
from polis.evaluation.quality_protocol import (
    LatencyMetrics,
    ResourceMetrics,
    RunIdentity,
    ThroughputMetrics,
)

type JsonValue = str | int | float | bool | None | list["JsonValue"] | JsonObject
type JsonObject = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class QualityReportError(ValueError):
    """Raised when a quality artifact violates its versioned contract."""

    message: str

    def __str__(self) -> str:
        return self.message


@dataclass(frozen=True, slots=True)
class QualityReport:
    """Parsed, trusted representation of one measured baseline report."""

    run_identity: RunIdentity
    dataset_id: str
    dataset_sha256: str
    dataset_cases: int
    dataset_source: str
    counts: QualityCounts
    quality_precision: float | None
    quality_recall: float | None
    quality_f1: float | None
    quality_span_accuracy: float | None
    quality_correction_accuracy: float | None
    quality_false_alarm_rate: float | None
    warmup_repetitions: int
    measured_repetitions: int
    repetition_hashes: tuple[str, ...]
    latency: LatencyMetrics
    throughput: ThroughputMetrics
    resources: ResourceMetrics

    @property
    def artifact_sha256(self) -> str:
        return str(self.run_identity.artifact_sha256)


@dataclass(frozen=True, slots=True)
class ThresholdProposal:
    """Parsed proposal whose policy and measured values still require validation."""

    baseline_path: str
    baseline_sha256: str
    dataset_sha256: str
    minimum_precision: float | None
    minimum_recall: float | None
    minimum_f1: float | None
    minimum_span_accuracy: float | None
    minimum_correction_accuracy: float | None
    maximum_false_alarm_rate: float | None
    status: str
    enforced: bool
