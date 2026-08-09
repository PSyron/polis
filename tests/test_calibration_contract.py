from __future__ import annotations

import importlib.util
import math

import pytest
from tests.calibration_test_helpers import (
    JsonObject,
    canonical_bytes,
    nonfinite_bytes,
    synthetic_config,
)

from polis.evaluation.calibration_models import CalibrationContractError

if importlib.util.find_spec("polis.evaluation.calibration_contract") is None:

    def test_planned_calibration_contract_module_is_available() -> None:
        pytest.fail("planned calibration contract module is absent")


else:
    from polis.evaluation.calibration_contract import parse_calibration_config

    def _nested(raw: JsonObject, field: str) -> JsonObject:
        value = raw[field]
        assert isinstance(value, dict)
        return value

    def test_valid_config_parses_exact_frozen_contract() -> None:
        parsed = parse_calibration_config(canonical_bytes(synthetic_config()))

        assert parsed.experiment_id == "polis-a-b-qualification-v2-v1"
        assert parsed.dataset_id == "polis-a-b-calibration-v2-v1"
        assert len(parsed.source_rows) == 20
        assert parsed.warmup_repetitions == 1
        assert parsed.measured_repetitions == 5

    @pytest.mark.parametrize("field", ["schema_id", "paths"])
    def test_config_rejects_missing_top_level_field(field: str) -> None:
        raw = synthetic_config()
        del raw[field]

        with pytest.raises(CalibrationContractError):
            parse_calibration_config(canonical_bytes(raw))

    def test_config_rejects_unknown_top_level_field() -> None:
        raw = synthetic_config()
        raw["unknown"] = "forbidden"

        with pytest.raises(CalibrationContractError):
            parse_calibration_config(canonical_bytes(raw))

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("schema_id", "wrong"),
            ("schema_version", 2),
            ("experiment_id", "wrong"),
            ("dataset_id", "wrong"),
            ("threshold_profile", "wrong"),
        ],
    )
    def test_config_rejects_identity_drift(field: str, value: str | int) -> None:
        raw = synthetic_config()
        raw[field] = value

        with pytest.raises(CalibrationContractError):
            parse_calibration_config(canonical_bytes(raw))

    def test_config_rejects_noncanonical_json() -> None:
        raw = canonical_bytes(synthetic_config()).replace(b'":', b'": ', 1)

        with pytest.raises(CalibrationContractError):
            parse_calibration_config(raw)

    @pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
    def test_config_rejects_nonfinite_threshold(value: float) -> None:
        raw = synthetic_config()
        _nested(raw, "thresholds")["precision"] = value

        with pytest.raises(CalibrationContractError):
            parse_calibration_config(nonfinite_bytes(raw))

    def test_config_rejects_boolean_integer() -> None:
        raw = synthetic_config()
        raw["warmup_repetitions"] = True

        with pytest.raises(CalibrationContractError):
            parse_calibration_config(canonical_bytes(raw))

    def test_config_rejects_boolean_schema_version() -> None:
        raw = synthetic_config()
        raw["schema_version"] = True

        with pytest.raises(CalibrationContractError):
            parse_calibration_config(canonical_bytes(raw))

    def test_config_rejects_source_snapshot_mismatch() -> None:
        raw = synthetic_config()
        raw["source_snapshot_sha256"] = "0" * 64

        with pytest.raises(CalibrationContractError):
            parse_calibration_config(canonical_bytes(raw))

    @pytest.mark.parametrize("path", ["/tmp/cases.json", "../cases.json"])
    def test_config_rejects_absolute_or_escaping_path(path: str) -> None:
        raw = synthetic_config()
        _nested(raw, "paths")["dataset"] = path

        with pytest.raises(CalibrationContractError):
            parse_calibration_config(canonical_bytes(raw))

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("warmup_repetitions", 2),
            ("measured_repetitions", 4),
            ("minimum_error_cases_per_key", 19),
            ("minimum_correct_cases_per_key", 39),
        ],
    )
    def test_config_rejects_repetition_or_minimum_override(
        field: str,
        value: int,
    ) -> None:
        raw = synthetic_config()
        raw[field] = value

        with pytest.raises(CalibrationContractError):
            parse_calibration_config(canonical_bytes(raw))

    @pytest.mark.parametrize("container", ["thresholds", "paths"])
    def test_config_rejects_unknown_nested_field(container: str) -> None:
        raw = synthetic_config()
        _nested(raw, container)["unknown"] = "forbidden"

        with pytest.raises(CalibrationContractError):
            parse_calibration_config(canonical_bytes(raw))
