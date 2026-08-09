from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import pytest

from polis.evaluation.calibration_commitment import CALIBRATION_ARTIFACT_COMMITMENT
from polis.evaluation.calibration_json import canonical_bytes
from polis.evaluation.calibration_manifest import parse_frozen_dataset_manifest
from polis.evaluation.calibration_models import JsonObject, JsonValue
from polis.evaluation.calibration_review import parse_dataset_review

type DatasetKind = Literal["calibration", "holdout"]

_EXPERIMENT = Path("experiments/a-b-qualification-v2")
_EXPECTED = {
    "calibration": (
        "0a334b1b494c5e7de1419d79a348d34b1843f88fb7de664c1dcc22e666375fb1",
        220_937,
        1_073,
    ),
    "holdout": (
        "eeeffe8c66286e124369629f5399b5224c1f016b1777556605fb98a42d02edc8",
        122_018,
        530,
    ),
}


def _document(path: Path) -> JsonObject:
    raw: JsonValue = json.loads(path.read_bytes())
    assert isinstance(raw, dict)
    return raw


def _metadata(kind: DatasetKind) -> tuple[bytes, bytes]:
    return (
        (_EXPERIMENT / f"{kind}.review.json").read_bytes(),
        (_EXPERIMENT / f"{kind}.dataset.manifest.json").read_bytes(),
    )


def _all_keys(value: JsonValue) -> set[str]:
    match value:
        case dict() as mapping:
            return set(mapping) | {
                key for nested in mapping.values() for key in _all_keys(nested)
            }
        case list() as values:
            return {key for nested in values for key in _all_keys(nested)}
        case _:
            return set()


@pytest.mark.parametrize("kind", ["calibration", "holdout"])
def test_tracked_review_and_manifest_parse_when_artifacts_are_frozen(
    kind: DatasetKind,
) -> None:
    review_bytes, manifest_bytes = _metadata(kind)
    review_document = _document(_EXPERIMENT / f"{kind}.review.json")
    payload_bytes = canonical_bytes(review_document["case_reviews"])

    review = parse_dataset_review(review_bytes, kind, payload_bytes)
    manifest = parse_frozen_dataset_manifest(manifest_bytes, kind)

    dataset_sha256, dataset_size_bytes, case_count = _EXPECTED[kind]
    assert review.dataset_sha256 == dataset_sha256
    assert len(review.case_reviews) == case_count
    assert manifest.dataset_sha256 == dataset_sha256
    assert manifest.dataset_size_bytes == dataset_size_bytes
    assert manifest.review_manifest_sha256 == hashlib.sha256(review_bytes).hexdigest()
    assert manifest.review_payload_sha256 == hashlib.sha256(payload_bytes).hexdigest()


@pytest.mark.parametrize("kind", ["calibration", "holdout"])
def test_tracked_review_metadata_is_canonical_and_plaintext_free(
    kind: DatasetKind,
) -> None:
    review_path = _EXPERIMENT / f"{kind}.review.json"
    manifest_path = _EXPERIMENT / f"{kind}.dataset.manifest.json"
    review = _document(review_path)
    manifest = _document(manifest_path)

    assert review_path.read_bytes() == canonical_bytes(review)
    assert manifest_path.read_bytes() == canonical_bytes(manifest)
    forbidden = {"text", "original", "suggestion", "expected_findings"}
    assert not forbidden & _all_keys(review)
    assert not forbidden & _all_keys(manifest)
    assert not (_EXPERIMENT / "cases.json").exists()


def test_overlap_report_freezes_only_the_approved_finite_classification() -> None:
    path = _EXPERIMENT / "dataset-overlap.report.json"
    report = _document(path)

    assert path.read_bytes() == canonical_bytes(report)
    assert report["preregistered_finite_exact_matches"] == 78
    assert report["finite_match_histogram"] == {
        "calibration_calibration": 18,
        "calibration_public_conservative": 0,
        "calibration_public_quality": 39,
        "calibration_public_v1": 21,
    }
    assert report["unexpected_exact_collisions"] == 0
    assert report["near_collisions"] == 0
    assert report["verdict"] == "APPROVE"
    assert not {"case_id", "text", "hmac", "fingerprint"} & _all_keys(report)


def test_freeze_receipt_binds_the_complete_metadata_dag_and_role_table() -> None:
    path = _EXPERIMENT / "freeze-verification.json"
    receipt = _document(path)
    overlap = (_EXPERIMENT / "dataset-overlap.report.json").read_bytes()

    assert path.read_bytes() == canonical_bytes(receipt)
    artifacts = receipt["artifacts"]
    assert isinstance(artifacts, dict)
    assert artifacts["overlap_report_sha256"] == hashlib.sha256(overlap).hexdigest()
    assignment = receipt["assignment"]
    assert isinstance(assignment, dict)
    roles = assignment["role_identities"]
    assert isinstance(roles, list)
    assert len(roles) == len(set(roles)) == 16
    assert receipt["verdict"] == "APPROVE"
    assert not {"case_id", "text", "hmac", "fingerprint"} & _all_keys(receipt)


def test_public_calibration_runner_is_bound_to_the_frozen_artifact_set() -> None:
    commitment = CALIBRATION_ARTIFACT_COMMITMENT

    assert commitment is not None
    assert commitment.dataset_sha256 == _EXPECTED["calibration"][0]
    assert (
        commitment.manifest_sha256
        == hashlib.sha256(
            (_EXPERIMENT / "calibration.dataset.manifest.json").read_bytes()
        ).hexdigest()
    )
    assert (
        commitment.review_sha256
        == hashlib.sha256(
            (_EXPERIMENT / "calibration.review.json").read_bytes()
        ).hexdigest()
    )
