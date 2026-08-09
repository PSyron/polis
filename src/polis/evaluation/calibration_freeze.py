from __future__ import annotations

import hashlib

from polis.evaluation.calibration_freeze_models import (
    FINITE_OVERLAP_APPROVAL,
    FINITE_OVERLAP_HISTOGRAM,
    PREREGISTERED_FINITE_EXACT_MATCHES,
    FreezeInputs,
    FreezeVerification,
)
from polis.evaluation.calibration_json import fail
from polis.evaluation.calibration_roles import ALL_ROLE_IDENTITIES


def _dataset_binding_matches(inputs: FreezeInputs) -> bool:
    pairs = (
        (inputs.calibration_manifest, inputs.calibration_review),
        (inputs.holdout_manifest, inputs.holdout_review),
    )
    return all(
        manifest.kind == review.kind
        and manifest.dataset_id == review.dataset_id
        and manifest.dataset_sha256 == review.dataset_sha256
        and manifest.author_identities == review.author_identities
        and manifest.custodian_identity == review.custodian_identity
        and manifest.reviewer_identity == review.reviewer_identity
        and manifest.review_manifest_sha256 == review.document_sha256
        and manifest.review_payload_sha256 == review.review_payload_sha256
        and hashlib.sha256(review.review_payload_bytes).hexdigest()
        == review.review_payload_sha256
        and manifest.assignment == review.assignment
        for manifest, review in pairs
    )


def verify_frozen_bindings(inputs: FreezeInputs) -> FreezeVerification:
    if not _dataset_binding_matches(inputs):
        fail("dataset manifests and reviews do not share exact frozen bindings")
    roles = (
        inputs.calibration_manifest.assignment.validator_implementer_identity,
        inputs.calibration_manifest.custodian_identity,
        *inputs.calibration_manifest.author_identities,
        inputs.calibration_manifest.reviewer_identity,
        inputs.holdout_manifest.custodian_identity,
        *inputs.holdout_manifest.author_identities,
        inputs.holdout_manifest.reviewer_identity,
        inputs.overlap_custodian_identity,
        inputs.freeze_verifier_a_identity,
        inputs.freeze_verifier_b_identity,
    )
    if roles != ALL_ROLE_IDENTITIES or len(set(roles)) != len(roles):
        fail("freeze roles do not match the distinct approved assignment")
    if (
        inputs.calibration_manifest.assignment != inputs.holdout_manifest.assignment
        or inputs.overlap.verdict != "APPROVE"
        or inputs.overlap.preregistered_finite_exact_matches
        != PREREGISTERED_FINITE_EXACT_MATCHES
        or inputs.overlap.finite_match_histogram != FINITE_OVERLAP_HISTOGRAM
        or inputs.overlap.unexpected_exact_collisions != 0
        or inputs.overlap.near_collisions != 0
        or inputs.overlap.comparison_count <= 0
        or inputs.overlap.approval != FINITE_OVERLAP_APPROVAL
    ):
        fail("freeze requires the approved finite overlap classification")
    return FreezeVerification(roles, "APPROVE")
