from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from polis.core import Finding

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]
type CurrentPolicyState = Literal["automatic", "review-only"]
type CalibrationRole = Literal["error", "correct"]
type KeyVerdict = Literal["candidate", "fail_threshold", "insufficient_evidence"]
type CalibrationSourceTuple = tuple[
    str,
    str,
    str,
    str,
    str,
    float,
    CurrentPolicyState,
]


class CalibrationContractError(ValueError):
    message: str

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class CalibrationIntegrityError(CalibrationContractError):
    pass


class CalibrationOutputError(CalibrationContractError):
    pass


class AnalyzerCallable(Protocol):
    def __call__(self, text: str) -> tuple[Finding, ...]: ...


class AnalyzerFactory(Protocol):
    def __call__(self) -> AnalyzerCallable: ...


@dataclass(frozen=True, slots=True)
class CalibrationSourceIdentity:
    source: str
    category: str
    operation: str
    behavior_version: str
    source_policy_version: str
    emitted_confidence: float
    current_policy_state: CurrentPolicyState

    def as_tuple(self) -> CalibrationSourceTuple:
        return (
            self.source,
            self.category,
            self.operation,
            self.behavior_version,
            self.source_policy_version,
            self.emitted_confidence,
            self.current_policy_state,
        )


@dataclass(frozen=True, slots=True)
class CalibrationThresholds:
    precision: float
    recall: float
    f1: float
    exact_span_accuracy: float
    exact_correction_accuracy: float
    correct_sentence_false_alarm_rate: float


@dataclass(frozen=True, slots=True)
class CalibrationPaths:
    dataset: Path
    manifest: Path
    raw_report: Path
    normalized_report: Path
    threshold_selection: Path


@dataclass(frozen=True, slots=True)
class CalibrationConfig:
    experiment_id: str
    dataset_id: str
    source_rows: tuple[CalibrationSourceIdentity, ...]
    threshold_profile: str
    thresholds: CalibrationThresholds
    warmup_repetitions: int
    measured_repetitions: int
    minimum_error_cases_per_key: int
    minimum_correct_cases_per_key: int
    paths: CalibrationPaths


@dataclass(frozen=True, slots=True)
class CalibrationManifest:
    dataset_id: str
    case_count: int
    reviewed_case_count: int
    dataset_sha256: str
    dataset_size_bytes: int


@dataclass(frozen=True, slots=True)
class ExpectedFinding:
    source: str
    category: str
    start: int
    end: int
    original: str
    suggestion: str


@dataclass(frozen=True, slots=True)
class CalibrationCase:
    id: str
    role: CalibrationRole
    primary_source_identity: str
    text: str
    expected_findings: tuple[ExpectedFinding, ...]


@dataclass(frozen=True, slots=True)
class CalibrationDataset:
    id: str
    cases: tuple[CalibrationCase, ...]
    sha256: str


@dataclass(frozen=True, slots=True)
class CalibrationCounts:
    error_cases: int
    correct_cases: int
    true_positive: int
    false_positive: int
    false_negative: int
    exact_span_matches: int
    exact_correction_matches: int
    correct_sentence_false_alarms: int

    def as_tuple(self) -> tuple[int, int, int, int, int, int, int, int]:
        return (
            self.error_cases,
            self.correct_cases,
            self.true_positive,
            self.false_positive,
            self.false_negative,
            self.exact_span_matches,
            self.exact_correction_matches,
            self.correct_sentence_false_alarms,
        )


@dataclass(frozen=True, slots=True)
class CalibrationMetrics:
    precision: float | None
    recall: float | None
    f1: float | None
    exact_span_accuracy: float | None
    exact_correction_accuracy: float | None
    correct_sentence_false_alarm_rate: float | None

    def as_tuple(
        self,
    ) -> tuple[
        float | None,
        float | None,
        float | None,
        float | None,
        float | None,
        float | None,
    ]:
        return (
            self.precision,
            self.recall,
            self.f1,
            self.exact_span_accuracy,
            self.exact_correction_accuracy,
            self.correct_sentence_false_alarm_rate,
        )


@dataclass(frozen=True, slots=True)
class KeyOutcome:
    identity: CalibrationSourceIdentity
    counts: CalibrationCounts
    metrics: CalibrationMetrics
    observed_confidence: float | None
    minimum_confidence: float | None
    verdict: KeyVerdict


@dataclass(frozen=True, slots=True)
class CalibrationRunAggregates:
    elapsed_seconds: float
    peak_memory_bytes: int


@dataclass(frozen=True, slots=True)
class CalibrationRunResult:
    repetition_hashes: tuple[str, ...]
    outcomes: tuple[KeyOutcome, ...]
    aggregates: CalibrationRunAggregates = CalibrationRunAggregates(0.0, 0)


@dataclass(frozen=True, slots=True)
class CalibrationReport:
    repetition_hashes: tuple[str, ...]
    outcomes: tuple[KeyOutcome, ...]
    aggregates: CalibrationRunAggregates | None
