from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from polis.evaluation.calibration_admission import (
    admit_frozen_calibration,
    verify_calibration_review_membership,
)
from polis.evaluation.calibration_commitment import case_payload_sha256
from polis.evaluation.calibration_dataset import load_calibration_dataset_bytes
from polis.evaluation.calibration_freeze_models import (
    DatasetKind,
    FrozenDatasetManifest,
)
from polis.evaluation.calibration_json import fail
from polis.evaluation.calibration_manifest import parse_frozen_dataset_manifest
from polis.evaluation.calibration_models import (
    CalibrationConfig,
    CalibrationPaths,
    CalibrationThresholds,
)
from polis.evaluation.calibration_operator_io import _SecureRepository
from polis.evaluation.calibration_overlap import DatasetLike, scan_dataset_pii
from polis.evaluation.calibration_review import parse_dataset_review
from polis.evaluation.calibration_sources import SOURCE_ROWS
from polis.evaluation.holdout_v2_dataset import load_holdout_v2_dataset_bytes

_EXPERIMENT = ("experiments", "a-b-qualification-v2")
_CALIBRATION = (".omo", "sealed", "a-b-calibration-v2-v1")
_HOLDOUT = (".omo", "sealed", "a-b-holdout-v2-v1")


@dataclass(frozen=True, slots=True)
class _ValidatedDataset:
    dataset: DatasetLike
    manifest: FrozenDatasetManifest


def _config() -> CalibrationConfig:
    names = ("dataset", "manifest", "raw", "normalized", "selection")
    return CalibrationConfig(
        "polis-a-b-qualification-v2-v1",
        "polis-a-b-calibration-v2-v1",
        SOURCE_ROWS,
        "active-baseline-v1",
        CalibrationThresholds(1.0, 5 / 7, 5 / 6, 5 / 7, 1.0, 0.0),
        1,
        5,
        20,
        40,
        CalibrationPaths(*(Path(name) for name in names)),
    )


def _validated(repo: _SecureRepository, kind: DatasetKind) -> _ValidatedDataset:
    root = _CALIBRATION if kind == "calibration" else _HOLDOUT
    dataset_bytes = repo.read((*root, "cases.json"), expected_mode=0o600)
    manifest_bytes = repo.read(
        (*_EXPERIMENT, f"{kind}.dataset.manifest.json"), expected_mode=0o644
    )
    review_bytes = repo.read((*_EXPERIMENT, f"{kind}.review.json"), expected_mode=0o644)
    payload_bytes = repo.read((*root, "review.payload.json"), expected_mode=0o600)
    pii_bytes = repo.read((*root, "pii-scan.json"), expected_mode=0o600)
    manifest = parse_frozen_dataset_manifest(manifest_bytes, kind)
    review = parse_dataset_review(review_bytes, kind, payload_bytes)
    if hashlib.sha256(pii_bytes).hexdigest() != manifest.pii_scan_sha256:
        fail("PII scan does not match the frozen manifest")
    if kind == "calibration":
        admitted = admit_frozen_calibration(manifest, review)
        calibration = load_calibration_dataset_bytes(dataset_bytes, admitted, _config())
        verify_calibration_review_membership(calibration, review)
        dataset: DatasetLike = calibration
    else:
        holdout = load_holdout_v2_dataset_bytes(dataset_bytes, manifest)
        reviewed = tuple(case.case_id for case in review.case_reviews)
        payloads = tuple(case.case_payload_sha256 for case in review.case_reviews)
        if reviewed != tuple(case.id for case in holdout.cases) or payloads != tuple(
            case_payload_sha256(case) for case in holdout.cases
        ):
            fail("holdout dataset and review membership do not match")
        dataset = holdout
    scan_dataset_pii(dataset)
    return _ValidatedDataset(dataset, manifest)
