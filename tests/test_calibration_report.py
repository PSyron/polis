from __future__ import annotations

import importlib.util
import json

import pytest
from tests.calibration_test_helpers import canonical_bytes, nonfinite_bytes
from tests.denominator_test_constants import expected_denominators
from tests.test_calibration_scoring import _inputs

from polis.evaluation.calibration_models import CalibrationContractError, JsonObject
from polis.evaluation.calibration_scoring import score_calibration
from polis.evaluation.calibration_sources import SOURCE_ROWS

if importlib.util.find_spec("polis.evaluation.calibration_report") is None:

    def test_planned_calibration_report_module_is_available() -> None:
        pytest.fail("planned calibration report module is absent")


else:
    from polis.evaluation.calibration_models import (
        CalibrationRunAggregates,
        CalibrationRunResult,
    )
    from polis.evaluation.calibration_report import (
        normalized_report_bytes,
        parse_raw_report,
        raw_report_bytes,
        threshold_selection_bytes,
    )

    _RAW_FIELDS = {
        "schema_id",
        "schema_version",
        "experiment_id",
        "dataset_id",
        "source_snapshot_sha256",
        "repetition_hashes",
        "outcomes",
        "aggregates",
    }
    _OUTCOME_FIELDS = {
        "identity",
        "counts",
        "metrics",
        "observed_confidence",
        "minimum_confidence",
        "verdict",
    }
    _IDENTITY_FIELDS = {
        "source",
        "category",
        "operation",
        "behavior_version",
        "source_policy_version",
        "emitted_confidence",
        "current_policy_state",
    }
    _COUNT_FIELDS = {
        "error_cases",
        "correct_cases",
        "true_positive",
        "false_positive",
        "false_negative",
        "exact_span_matches",
        "exact_correction_matches",
        "correct_sentence_false_alarms",
    }
    _METRIC_FIELDS = {
        "precision",
        "recall",
        "f1",
        "exact_span_accuracy",
        "exact_correction_accuracy",
        "correct_sentence_false_alarm_rate",
    }

    def _result() -> CalibrationRunResult:
        dataset, config, findings = _inputs()
        return CalibrationRunResult(
            repetition_hashes=("a" * 64,) * 5,
            outcomes=score_calibration(dataset, findings, config),
            aggregates=CalibrationRunAggregates(1.25, 4096),
        )

    def _json(raw: bytes) -> JsonObject:
        value = json.loads(raw)
        assert isinstance(value, dict)
        return value

    def _first_outcome(raw: JsonObject) -> JsonObject:
        outcomes = raw["outcomes"]
        assert isinstance(outcomes, list) and outcomes
        outcome = outcomes[0]
        assert isinstance(outcome, dict)
        return outcome

    def test_raw_and_normalized_reports_have_exact_allowlists() -> None:
        raw = _json(raw_report_bytes(_result()))
        normalized = _json(
            normalized_report_bytes(parse_raw_report(canonical_bytes(raw)))
        )
        outcome = _first_outcome(raw)

        assert set(raw) == _RAW_FIELDS
        assert set(normalized) == _RAW_FIELDS - {"aggregates"}
        assert set(outcome) == _OUTCOME_FIELDS
        assert set(outcome["identity"]) == _IDENTITY_FIELDS
        assert set(outcome["counts"]) == _COUNT_FIELDS
        assert set(outcome["metrics"]) == _METRIC_FIELDS
        assert set(raw["aggregates"]) == {"elapsed_seconds", "peak_memory_bytes"}

    def test_normalized_rebuild_is_byte_identical() -> None:
        first = normalized_report_bytes(parse_raw_report(raw_report_bytes(_result())))
        second = normalized_report_bytes(parse_raw_report(first))

        assert second == first
        assert first.endswith(b"\n")

    def test_noncanonical_report_is_rejected() -> None:
        raw = raw_report_bytes(_result())
        with pytest.raises(CalibrationContractError):
            parse_raw_report(raw.replace(b",", b", ", 1))

    def test_threshold_selection_is_exactly_unsigned_and_non_authorizing() -> None:
        selection = _json(threshold_selection_bytes(_result()))
        rows = selection["selections"]

        assert set(selection) == {
            "schema_id",
            "schema_version",
            "experiment_id",
            "dataset_id",
            "source_snapshot_sha256",
            "authorization_status",
            "selections",
        }
        assert selection["authorization_status"] == "unsigned-non-authorizing"
        assert isinstance(rows, list) and len(rows) == 20
        assert [row["identity"]["source"] for row in rows] == [
            identity.source for identity in SOURCE_ROWS
        ]
        assert all(
            isinstance(row, dict)
            and set(row) == {"identity", "denominators", "metrics", "verdict"}
            and set(row["identity"]) == _IDENTITY_FIELDS
            and row["denominators"] == expected_denominators(row["identity"]["source"])
            and set(row["metrics"]) == _METRIC_FIELDS
            and row["verdict"]
            in {"candidate", "fail_threshold", "insufficient_evidence"}
            for row in rows
        )

    @pytest.mark.parametrize(
        "sentinel",
        [
            "Błąd🙂",
            "gold",
            "original",
            "suggestion",
            "/Users/syron/Developer/polis",
            "/Users/syron",
            "jan.kowalski@example.test",
        ],
    )
    def test_privacy_sentinels_are_absent_from_every_report(sentinel: str) -> None:
        result = _result()
        reports = (
            raw_report_bytes(result),
            normalized_report_bytes(parse_raw_report(raw_report_bytes(result))),
            threshold_selection_bytes(result),
        )

        assert all(sentinel.encode() not in report for report in reports)

    @pytest.mark.parametrize(
        "slot",
        [
            "schema_id",
            "experiment_id",
            "dataset_id",
            "source_snapshot_sha256",
            "repetition_hash",
            "source",
            "category",
            "operation",
            "behavior_version",
            "source_policy_version",
            "current_policy_state",
            "verdict",
        ],
    )
    def test_privacy_string_injection_is_rejected(slot: str) -> None:
        raw = _json(raw_report_bytes(_result()))
        outcome = _first_outcome(raw)
        identity = outcome["identity"]
        assert isinstance(identity, dict)
        if slot == "repetition_hash":
            hashes = raw["repetition_hashes"]
            assert isinstance(hashes, list)
            hashes[0] = "jan.kowalski@example.test"
        elif slot in _IDENTITY_FIELDS:
            identity[slot] = "jan.kowalski@example.test"
        elif slot == "verdict":
            outcome[slot] = "jan.kowalski@example.test"
        else:
            raw[slot] = "jan.kowalski@example.test"

        with pytest.raises(CalibrationContractError):
            parse_raw_report(canonical_bytes(raw))

    @pytest.mark.parametrize(
        ("container", "field"),
        [
            ("top", "extra"),
            ("outcome", "extra"),
            ("identity", "extra"),
            ("counts", "extra"),
            ("metrics", "extra"),
            ("aggregates", "extra"),
        ],
    )
    def test_unknown_fields_are_rejected(container: str, field: str) -> None:
        raw = _json(raw_report_bytes(_result()))
        outcome = _first_outcome(raw)
        targets = {
            "top": raw,
            "outcome": outcome,
            "identity": outcome["identity"],
            "counts": outcome["counts"],
            "metrics": outcome["metrics"],
            "aggregates": raw["aggregates"],
        }
        target = targets[container]
        assert isinstance(target, dict)
        target[field] = "forbidden"

        with pytest.raises(CalibrationContractError):
            parse_raw_report(canonical_bytes(raw))

    def test_boolean_schema_version_is_rejected() -> None:
        raw = _json(raw_report_bytes(_result()))
        raw["schema_version"] = True

        with pytest.raises(CalibrationContractError):
            parse_raw_report(canonical_bytes(raw))

    @pytest.mark.parametrize("constant", [float("nan"), float("inf"), -float("inf")])
    def test_nonfinite_aggregates_and_metrics_are_rejected(constant: float) -> None:
        raw = _json(raw_report_bytes(_result()))
        raw["aggregates"]["elapsed_seconds"] = constant

        with pytest.raises(CalibrationContractError):
            parse_raw_report(nonfinite_bytes(raw))

        raw = _json(raw_report_bytes(_result()))
        _first_outcome(raw)["metrics"]["precision"] = constant
        with pytest.raises(CalibrationContractError):
            parse_raw_report(nonfinite_bytes(raw))

    def test_negative_resource_aggregate_is_rejected() -> None:
        raw = _json(raw_report_bytes(_result()))
        raw["aggregates"]["elapsed_seconds"] = -0.01

        with pytest.raises(CalibrationContractError):
            parse_raw_report(canonical_bytes(raw))

    @pytest.mark.parametrize(
        ("container", "field"),
        [("counts", "true_positive"), ("aggregates", "peak_memory_bytes")],
    )
    def test_boolean_counts_are_rejected(container: str, field: str) -> None:
        raw = _json(raw_report_bytes(_result()))
        outcome = _first_outcome(raw)
        target = outcome[container] if container == "counts" else raw[container]
        assert isinstance(target, dict)
        target[field] = True

        with pytest.raises(CalibrationContractError):
            parse_raw_report(canonical_bytes(raw))
