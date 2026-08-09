from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Protocol

from tests.calibration_test_helpers import (
    canonical_bytes,
    synthetic_config,
    synthetic_dataset,
    synthetic_manifest,
)
from tests.test_calibration_scoring import _inputs

from polis.core import Confidence, Finding
from polis.evaluation.calibration_contract import parse_calibration_manifest
from polis.evaluation.calibration_models import (
    CalibrationConfig,
    CalibrationDataset,
    CalibrationManifest,
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
    raw = canonical_bytes(synthetic_dataset())
    experiment = root / "experiments/a-b-qualification-v2"
    sealed = root / ".omo/sealed/a-b-calibration-v2-v1"
    experiment.mkdir(parents=True)
    sealed.mkdir(parents=True)
    config_path = experiment / "config.json"
    config_path.write_bytes(canonical_bytes(synthetic_config()))
    (experiment / "calibration.dataset.manifest.json").write_bytes(
        canonical_bytes(synthetic_manifest(raw))
    )
    (sealed / "cases.json").write_bytes(raw)
    return Path("experiments/a-b-qualification-v2/config.json")


def output_paths(root: Path) -> tuple[Path, Path, Path]:
    experiment = root / "experiments/a-b-qualification-v2"
    return (
        experiment / "calibration.report.json",
        experiment / "calibration.normalized-report.json",
        experiment / "threshold-selection.json",
    )
