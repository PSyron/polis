from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from polis import Finding
from polis.evaluation.holdout_admission import (
    HoldoutAdmissionError,
)
from polis.evaluation.holdout_admission import (
    load_external_admission as _load_external_admission,
)
from polis.evaluation.holdout_contract import canonical_sha256, parse_holdout_config
from polis.evaluation.holdout_dataset import (
    HoldoutDatasetError,
)
from polis.evaluation.holdout_dataset import (
    load_holdout_dataset as _load_holdout_dataset,
)
from polis.evaluation.holdout_execution import run_from_config as _run_from_config
from polis.evaluation.holdout_models import (
    AdmissionEvidence,
    HoldoutConfig,
    HoldoutDataset,
    JsonObject,
)
from polis.evaluation.holdout_report import normalized_report_bytes, parse_raw_report
from polis.evaluation.holdout_reservation import (
    HoldoutAlreadyConsumedError,
    load_reserved_dataset,
    reserve_consumption,
)
from polis.evaluation.holdout_sources import source_sha256

__all__ = ["HoldoutAdmissionError", "HoldoutAlreadyConsumedError"]

load_external_admission = _load_external_admission
run_from_config = _run_from_config

_SYNTHETIC_MERGE_COMMIT = "7" * 40
_SYNTHETIC_VERIFICATION_PAYLOAD_SHA256 = "9" * 64


class HoldoutDependencies(Protocol):
    observed_admission: AdmissionEvidence
    output_directory: Path

    def load_dataset(self, path: Path) -> tuple[str, ...]: ...
    def analyzer(self, text: str) -> tuple[Finding, ...]: ...
    def clock_ns(self) -> int: ...
    def rss_probe(self) -> int: ...
    def reserved_at(self) -> str: ...


@dataclass(frozen=True, slots=True)
class HoldoutRunResult:
    raw_report_path: Path
    normalized_report_path: Path


def _admit(
    config_document: JsonObject, config: HoldoutConfig, evidence: AdmissionEvidence
) -> None:
    requirements: tuple[tuple[str, str | bool | None, str | bool], ...] = (
        ("config_sha256", evidence.config_sha256, canonical_sha256(config_document)),
        ("source_sha256", evidence.source_sha256, source_sha256(config)),
        ("dataset_sha256", evidence.dataset_sha256, config.dataset.sha256),
        ("evaluated_merge_commit", evidence.merge_commit, _SYNTHETIC_MERGE_COMMIT),
        ("verification_verified", evidence.verification_verified, True),
        (
            "verification_reason",
            evidence.verification_reason,
            config.signature.required_reason,
        ),
        (
            "verification_payload_sha256",
            evidence.verification_payload_sha256,
            _SYNTHETIC_VERIFICATION_PAYLOAD_SHA256,
        ),
    )
    for name, actual, expected in requirements:
        if actual != expected:
            raise HoldoutAdmissionError(
                f"{name} does not match the authorized admission"
            )


def _empty_source_outcomes(config: HoldoutConfig) -> list[JsonObject]:
    return [
        {
            "identity": [
                item.source,
                item.category,
                item.operation,
                item.behavior_version,
                item.source_policy_version,
            ],
            "case_count": 0,
            "expected_findings": 0,
            "predicted_findings": 0,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "span_matches": 0,
            "correction_matches": 0,
            "correct_cases": 0,
            "alarmed_correct_cases": 0,
            "verdict": "insufficient_evidence",
        }
        for item in config.source_identities
    ]


def _synthetic_report(
    config: HoldoutConfig, evidence: AdmissionEvidence, peak_rss: int
) -> JsonObject:
    return {
        "schema_id": "polis.a-b-one-shot.raw-report",
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "identities": {
            "config_sha256": evidence.config_sha256,
            "dataset_sha256": evidence.dataset_sha256,
            "source_sha256": evidence.source_sha256,
            "wheel_sha256": "0" * 64,
            "sdist_sha256": "0" * 64,
            "lock_sha256": "0" * 64,
        },
        "quality": {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "exact_span_accuracy": 0.0,
            "exact_correction_accuracy": 0.0,
            "correct_sentence_false_alarm_rate": 0.0,
        },
        "performance": {
            "latency_ns": {"min": 0, "mean": 0, "p50": 0, "p95": 0, "max": 0},
            "throughput": {"cases_per_second": 0.0, "code_points_per_second": 0.0},
            "peak_rss_bytes": peak_rss,
        },
        "environment": {
            "os": "Darwin",
            "release": "0.0-test",
            "machine": "arm64",
            "python": "3.14.3",
            "package": "0.2.0",
            "morfeusz_dictionary": "pl.sgjp",
            "morfeusz_notice_sha256": "0" * 64,
        },
        "per_source": _empty_source_outcomes(config),
        "verdict": "insufficient_evidence",
    }


def load_holdout_dataset(path: Path, config: HoldoutConfig) -> HoldoutDataset:
    try:
        return _load_holdout_dataset(path, config)
    except HoldoutDatasetError as error:
        raise HoldoutAdmissionError(str(error)) from error


def run_synthetic_holdout(
    config_document: JsonObject, dependencies: HoldoutDependencies
) -> HoldoutRunResult:
    config = parse_holdout_config(config_document)
    evidence = dependencies.observed_admission
    _admit(config_document, config, evidence)
    identity: JsonObject = {
        "experiment_id": config.experiment_id,
        "config_sha256": evidence.config_sha256,
        "source_sha256": evidence.source_sha256,
        "dataset_sha256": evidence.dataset_sha256,
    }
    marker = dependencies.output_directory / config.paths.marker
    capability = reserve_consumption(
        marker, identity, reserved_at=dependencies.reserved_at()
    )
    cases = load_reserved_dataset(
        capability, lambda: dependencies.load_dataset(config.paths.dataset)
    )
    for text in cases:
        dependencies.analyzer(text)
    for _ in range(config.measured_repetitions):
        dependencies.clock_ns()
        for text in cases:
            dependencies.analyzer(text)
        dependencies.clock_ns()
    raw = _synthetic_report(config, evidence, dependencies.rss_probe())
    parsed = parse_raw_report(raw)
    raw_path = dependencies.output_directory / config.paths.raw_report
    normalized_path = dependencies.output_directory / config.paths.normalized_report
    raw_path.write_text(
        json.dumps(
            raw,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    normalized_path.write_bytes(normalized_report_bytes(parsed))
    return HoldoutRunResult(raw_path, normalized_path)
