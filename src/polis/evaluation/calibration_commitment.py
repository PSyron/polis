from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Final

from polis.evaluation.calibration_json import canonical_bytes, fail
from polis.evaluation.calibration_models import (
    CalibrationCase,
    JsonObject,
    JsonValue,
)


@dataclass(frozen=True, slots=True)
class CalibrationArtifactCommitment:
    dataset_sha256: str
    manifest_sha256: str
    review_sha256: str
    review_payload_sha256: str


CALIBRATION_ARTIFACT_COMMITMENT: Final = CalibrationArtifactCommitment(
    "0a334b1b494c5e7de1419d79a348d34b1843f88fb7de664c1dcc22e666375fb1",
    "62d47cce9f1e3e0b01a20a250766563a7ab869a240cf4ca18cd2c4e43070c0e3",
    "5d02e95e29d635015074b0bf33e3d47dfd20f74c676b6b24b36d84fb939f2d68",
    "a711047a33c765176c79acdb79aa07ed633e65527aa7b02d4bde2cf5b011d666",
)


def _finding_payload(case: CalibrationCase) -> list[JsonValue]:
    return [
        {
            "source": finding.source,
            "category": finding.category,
            "start": finding.start,
            "end": finding.end,
            "original": finding.original,
            "suggestion": finding.suggestion,
        }
        for finding in case.expected_findings
    ]


def case_payload_sha256(case: CalibrationCase) -> str:
    payload: JsonObject = {
        "id": case.id,
        "role": case.role,
        "primary_source_identity": case.primary_source_identity,
        "text": case.text,
        "expected_findings": _finding_payload(case),
    }
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def verify_artifact_commitment(
    commitment: CalibrationArtifactCommitment | None,
    *,
    dataset_sha256: str,
    manifest_bytes: bytes,
    review_bytes: bytes,
    review_payload_bytes: bytes,
) -> None:
    if commitment is None:
        fail("calibration artifact commitment is not frozen")
    observed = CalibrationArtifactCommitment(
        dataset_sha256,
        hashlib.sha256(manifest_bytes).hexdigest(),
        hashlib.sha256(review_bytes).hexdigest(),
        hashlib.sha256(review_payload_bytes).hexdigest(),
    )
    if observed != commitment:
        fail("calibration artifacts do not match the frozen commitment")
