from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path

from polis.core import Finding
from polis.evaluation.calibration_models import (
    AnalyzerCallable,
    AnalyzerFactory,
    CalibrationConfig,
    CalibrationContractError,
    CalibrationDataset,
    CalibrationIntegrityError,
    CalibrationManifest,
    CalibrationRunResult,
    JsonValue,
)
from polis.evaluation.calibration_scoring import score_calibration
from polis.evaluation.calibration_sources import SOURCE_ROWS

type FindingsByCase = dict[str, tuple[Finding, ...]]


def _validate_inputs(
    config: CalibrationConfig,
    manifest: CalibrationManifest,
    dataset: CalibrationDataset,
) -> None:
    if (
        config.source_rows != SOURCE_ROWS
        or config.warmup_repetitions != 1
        or config.measured_repetitions != 5
        or config.minimum_error_cases_per_key != 20
        or config.minimum_correct_cases_per_key != 40
    ):
        raise CalibrationContractError("calibration run configuration drifted")
    if (
        manifest.dataset_id != config.dataset_id
        or dataset.id != config.dataset_id
        or dataset.sha256 != manifest.dataset_sha256
        or manifest.case_count != 1200
        or manifest.reviewed_case_count != 1200
        or len(dataset.cases) != 1200
    ):
        raise CalibrationContractError("calibration run dataset identity drifted")
    counts: dict[tuple[str, str], int] = {}
    for case in dataset.cases:
        key = (case.primary_source_identity, case.role)
        counts[key] = counts.get(key, 0) + 1
    if any(
        counts.get((row.source, "error"), 0) != 20
        or counts.get((row.source, "correct"), 0) != 40
        for row in SOURCE_ROWS
    ):
        raise CalibrationContractError("calibration run denominators drifted")


def _finding_row(finding: Finding) -> list[JsonValue]:
    return [
        finding.id,
        finding.category.value,
        finding.severity.value,
        finding.message,
        finding.explanation,
        finding.original,
        finding.suggestion,
        finding.start,
        finding.end,
        finding.confidence.value,
        str(finding.source),
    ]


def _findings_sha256(
    dataset: CalibrationDataset,
    findings: Mapping[str, tuple[Finding, ...]],
) -> str:
    payload: list[JsonValue] = [
        [case.id, [_finding_row(item) for item in findings.get(case.id, ())]]
        for case in dataset.cases
    ]
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(raw).hexdigest()


def _measure_once(
    dataset: CalibrationDataset,
    analyzer: AnalyzerCallable,
) -> FindingsByCase:
    return {case.id: analyzer(case.text) for case in dataset.cases}


def run_synthetic_calibration(
    config: CalibrationConfig,
    manifest: CalibrationManifest,
    dataset: CalibrationDataset,
    analyzer: AnalyzerCallable,
) -> CalibrationRunResult:
    _validate_inputs(config, manifest, dataset)
    for _ in range(config.warmup_repetitions):
        for case in dataset.cases:
            analyzer(case.text)
    measured = tuple(
        _measure_once(dataset, analyzer) for _ in range(config.measured_repetitions)
    )
    hashes = tuple(_findings_sha256(dataset, findings) for findings in measured)
    if len(set(hashes)) != 1:
        raise CalibrationIntegrityError(
            "calibration findings changed between measured repetitions"
        )
    return CalibrationRunResult(
        repetition_hashes=hashes,
        outcomes=score_calibration(dataset, measured[0], config),
    )


def run_calibration(config_path: Path) -> int:
    from polis.evaluation.calibration_runner_io import _run_calibration_files

    implementation: Callable[[Path], int] = _run_calibration_files
    return implementation(config_path)


def _run_calibration_for_test(
    config_path: Path,
    analyzer_factory: AnalyzerFactory,
    repository_root: Path,
) -> int:
    from polis.evaluation.calibration_runner_io import _run_calibration_files_for_test

    implementation: Callable[[Path, AnalyzerFactory, Path], int] = (
        _run_calibration_files_for_test
    )
    return implementation(config_path, analyzer_factory, repository_root)
