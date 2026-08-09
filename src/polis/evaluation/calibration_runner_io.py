from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Literal, Protocol

from polis.core import AnalysisResult, Finding
from polis.evaluation.calibration_admission import (
    admit_frozen_calibration,
    verify_calibration_review_membership,
)
from polis.evaluation.calibration_commitment import (
    CALIBRATION_ARTIFACT_COMMITMENT,
    CalibrationArtifactCommitment,
    verify_artifact_commitment,
)
from polis.evaluation.calibration_contract import parse_calibration_config
from polis.evaluation.calibration_dataset import load_calibration_dataset_bytes
from polis.evaluation.calibration_manifest import parse_frozen_dataset_manifest
from polis.evaluation.calibration_models import (
    AnalyzerCallable,
    AnalyzerFactory,
    CalibrationContractError,
    CalibrationOutputError,
)
from polis.evaluation.calibration_offline import _offline_socket_boundary
from polis.evaluation.calibration_paths import (
    CALIBRATION_REVIEW,
    CALIBRATION_REVIEW_PAYLOAD,
    require_canonical_calibration_config,
)
from polis.evaluation.calibration_report import (
    normalized_report_bytes,
    parse_raw_report,
    raw_report_bytes,
    threshold_selection_bytes,
)
from polis.evaluation.calibration_review import parse_dataset_review
from polis.evaluation.calibration_runner import _run_admitted_calibration
from polis.evaluation.calibration_sources import validate_live_sources


class _Analyze(Protocol):
    def __call__(self, text: str) -> AnalysisResult: ...


type _CommitmentInput = (
    CalibrationArtifactCommitment | Literal["synthetic-current"] | None
)


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
    commitment: _CommitmentInput,
    repository_root: Path | None = None,
) -> int:
    require_canonical_calibration_config(config_path, repository_root=repository_root)
    root = repository_root or Path.cwd()

    with _offline_socket_boundary():
        return _run_admitted_files(config_path, analyzer_factory, commitment, root)


def _run_admitted_files(
    config_path: Path,
    analyzer_factory: AnalyzerFactory,
    commitment: _CommitmentInput,
    root: Path,
) -> int:
    config = parse_calibration_config(_read(config_path, "calibration config"))
    validate_live_sources()
    manifest_path = root / config.paths.manifest
    dataset_path = root / config.paths.dataset
    manifest_bytes = _read(manifest_path, "calibration manifest")
    frozen_manifest = parse_frozen_dataset_manifest(manifest_bytes, "calibration")
    review_bytes = _read(root / CALIBRATION_REVIEW, "calibration review")
    review_payload_bytes = _read(
        root / CALIBRATION_REVIEW_PAYLOAD, "calibration review payload"
    )
    review = parse_dataset_review(
        review_bytes,
        "calibration",
        review_payload_bytes,
    )
    if commitment == "synthetic-current":
        commitment = CalibrationArtifactCommitment(
            frozen_manifest.dataset_sha256,
            hashlib.sha256(manifest_bytes).hexdigest(),
            hashlib.sha256(review_bytes).hexdigest(),
            hashlib.sha256(review_payload_bytes).hexdigest(),
        )
    verify_artifact_commitment(
        commitment,
        dataset_sha256=frozen_manifest.dataset_sha256,
        manifest_bytes=manifest_bytes,
        review_bytes=review_bytes,
        review_payload_bytes=review_payload_bytes,
    )
    manifest = admit_frozen_calibration(frozen_manifest, review)
    dataset = load_calibration_dataset_bytes(
        _read(dataset_path, "calibration dataset"), manifest, config
    )
    verify_calibration_review_membership(dataset, review)
    paths = (
        root / config.paths.raw_report,
        root / config.paths.normalized_report,
        root / config.paths.threshold_selection,
    )
    if any(path.exists() for path in paths):
        raise CalibrationOutputError("calibration output already exists")
    result = _run_admitted_calibration(config, manifest, dataset, analyzer_factory())
    raw = raw_report_bytes(result)
    normalized = normalized_report_bytes(parse_raw_report(raw))
    selection = threshold_selection_bytes(result)
    _write_reports(tuple(zip(paths, (raw, normalized, selection), strict=True)))
    return 0


def _run_calibration_files(config_path: Path) -> int:
    return _run_files(config_path, _default_factory, CALIBRATION_ARTIFACT_COMMITMENT)


def _run_calibration_files_for_test(
    config_path: Path,
    analyzer_factory: AnalyzerFactory,
    repository_root: Path,
) -> int:
    return _run_files(
        config_path,
        analyzer_factory,
        "synthetic-current",
        repository_root,
    )


def _run_calibration_files_with_commitment_for_test(
    config_path: Path,
    analyzer_factory: AnalyzerFactory,
    repository_root: Path,
    commitment: CalibrationArtifactCommitment,
) -> int:
    return _run_files(config_path, analyzer_factory, commitment, repository_root)
