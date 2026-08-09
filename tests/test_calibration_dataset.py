from __future__ import annotations

import importlib.util

import pytest
from tests.calibration_test_helpers import (
    JsonObject,
    canonical_bytes,
    synthetic_config,
    synthetic_dataset,
    synthetic_manifest,
)

from polis.evaluation.calibration_models import (
    CalibrationContractError,
    CalibrationDataset,
)
from polis.evaluation.calibration_sources import SOURCE_ROWS

_MODULES_PRESENT = all(
    importlib.util.find_spec(name) is not None
    for name in (
        "polis.evaluation.calibration_contract",
        "polis.evaluation.calibration_dataset",
    )
)


if not _MODULES_PRESENT:

    def test_planned_calibration_dataset_module_is_available() -> None:
        pytest.fail("planned calibration dataset module is absent")


else:
    from polis.evaluation.calibration_contract import (
        parse_calibration_config,
        parse_calibration_manifest,
    )
    from polis.evaluation.calibration_dataset import load_calibration_dataset_bytes

    def _cases(raw: JsonObject) -> list[JsonObject]:
        value = raw["cases"]
        assert isinstance(value, list)
        assert all(isinstance(item, dict) for item in value)
        return value

    def _valid_inputs() -> tuple[bytes, JsonObject]:
        dataset_bytes = canonical_bytes(synthetic_dataset())
        return dataset_bytes, synthetic_manifest(dataset_bytes)

    def _load(dataset_raw: JsonObject) -> CalibrationDataset:
        dataset_bytes = canonical_bytes(dataset_raw)
        manifest = parse_calibration_manifest(
            canonical_bytes(synthetic_manifest(dataset_bytes))
        )
        config = parse_calibration_config(canonical_bytes(synthetic_config()))
        return load_calibration_dataset_bytes(dataset_bytes, manifest, config)

    def test_reviewed_manifest_and_1200_case_dataset_are_accepted() -> None:
        dataset_bytes, manifest_raw = _valid_inputs()
        manifest = parse_calibration_manifest(canonical_bytes(manifest_raw))
        config = parse_calibration_config(canonical_bytes(synthetic_config()))

        dataset = load_calibration_dataset_bytes(dataset_bytes, manifest, config)

        assert len(dataset.cases) == 1200
        assert sum(case.role == "error" for case in dataset.cases) == 400
        assert sum(case.role == "correct" for case in dataset.cases) == 800

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("license", "MIT"),
            ("provenance", "private"),
            ("review_status", "pending"),
            ("pii_status", "unknown"),
            ("reviewed_case_count", 1199),
        ],
    )
    def test_manifest_rejects_non_public_or_incomplete_review(
        field: str,
        value: str | int,
    ) -> None:
        dataset_bytes, raw = _valid_inputs()
        raw[field] = value

        with pytest.raises(CalibrationContractError):
            parse_calibration_manifest(canonical_bytes(raw))

    def test_manifest_rejects_noncanonical_bytes() -> None:
        dataset_bytes, raw = _valid_inputs()
        encoded = canonical_bytes(raw).replace(b'":', b'": ', 1)

        with pytest.raises(CalibrationContractError):
            parse_calibration_manifest(encoded)

    @pytest.mark.parametrize("field", ["schema_id", "dataset_sha256"])
    def test_manifest_rejects_missing_field(field: str) -> None:
        dataset_bytes, raw = _valid_inputs()
        del raw[field]

        with pytest.raises(CalibrationContractError):
            parse_calibration_manifest(canonical_bytes(raw))

    def test_manifest_rejects_unknown_field() -> None:
        dataset_bytes, raw = _valid_inputs()
        raw["unknown"] = "forbidden"

        with pytest.raises(CalibrationContractError):
            parse_calibration_manifest(canonical_bytes(raw))

    def test_manifest_rejects_boolean_schema_version() -> None:
        dataset_bytes, raw = _valid_inputs()
        raw["schema_version"] = True

        with pytest.raises(CalibrationContractError):
            parse_calibration_manifest(canonical_bytes(raw))

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("schema_id", "wrong"),
            ("schema_version", 2),
            ("dataset_id", "wrong"),
        ],
    )
    def test_manifest_rejects_schema_or_dataset_identity_drift(
        field: str,
        value: str | int,
    ) -> None:
        dataset_bytes, raw = _valid_inputs()
        raw[field] = value

        with pytest.raises(CalibrationContractError):
            parse_calibration_manifest(canonical_bytes(raw))

    def test_dataset_rejects_boolean_schema_version() -> None:
        raw = synthetic_dataset()
        raw["schema_version"] = True

        with pytest.raises(CalibrationContractError):
            _load(raw)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("schema_id", "wrong"),
            ("schema_version", 2),
            ("dataset_id", "wrong"),
            ("language", "en"),
        ],
    )
    def test_dataset_rejects_root_identity_drift(
        field: str,
        value: str | int,
    ) -> None:
        raw = synthetic_dataset()
        raw[field] = value

        with pytest.raises(CalibrationContractError):
            _load(raw)

    @pytest.mark.parametrize("field", ["language", "cases"])
    def test_dataset_rejects_missing_root_field(field: str) -> None:
        raw = synthetic_dataset()
        del raw[field]

        with pytest.raises(CalibrationContractError):
            _load(raw)

    def test_dataset_rejects_unknown_root_field() -> None:
        raw = synthetic_dataset()
        raw["unknown"] = "forbidden"

        with pytest.raises(CalibrationContractError):
            _load(raw)

    def test_dataset_rejects_duplicate_case_id() -> None:
        raw = synthetic_dataset()
        cases = _cases(raw)
        cases[1]["id"] = cases[0]["id"]

        with pytest.raises(CalibrationContractError):
            _load(raw)

    def test_dataset_rejects_unknown_primary_source() -> None:
        raw = synthetic_dataset()
        _cases(raw)[0]["primary_source_identity"] = "rule:unknown"

        with pytest.raises(CalibrationContractError):
            _load(raw)

    def test_dataset_rejects_wrong_role() -> None:
        raw = synthetic_dataset()
        _cases(raw)[0]["role"] = "unknown"

        with pytest.raises(CalibrationContractError):
            _load(raw)

    def test_dataset_rejects_unicode_surface_mismatch() -> None:
        raw = synthetic_dataset()
        findings = _cases(raw)[0]["expected_findings"]
        assert isinstance(findings, list)
        finding = findings[0]
        assert isinstance(finding, dict)
        finding["end"] = 5

        with pytest.raises(CalibrationContractError):
            _load(raw)

    def test_dataset_rejects_finding_for_wrong_primary_source() -> None:
        raw = synthetic_dataset()
        findings = _cases(raw)[0]["expected_findings"]
        assert isinstance(findings, list)
        finding = findings[0]
        assert isinstance(finding, dict)
        finding["source"] = "rule:spelling.jestes"

        with pytest.raises(CalibrationContractError):
            _load(raw)

    @pytest.mark.parametrize("role", ["error", "correct"])
    def test_dataset_rejects_wrong_finding_count_for_role(role: str) -> None:
        raw = synthetic_dataset()
        case = next(case for case in _cases(raw) if case["role"] == role)
        case["expected_findings"] = (
            []
            if role == "error"
            else [
                {
                    "source": SOURCE_ROWS[0].source,
                    "category": SOURCE_ROWS[0].category,
                    "start": 0,
                    "end": 4,
                    "original": "Popr",
                    "suggestion": "Zmiana",
                }
            ]
        )

        with pytest.raises(CalibrationContractError):
            _load(raw)

    @pytest.mark.parametrize("role", ["error", "correct"])
    def test_dataset_rejects_below_minimum_denominator(role: str) -> None:
        raw = synthetic_dataset()
        cases = _cases(raw)
        case = next(case for case in cases if case["role"] == role)
        case["primary_source_identity"] = SOURCE_ROWS[1].source
        findings = case["expected_findings"]
        assert isinstance(findings, list)
        if findings:
            finding = findings[0]
            assert isinstance(finding, dict)
            finding["source"] = SOURCE_ROWS[1].source
            finding["category"] = SOURCE_ROWS[1].category

        with pytest.raises(CalibrationContractError):
            _load(raw)

    @pytest.mark.parametrize(
        ("field", "value"),
        [("dataset_sha256", "0" * 64), ("dataset_size_bytes", 1)],
    )
    def test_dataset_rejects_manifest_digest_or_size_mismatch(
        field: str,
        value: str | int,
    ) -> None:
        dataset_bytes, manifest_raw = _valid_inputs()
        manifest_raw[field] = value
        manifest = parse_calibration_manifest(canonical_bytes(manifest_raw))
        config = parse_calibration_config(canonical_bytes(synthetic_config()))

        with pytest.raises(CalibrationContractError):
            load_calibration_dataset_bytes(dataset_bytes, manifest, config)

    def test_dataset_rejects_noncanonical_bytes() -> None:
        dataset_bytes, manifest_raw = _valid_inputs()
        noncanonical = dataset_bytes.replace(b'":', b'": ', 1)
        manifest = parse_calibration_manifest(canonical_bytes(manifest_raw))
        config = parse_calibration_config(canonical_bytes(synthetic_config()))

        with pytest.raises(CalibrationContractError):
            load_calibration_dataset_bytes(noncanonical, manifest, config)
