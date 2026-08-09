from __future__ import annotations

import hashlib
import importlib.util

import pytest
from tests.independent_dataset_test_helpers import (
    canonical_bytes,
    dataset_document,
    dataset_manifest,
    dataset_review,
    recompute_review_approval,
    review_payload_bytes,
)

from polis.evaluation.calibration_models import CalibrationContractError

if importlib.util.find_spec("polis.evaluation.calibration_manifest") is None:

    def test_planned_independent_dataset_contract_is_absent() -> None:
        pytest.fail("planned independent dataset contract is absent")

else:
    from polis.evaluation.calibration_manifest import parse_frozen_dataset_manifest
    from polis.evaluation.calibration_review import parse_dataset_review

    def test_review_and_manifest_bind_approved_assignment() -> None:
        dataset = canonical_bytes(dataset_document("calibration"))
        review_raw = dataset_review("calibration", dataset)
        manifest = parse_frozen_dataset_manifest(
            canonical_bytes(dataset_manifest("calibration", dataset)), "calibration"
        )
        review = parse_dataset_review(
            canonical_bytes(review_raw),
            "calibration",
            review_payload_bytes(review_raw),
        )
        assert (
            manifest.assignment.validator_implementer_identity
            == "polis-269-validator-v1"
        )
        assert review.assignment.role_assignment_comment_id == 5232770360
        assert manifest.assignment.denominator_approval_comment_id == 5233051643
        assert review.assignment.denominator_approval_body_sha256 == (
            "63484eb3feabe5f5a6c0aabf86107657170162b58a5c4a7a188406aaa785bdc9"
        )

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("validator_implementer_identity", "polis-269-calibration-author-a-v1"),
            ("role_assignment_comment_id", 5232770361),
            ("role_assignment_comment_url", "https://example.invalid/changed"),
            ("role_assignment_comment_author", "someone-else"),
            ("role_assignment_body_sha256", "0" * 64),
            ("denominator_approval_comment_id", 5233051644),
            ("denominator_approval_comment_url", "https://example.invalid/changed"),
            ("denominator_approval_comment_author", "someone-else"),
            ("denominator_approval_body_sha256", "0" * 64),
        ],
    )
    def test_manifest_rejects_assignment_drift(field: str, value: str | int) -> None:
        dataset = canonical_bytes(dataset_document("calibration"))
        raw = dataset_manifest("calibration", dataset)
        raw[field] = value
        with pytest.raises(CalibrationContractError):
            parse_frozen_dataset_manifest(canonical_bytes(raw), "calibration")

    def test_review_rejects_missing_binding_even_with_recomputed_digest() -> None:
        dataset = canonical_bytes(dataset_document("holdout"))
        raw = dataset_review("holdout", dataset)
        payload = review_payload_bytes(raw)
        del raw["validator_implementer_identity"]
        with pytest.raises(CalibrationContractError):
            parse_dataset_review(canonical_bytes(raw), "holdout", payload)

    def test_review_rejects_changed_assignment_with_recomputed_digest() -> None:
        dataset = canonical_bytes(dataset_document("calibration"))
        raw = dataset_review("calibration", dataset)
        raw["role_assignment_body_sha256"] = "0" * 64
        recompute_review_approval(raw)
        with pytest.raises(CalibrationContractError):
            parse_dataset_review(
                canonical_bytes(raw), "calibration", review_payload_bytes(raw)
            )

    def test_review_rejects_denominator_approval_drift_with_recomputed_digest() -> None:
        dataset = canonical_bytes(dataset_document("holdout"))
        raw = dataset_review("holdout", dataset)
        raw["denominator_approval_body_sha256"] = "0" * 64
        recompute_review_approval(raw)
        with pytest.raises(CalibrationContractError):
            parse_dataset_review(
                canonical_bytes(raw), "holdout", review_payload_bytes(raw)
            )

    def test_review_rejects_arbitrary_payload_digest() -> None:
        dataset = canonical_bytes(dataset_document("calibration"))
        raw = dataset_review("calibration", dataset)
        payload = review_payload_bytes(raw)
        raw["review_payload_sha256"] = "4" * 64
        recompute_review_approval(raw)
        with pytest.raises(CalibrationContractError):
            parse_dataset_review(canonical_bytes(raw), "calibration", payload)

    def test_review_rejects_record_drift_after_all_metadata_digests_change() -> None:
        dataset = canonical_bytes(dataset_document("holdout"))
        raw = dataset_review("holdout", dataset)
        trusted_payload = review_payload_bytes(raw)
        case_reviews = raw["case_reviews"]
        assert isinstance(case_reviews, list) and isinstance(case_reviews[0], dict)
        case_reviews[0]["author_identity"] = case_reviews[1]["author_identity"]
        raw["review_payload_sha256"] = hashlib.sha256(
            review_payload_bytes(raw)
        ).hexdigest()
        recompute_review_approval(raw)
        with pytest.raises(CalibrationContractError):
            parse_dataset_review(canonical_bytes(raw), "holdout", trusted_payload)

    def test_manifest_rejects_bool_count_and_role_reuse() -> None:
        dataset = canonical_bytes(dataset_document("holdout"))
        raw = dataset_manifest("holdout", dataset)
        raw["case_count"] = True
        with pytest.raises(CalibrationContractError):
            parse_frozen_dataset_manifest(canonical_bytes(raw), "holdout")
        raw = dataset_manifest("holdout", dataset)
        raw["reviewer_identity"] = raw["custodian_identity"]
        with pytest.raises(CalibrationContractError):
            parse_frozen_dataset_manifest(canonical_bytes(raw), "holdout")
