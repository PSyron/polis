from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from polis.core import AnalysisResult, Finding
from polis.evaluation.calibration_contract import (
    parse_calibration_config,
    parse_calibration_manifest,
)
from polis.evaluation.calibration_dataset import load_calibration_dataset_bytes
from polis.evaluation.calibration_models import (
    AnalyzerCallable,
    AnalyzerFactory,
    CalibrationContractError,
    CalibrationOutputError,
)
from polis.evaluation.calibration_offline import _offline_socket_boundary
from polis.evaluation.calibration_paths import require_canonical_calibration_config
from polis.evaluation.calibration_report import (
    normalized_report_bytes,
    parse_raw_report,
    raw_report_bytes,
    threshold_selection_bytes,
)
from polis.evaluation.calibration_runner import run_synthetic_calibration
from polis.evaluation.calibration_sources import validate_live_sources


class _Analyze(Protocol):
    def __call__(self, text: str) -> AnalysisResult: ...


def _default_factory() -> AnalyzerCallable:
    from polis import Analyzer
    from polis.analyzer import AnalyzerConfig

    analyzer = Analyzer(AnalyzerConfig())
    analyze_impl: _Analyze = analyzer.analyze

    def analyze(text: str) -> tuple[Finding, ...]:
        issues: tuple[Finding, ...] = analyze_impl(text).issues
        return issues

    return analyze


def _read(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as error:
        raise CalibrationContractError(f"{label} is unavailable") from error


def _write_all(descriptor: int, content: bytes) -> None:
    remaining = memoryview(content)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("calibration output write made no progress")
        remaining = remaining[written:]


def _write_exclusive(path: Path, content: bytes) -> None:
    created = False
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        try:
            _write_all(descriptor, content)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except OSError:
        if created:
            path.unlink(missing_ok=True)
        raise


def _write_reports(outputs: tuple[tuple[Path, bytes], ...]) -> None:
    created: list[Path] = []
    try:
        for path, content in outputs:
            _write_exclusive(path, content)
            created.append(path)
    except OSError as error:
        for path in created:
            path.unlink(missing_ok=True)
        raise CalibrationOutputError("exclusive calibration output failed") from error


def _run_files(
    config_path: Path,
    analyzer_factory: AnalyzerFactory,
    repository_root: Path | None = None,
) -> int:
    require_canonical_calibration_config(config_path, repository_root=repository_root)
    root = repository_root or Path.cwd()

    with _offline_socket_boundary():
        return _run_admitted_files(config_path, analyzer_factory, root)


def _run_admitted_files(
    config_path: Path, analyzer_factory: AnalyzerFactory, root: Path
) -> int:
    config = parse_calibration_config(_read(config_path, "calibration config"))
    validate_live_sources()
    manifest_path = root / config.paths.manifest
    dataset_path = root / config.paths.dataset
    manifest = parse_calibration_manifest(_read(manifest_path, "calibration manifest"))
    dataset = load_calibration_dataset_bytes(
        _read(dataset_path, "calibration dataset"), manifest, config
    )
    paths = (
        root / config.paths.raw_report,
        root / config.paths.normalized_report,
        root / config.paths.threshold_selection,
    )
    if any(path.exists() for path in paths):
        raise CalibrationOutputError("calibration output already exists")
    result = run_synthetic_calibration(config, manifest, dataset, analyzer_factory())
    raw = raw_report_bytes(result)
    normalized = normalized_report_bytes(parse_raw_report(raw))
    selection = threshold_selection_bytes(result)
    _write_reports(tuple(zip(paths, (raw, normalized, selection), strict=True)))
    return 0


def _run_calibration_files(config_path: Path) -> int:
    return _run_files(config_path, _default_factory)


def _run_calibration_files_for_test(
    config_path: Path,
    analyzer_factory: AnalyzerFactory,
    repository_root: Path,
) -> int:
    return _run_files(config_path, analyzer_factory, repository_root)
