from __future__ import annotations

import hashlib
import importlib.util
from dataclasses import replace

import pytest
from tests.independent_dataset_test_helpers import (
    canonical_bytes,
    dataset_document,
    dataset_manifest,
    dataset_review,
    review_payload_bytes,
)

from polis.evaluation.calibration_models import CalibrationContractError

if importlib.util.find_spec("polis.evaluation.calibration_freeze") is None:

    def test_planned_independent_dataset_freeze_is_absent() -> None:
        pytest.fail("planned independent dataset freeze contract is absent")

else:
    from polis.evaluation.calibration_freeze import verify_frozen_bindings
    from polis.evaluation.calibration_freeze_models import (
        FINITE_OVERLAP_APPROVAL,
        FINITE_OVERLAP_HISTOGRAM,
        PREREGISTERED_FINITE_EXACT_MATCHES,
        FreezeInputs,
        OverlapResult,
    )
    from polis.evaluation.calibration_manifest import parse_frozen_dataset_manifest
    from polis.evaluation.calibration_review import parse_dataset_review

    def _inputs() -> FreezeInputs:
        cal_bytes = canonical_bytes(dataset_document("calibration"))
        hold_bytes = canonical_bytes(dataset_document("holdout"))
        cal_review_raw = dataset_review("calibration", cal_bytes)
        hold_review_raw = dataset_review("holdout", hold_bytes)
        cal_review_bytes = canonical_bytes(cal_review_raw)
        hold_review_bytes = canonical_bytes(hold_review_raw)
        cal_manifest = dataset_manifest("calibration", cal_bytes)
        hold_manifest = dataset_manifest("holdout", hold_bytes)
        cal_manifest["review_manifest_sha256"] = hashlib.sha256(
            cal_review_bytes
        ).hexdigest()
        hold_manifest["review_manifest_sha256"] = hashlib.sha256(
            hold_review_bytes
        ).hexdigest()
        cal_manifest["review_payload_sha256"] = cal_review_raw["review_payload_sha256"]
        hold_manifest["review_payload_sha256"] = hold_review_raw[
            "review_payload_sha256"
        ]
        return FreezeInputs(
            parse_frozen_dataset_manifest(
                canonical_bytes(cal_manifest),
                "calibration",
            ),
            parse_frozen_dataset_manifest(canonical_bytes(hold_manifest), "holdout"),
            parse_dataset_review(
                cal_review_bytes, "calibration", review_payload_bytes(cal_review_raw)
            ),
            parse_dataset_review(
                hold_review_bytes, "holdout", review_payload_bytes(hold_review_raw)
            ),
            OverlapResult(
                0,
                0,
                1,
                "APPROVE",
                PREREGISTERED_FINITE_EXACT_MATCHES,
                FINITE_OVERLAP_HISTOGRAM,
                FINITE_OVERLAP_APPROVAL,
            ),
            "polis-269-overlap-custodian-v1",
            "polis-269-freeze-verifier-a-v1",
            "polis-269-freeze-verifier-b-v1",
        )

    def test_freeze_accepts_complete_approved_role_assignment() -> None:
        result = verify_frozen_bindings(_inputs())
        assert result.verdict == "APPROVE"
        assert len(result.role_identities) == 16

    def test_freeze_rejects_role_reuse_and_overlap_block() -> None:
        inputs = _inputs()
        reused = FreezeInputs(
            inputs.calibration_manifest,
            inputs.holdout_manifest,
            inputs.calibration_review,
            inputs.holdout_review,
            inputs.overlap,
            inputs.calibration_manifest.custodian_identity,
            inputs.freeze_verifier_a_identity,
            inputs.freeze_verifier_b_identity,
        )
        with pytest.raises(CalibrationContractError):
            verify_frozen_bindings(reused)
        blocked = FreezeInputs(
            inputs.calibration_manifest,
            inputs.holdout_manifest,
            inputs.calibration_review,
            inputs.holdout_review,
            OverlapResult(
                1,
                0,
                1,
                "BLOCK",
                PREREGISTERED_FINITE_EXACT_MATCHES,
                FINITE_OVERLAP_HISTOGRAM,
                FINITE_OVERLAP_APPROVAL,
            ),
            inputs.overlap_custodian_identity,
            inputs.freeze_verifier_a_identity,
            inputs.freeze_verifier_b_identity,
        )
        with pytest.raises(CalibrationContractError):
            verify_frozen_bindings(blocked)

    def test_freeze_rejects_joint_review_payload_digest_drift() -> None:
        inputs = _inputs()
        drifted_digest = "4" * 64
        forged = replace(
            inputs,
            calibration_manifest=replace(
                inputs.calibration_manifest,
                review_payload_sha256=drifted_digest,
            ),
            calibration_review=replace(
                inputs.calibration_review,
                review_payload_sha256=drifted_digest,
            ),
        )
        with pytest.raises(CalibrationContractError):
            verify_frozen_bindings(forged)
