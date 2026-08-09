from __future__ import annotations

import importlib.util

import pytest
from tests.denominator_test_constants import FINITE_CAPACITIES, DatasetKind
from tests.independent_dataset_test_helpers import (
    canonical_bytes,
    dataset_document,
    dataset_manifest,
)

from polis.evaluation.calibration_models import CalibrationContractError
from polis.evaluation.calibration_sources import SOURCE_ROWS, SOURCE_SNAPSHOT_SHA256

if importlib.util.find_spec("polis.evaluation.calibration_denominators") is None:

    def test_planned_approved_denominator_contract_is_absent() -> None:
        pytest.fail("planned approved denominator contract is absent")

else:
    from polis.evaluation.calibration_denominators import (
        CALIBRATION_CASE_COUNT,
        CALIBRATION_CORRECT_COUNT,
        CALIBRATION_ERROR_COUNT,
        FINITE_SOURCE_CAPACITIES,
        HOLDOUT_CASE_COUNT,
        HOLDOUT_CORRECT_COUNT,
        HOLDOUT_ERROR_COUNT,
        SOURCE_DENOMINATORS,
    )
    from polis.evaluation.calibration_manifest import parse_frozen_dataset_manifest

    def test_exact_finite_capacities_and_aggregate_cores_are_frozen() -> None:
        assert FINITE_SOURCE_CAPACITIES == FINITE_CAPACITIES
        assert [row.source for row in SOURCE_DENOMINATORS] == [
            row.source for row in SOURCE_ROWS
        ]
        assert SOURCE_SNAPSHOT_SHA256 == (
            "92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92"
        )
        assert (
            CALIBRATION_CASE_COUNT,
            CALIBRATION_ERROR_COUNT,
            CALIBRATION_CORRECT_COUNT,
        ) == (1073, 273, 800)
        assert (HOLDOUT_CASE_COUNT, HOLDOUT_ERROR_COUNT, HOLDOUT_CORRECT_COUNT) == (
            530,
            130,
            400,
        )

    @pytest.mark.parametrize("kind", ["calibration", "holdout"])
    def test_manifest_binds_denominators_verdict_and_approval(
        kind: DatasetKind,
    ) -> None:
        dataset = canonical_bytes(dataset_document(kind))
        manifest = parse_frozen_dataset_manifest(
            canonical_bytes(dataset_manifest(kind, dataset)), kind
        )
        finite = {
            row.source: row
            for row in manifest.per_source_counts
            if row.source in dict(FINITE_CAPACITIES)
        }
        assert all(
            row.preregistered_verdict == "insufficient_evidence"
            for row in finite.values()
        )
        assert manifest.assignment.denominator_approval_comment_id == 5233051643

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("denominator_approval_comment_id", 5233051644),
            ("denominator_approval_comment_url", "https://example.invalid/drift"),
            ("denominator_approval_comment_author", "someone-else"),
            ("denominator_approval_body_sha256", "0" * 64),
        ],
    )
    def test_manifest_rejects_denominator_approval_drift(
        field: str, value: str | int
    ) -> None:
        dataset = canonical_bytes(dataset_document("calibration"))
        raw = dataset_manifest("calibration", dataset)
        raw[field] = value
        with pytest.raises(CalibrationContractError):
            parse_frozen_dataset_manifest(canonical_bytes(raw), "calibration")

    @pytest.mark.parametrize("kind", ["calibration", "holdout"])
    @pytest.mark.parametrize("mutation", ["count", "verdict"])
    def test_manifest_rejects_finite_policy_drift(
        kind: DatasetKind, mutation: str
    ) -> None:
        dataset = canonical_bytes(dataset_document(kind))
        raw = dataset_manifest(kind, dataset)
        rows = raw["per_source_counts"]
        assert isinstance(rows, list) and isinstance(rows[2], dict)
        field = "error_case_count" if mutation == "count" else "preregistered_verdict"
        rows[2][field] = (
            2
            if kind == "calibration" and mutation == "count"
            else (1 if mutation == "count" else None)
        )
        with pytest.raises(CalibrationContractError):
            parse_frozen_dataset_manifest(canonical_bytes(raw), kind)

    def test_manifest_rejects_ordinary_denominator_drift() -> None:
        dataset = canonical_bytes(dataset_document("calibration"))
        raw = dataset_manifest("calibration", dataset)
        rows = raw["per_source_counts"]
        assert isinstance(rows, list) and isinstance(rows[0], dict)
        rows[0]["error_case_count"] = 19
        with pytest.raises(CalibrationContractError):
            parse_frozen_dataset_manifest(canonical_bytes(raw), "calibration")
