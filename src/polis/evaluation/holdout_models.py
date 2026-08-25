from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]


class HoldoutContractError(ValueError):
    pass


class HoldoutAdmissionError(RuntimeError):
    pass


class HoldoutReportError(ValueError):
    pass


class HoldoutVerdict(StrEnum):
    PASS = "pass"
    FAIL_THRESHOLD = "fail_threshold"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class DatasetIdentity:
    sha256: str
    size_bytes: int
    case_count: int
    source_count: int
    license: str
    provenance: str
    review_status: str
    reviewed_case_count: int
    mode: str


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    source: str
    category: str
    operation: str
    behavior_version: str
    source_policy_version: str


@dataclass(frozen=True, slots=True)
class Taxonomy:
    categories: tuple[str, ...]
    roles: tuple[str, ...]
    features: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Thresholds:
    precision: float
    recall: float
    f1: float
    exact_span_accuracy: float
    exact_correction_accuracy: float
    correct_sentence_false_alarm_rate: float


@dataclass(frozen=True, slots=True)
class FailurePolicy:
    retry: str
    tuning: str
    non_pass_source: str


@dataclass(frozen=True, slots=True)
class SignatureRequirements:
    method: str
    status: str
    required_verified: bool
    required_reason: str
    required_bindings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AuthorizationSignatureRequirements:
    method: str
    signer_identity: str
    namespace: str
    trusted_public_key: str
    trusted_key_fingerprint: str
    signed_payload: str
    host_system: str
    host_machine: str
    ssh_keygen_path: Path


@dataclass(frozen=True, slots=True)
class HoldoutPaths:
    dataset: Path
    merge_verification: Path
    run_authorization: Path
    run_authorization_signature: Path
    marker: Path
    raw_report: Path
    normalized_report: Path
    result_manifest: Path


@dataclass(frozen=True, slots=True)
class HoldoutSchemas:
    dataset: str
    merge_verification: str
    run_authorization: str


@dataclass(frozen=True, slots=True)
class HoldoutConfig:
    experiment_id: str
    exact_command: str
    warmup_repetitions: int
    measured_repetitions: int
    dataset: DatasetIdentity
    taxonomy: Taxonomy
    metrics: tuple[str, ...]
    thresholds: Thresholds
    source_identities: tuple[SourceIdentity, ...]
    exclusions: tuple[str, ...]
    failure_policy: FailurePolicy
    signature: SignatureRequirements
    authorization_signature: AuthorizationSignatureRequirements
    external_schemas: HoldoutSchemas
    paths: HoldoutPaths


@dataclass(frozen=True, slots=True)
class AdmissionEvidence:
    config_sha256: str
    source_sha256: str
    source_tree_sha256: str
    dataset_sha256: str
    merge_commit: str | None
    verification_verified: bool | None
    verification_reason: str | None
    verification_payload_sha256: str | None


@dataclass(frozen=True, slots=True)
class HoldoutExpectedFinding:
    category: str
    start: int
    end: int
    original: str
    suggestion: str
    source: str


@dataclass(frozen=True, slots=True)
class HoldoutCase:
    id: str
    role: str
    targets: tuple[str, ...]
    features: tuple[str, ...]
    text: str
    expected_findings: tuple[HoldoutExpectedFinding, ...]


@dataclass(frozen=True, slots=True)
class HoldoutDataset:
    id: str
    cases: tuple[HoldoutCase, ...]
    sha256: str


@dataclass(frozen=True, slots=True)
class HoldoutQuality:
    precision: float
    recall: float
    f1: float
    exact_span_accuracy: float
    exact_correction_accuracy: float
    correct_sentence_false_alarm_rate: float


@dataclass(frozen=True, slots=True)
class HoldoutPerformance:
    latency_ns: JsonObject
    throughput: JsonObject
    peak_rss_bytes: int


@dataclass(frozen=True, slots=True)
class HoldoutSourceOutcome:
    identity: tuple[str, str, str, str, str]
    case_count: int
    expected_findings: int
    predicted_findings: int
    true_positives: int
    false_positives: int
    false_negatives: int
    span_matches: int
    correction_matches: int
    correct_cases: int
    alarmed_correct_cases: int
    verdict: str


@dataclass(frozen=True, slots=True)
class RawReport:
    schema_id: str
    schema_version: int
    experiment_id: str
    identities: JsonObject
    quality: HoldoutQuality
    performance: HoldoutPerformance
    environment: JsonObject
    per_source: tuple[HoldoutSourceOutcome, ...]
    verdict: str
