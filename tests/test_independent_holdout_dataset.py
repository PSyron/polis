from __future__ import annotations

import importlib.util

import pytest
from tests.independent_dataset_test_helpers import (
    canonical_bytes,
    dataset_document,
    dataset_manifest,
)

from polis.evaluation.calibration_models import CalibrationContractError, JsonObject

if importlib.util.find_spec("polis.evaluation.holdout_v2_dataset") is None:

    def test_planned_independent_holdout_contract_is_absent() -> None:
        pytest.fail("planned independent dataset holdout loader is absent")

else:
    from polis.evaluation.calibration_manifest import parse_frozen_dataset_manifest
    from polis.evaluation.holdout_v2_dataset import load_holdout_v2_dataset_bytes

    def _load(document: JsonObject) -> None:
        raw = canonical_bytes(document)
        manifest = parse_frozen_dataset_manifest(
            canonical_bytes(dataset_manifest("holdout", raw)), "holdout"
        )
        load_holdout_v2_dataset_bytes(raw, manifest)

    def test_loads_exact_ordered_530_case_holdout() -> None:
        document = dataset_document("holdout")
        raw = canonical_bytes(document)
        manifest = parse_frozen_dataset_manifest(
            canonical_bytes(dataset_manifest("holdout", raw)), "holdout"
        )
        dataset = load_holdout_v2_dataset_bytes(raw, manifest)
        assert len(dataset.cases) == 530
        assert dataset.cases[0].id == "hold-v2-00-error-00"
        assert dataset.cases[-1].id == "hold-v2-19-correct-19"
        assert not any(
            case.role == "error"
            and case.primary_source_identity
            == "rule:agreement.nominal_group_te_duze_okno"
            for case in dataset.cases
        )

    def test_rejects_wrong_order_and_invalid_unicode_span() -> None:
        document = dataset_document("holdout")
        cases = document["cases"]
        assert isinstance(cases, list)
        cases[0], cases[1] = cases[1], cases[0]
        with pytest.raises(CalibrationContractError):
            _load(document)
        document = dataset_document("holdout")
        cases = document["cases"]
        assert isinstance(cases, list) and isinstance(cases[0], dict)
        findings = cases[0]["expected_findings"]
        assert isinstance(findings, list) and isinstance(findings[0], dict)
        findings[0]["end"] = 4
        with pytest.raises(CalibrationContractError):
            _load(document)

    def test_rejects_wrong_per_source_denominator() -> None:
        document = dataset_document("holdout")
        cases = document["cases"]
        assert isinstance(cases, list)
        del cases[-1]
        with pytest.raises(CalibrationContractError):
            _load(document)
