from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from tests.calibration_test_helpers import (
    canonical_bytes,
    synthetic_config,
    synthetic_dataset,
    synthetic_manifest,
)
from tests.independent_dataset_test_helpers import (
    dataset_manifest,
    dataset_review,
    recompute_review_approval,
    review_payload_bytes,
)
from tests.test_calibration_scoring import _inputs

from polis.core import Confidence, Finding
from polis.evaluation.calibration_commitment import CalibrationArtifactCommitment
from polis.evaluation.calibration_contract import parse_calibration_manifest
from polis.evaluation.calibration_models import (
    CalibrationConfig,
    CalibrationDataset,
    CalibrationManifest,
    JsonObject,
)

type FindingsByText = dict[str, tuple[Finding, ...]]


class AnalyzerLike(Protocol):
    def __call__(self, text: str) -> tuple[Finding, ...]: ...


class RecordingAnalyzer:
    calls: list[str]

    def __init__(
        self,
        findings: FindingsByText,
        *,
        drift_call: int | None = None,
        failure_call: int | None = None,
    ) -> None:
        self._findings = findings
        self._drift_call = drift_call
        self._failure_call = failure_call
        self.calls = []

    def __call__(self, text: str) -> tuple[Finding, ...]:
        self.calls.append(text)
        call = len(self.calls)
        if call == self._failure_call:
            raise SyntheticAnalyzerError("synthetic analyzer failure")
        findings = self._findings[text]
        if call == self._drift_call and findings:
            first, *remaining = findings
            drifted = replace(first, confidence=Confidence(0.5))
            return (drifted, *remaining)
        return findings


class RecordingFactory:
    calls: int

    def __init__(self, analyzer: AnalyzerLike) -> None:
        self.analyzer = analyzer
        self.calls = 0

    def __call__(self) -> AnalyzerLike:
        self.calls += 1
        return self.analyzer


class SyntheticAnalyzerError(RuntimeError):
    pass


def read_json(path: Path) -> JsonObject:
    value = json.loads(path.read_bytes())
    assert isinstance(value, dict)
    return value


def refresh_review_binding(root: Path, review: JsonObject) -> None:
    recompute_review_approval(review)
    review_bytes = canonical_bytes(review)
    review_path = root / "experiments/a-b-qualification-v2/calibration.review.json"
    review_path.write_bytes(review_bytes)
    manifest_path = review_path.with_name("calibration.dataset.manifest.json")
    manifest = read_json(manifest_path)
    manifest["review_manifest_sha256"] = hashlib.sha256(review_bytes).hexdigest()
    manifest_path.write_bytes(canonical_bytes(manifest))


def refresh_dataset_binding(root: Path, dataset: JsonObject) -> None:
    dataset_bytes = canonical_bytes(dataset)
    experiment = root / "experiments/a-b-qualification-v2"
    dataset_path = root / ".omo/sealed/a-b-calibration-v2-v1/cases.json"
    dataset_path.write_bytes(dataset_bytes)
    review = read_json(experiment / "calibration.review.json")
    cases = dataset["cases"]
    case_reviews = review["case_reviews"]
    assert isinstance(cases, list) and isinstance(case_reviews, list)
    assert len(cases) == len(case_reviews)
    for case, case_review in zip(cases, case_reviews, strict=True):
        assert isinstance(case, dict) and isinstance(case_review, dict)
        case_review["case_payload_sha256"] = hashlib.sha256(
            canonical_bytes(case)
        ).hexdigest()
    review["dataset_sha256"] = hashlib.sha256(dataset_bytes).hexdigest()
    payload_bytes = canonical_bytes(case_reviews)
    (root / ".omo/sealed/a-b-calibration-v2-v1/review.payload.json").write_bytes(
        payload_bytes
    )
    review["review_payload_sha256"] = hashlib.sha256(payload_bytes).hexdigest()
    refresh_review_binding(root, review)
    manifest_path = experiment / "calibration.dataset.manifest.json"
    manifest = read_json(manifest_path)
    manifest["dataset_sha256"] = hashlib.sha256(dataset_bytes).hexdigest()
    manifest["dataset_size_bytes"] = len(dataset_bytes)
    manifest["review_payload_sha256"] = review["review_payload_sha256"]
    manifest_path.write_bytes(canonical_bytes(manifest))


def workspace_commitment(root: Path) -> CalibrationArtifactCommitment:
    experiment = root / "experiments/a-b-qualification-v2"
    paths = (
        root / ".omo/sealed/a-b-calibration-v2-v1/cases.json",
        experiment / "calibration.dataset.manifest.json",
        experiment / "calibration.review.json",
        root / ".omo/sealed/a-b-calibration-v2-v1/review.payload.json",
    )
    digests = tuple(hashlib.sha256(path.read_bytes()).hexdigest() for path in paths)
    return CalibrationArtifactCommitment(*digests)


def synthetic_run_inputs() -> tuple[
    CalibrationConfig,
    CalibrationManifest,
    CalibrationDataset,
    FindingsByText,
]:
    dataset, config, findings_by_case = _inputs()
    raw = canonical_bytes(synthetic_dataset())
    manifest = parse_calibration_manifest(canonical_bytes(synthetic_manifest(raw)))
    findings = {case.text: findings_by_case.get(case.id, ()) for case in dataset.cases}
    return config, manifest, dataset, findings


def write_workspace(root: Path) -> Path:
    document = synthetic_dataset()
    cases = document["cases"]
    assert isinstance(cases, list)
    for case in cases:
        assert isinstance(case, dict)
        case_id = case["id"]
        assert isinstance(case_id, str)
        role, source_index, case_index = case_id.split("-")
        case["id"] = f"cal-v2-{source_index}-{role}-{case_index}"
    raw = canonical_bytes(document)
    review = dataset_review("calibration", raw)
    review_bytes = canonical_bytes(review)
    payload = review_payload_bytes(review)
    manifest = dataset_manifest("calibration", raw)
    manifest["review_manifest_sha256"] = hashlib.sha256(review_bytes).hexdigest()
    manifest["review_payload_sha256"] = hashlib.sha256(payload).hexdigest()
    experiment = root / "experiments/a-b-qualification-v2"
    sealed = root / ".omo/sealed/a-b-calibration-v2-v1"
    experiment.mkdir(parents=True)
    sealed.mkdir(parents=True)
    config_path = experiment / "config.json"
    config_path.write_bytes(canonical_bytes(synthetic_config()))
    (experiment / "calibration.dataset.manifest.json").write_bytes(
        canonical_bytes(manifest)
    )
    (experiment / "calibration.review.json").write_bytes(review_bytes)
    (sealed / "review.payload.json").write_bytes(payload)
    (sealed / "cases.json").write_bytes(raw)
    return Path("experiments/a-b-qualification-v2/config.json")


def write_legacy_workspace(root: Path) -> Path:
    config_path = write_workspace(root)
    dataset = root / ".omo/sealed/a-b-calibration-v2-v1/cases.json"
    manifest = root / config_path.parent / "calibration.dataset.manifest.json"
    manifest.write_bytes(canonical_bytes(synthetic_manifest(dataset.read_bytes())))
    return config_path


def output_paths(root: Path) -> tuple[Path, Path, Path]:
    experiment = root / "experiments/a-b-qualification-v2"
    return (
        experiment / "calibration.report.json",
        experiment / "calibration.normalized-report.json",
        experiment / "threshold-selection.json",
    )
