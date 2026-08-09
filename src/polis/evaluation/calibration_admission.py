from __future__ import annotations

import hashlib

from polis.evaluation.calibration_commitment import case_payload_sha256
from polis.evaluation.calibration_denominators import expected_case_rows
from polis.evaluation.calibration_freeze_models import (
    DatasetReview,
    FrozenDatasetManifest,
)
from polis.evaluation.calibration_json import fail
from polis.evaluation.calibration_models import CalibrationDataset, CalibrationManifest


def admit_frozen_calibration(
    manifest: FrozenDatasetManifest,
    review: DatasetReview,
) -> CalibrationManifest:
    if (
        manifest.kind != "calibration"
        or review.kind != "calibration"
        or manifest.dataset_id != review.dataset_id
        or manifest.dataset_sha256 != review.dataset_sha256
        or manifest.case_count != len(review.case_reviews)
        or manifest.author_identities != review.author_identities
        or manifest.custodian_identity != review.custodian_identity
        or manifest.reviewer_identity != review.reviewer_identity
        or manifest.review_manifest_sha256 != review.document_sha256
        or manifest.review_payload_sha256 != review.review_payload_sha256
        or hashlib.sha256(review.review_payload_bytes).hexdigest()
        != review.review_payload_sha256
        or manifest.assignment != review.assignment
    ):
        fail("calibration manifest and review do not share frozen bindings")
    return CalibrationManifest(
        manifest.dataset_id,
        manifest.case_count,
        len(review.case_reviews),
        manifest.dataset_sha256,
        manifest.dataset_size_bytes,
    )


def verify_calibration_review_membership(
    dataset: CalibrationDataset,
    review: DatasetReview,
) -> None:
    actual = tuple(
        (case.id, case.role, case.primary_source_identity) for case in dataset.cases
    )
    expected = tuple(
        (row.case_id, row.role, row.source) for row in expected_case_rows("calibration")
    )
    reviewed_ids = tuple(case.case_id for case in review.case_reviews)
    reviewed_payloads = tuple(case.case_payload_sha256 for case in review.case_reviews)
    actual_payloads = tuple(case_payload_sha256(case) for case in dataset.cases)
    if (
        actual != expected
        or reviewed_ids != tuple(row[0] for row in actual)
        or reviewed_payloads != actual_payloads
    ):
        fail("calibration dataset and review membership do not match")
