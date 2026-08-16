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


@dataclass(frozen=True, slots=True)
class QualityFloors:
    minimum_precision: float | None
    minimum_recall: float | None
    minimum_f1: float | None
    minimum_exact_span_accuracy: float | None
    minimum_exact_correction_accuracy: float | None
    maximum_false_alarm_rate: float | None


@dataclass(frozen=True, slots=True)
class PerformanceComparison:
    maximum_p95_latency_ns: int
    minimum_throughput_cases_per_second: float
    maximum_peak_rss_bytes: int
    required_warmup_repetitions: int
    required_measured_repetitions: int
    require_identical_repetition_hashes: bool
    required_environment_match: tuple[str, ...]
    allowed_regression_fraction: float
    missing_metric: str
    nondeterminism: str
    environment_mismatch: str
    performance_regression: str


@dataclass(frozen=True, slots=True)
class ProfileThresholdProposal:
    baseline_path: str
    baseline_sha256: str
    planned_morphology_source_semantics: str
    planned_non_morphology_source_semantics: str
    quality: QualityFloors
    performance: PerformanceComparison


@dataclass(frozen=True, slots=True)
class ThresholdProposalV2:
    dataset_sha256: str
    artifact_sha256: str
    source_git_sha: str
    default: ProfileThresholdProposal
    morphology: ProfileThresholdProposal
    status: str
    enforced: bool


@dataclass(frozen=True, slots=True)
class ProfileThresholdProposalV3:
    baseline_path: str
    baseline_sha256: str
    performance_result_path: str
    performance_result_sha256: str
    planned_morphology_source_semantics: str
    planned_non_morphology_source_semantics: str
    quality: QualityFloors
    performance: PerformanceComparison


@dataclass(frozen=True, slots=True)
class ThresholdProposalV3:
    dataset_sha256: str
    quality_artifact_sha256: str
    quality_source_git_sha: str
    performance_artifact_sha256: str
    performance_source_git_sha: str
    default: ProfileThresholdProposalV3
    morphology: ProfileThresholdProposalV3
    status: str
    enforced: bool


type ThresholdProposalArtifact = (
    ThresholdProposal | ThresholdProposalV2 | ThresholdProposalV3
)
