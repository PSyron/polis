from __future__ import annotations

import pytest
from tests.calibration_test_helpers import canonical_bytes
from tests.test_calibration_report import _json, _result

from polis.evaluation.calibration_models import CalibrationContractError, JsonObject
from polis.evaluation.calibration_report import parse_raw_report, raw_report_bytes


def _finite_outcome() -> tuple[JsonObject, JsonObject]:
    raw = _json(raw_report_bytes(_result()))
    outcomes = raw["outcomes"]
    assert isinstance(outcomes, list) and isinstance(outcomes[2], dict)
    return raw, outcomes[2]


def test_finite_report_row_is_structurally_insufficient() -> None:
    _, outcome = _finite_outcome()
    assert outcome["verdict"] == "insufficient_evidence"
    assert outcome["minimum_confidence"] is None
    assert outcome["counts"] == {
        "error_cases": 1,
        "correct_cases": 40,
        "true_positive": 1,
        "false_positive": 0,
        "false_negative": 0,
        "exact_span_matches": 1,
        "exact_correction_matches": 1,
        "correct_sentence_false_alarms": 0,
    }


@pytest.mark.parametrize("verdict", ["candidate", "fail_threshold"])
def test_report_parser_rejects_promotion_of_finite_key(verdict: str) -> None:
    raw, outcome = _finite_outcome()
    outcome["verdict"] = verdict
    if verdict == "candidate":
        identity = outcome["identity"]
        assert isinstance(identity, dict)
        outcome["minimum_confidence"] = identity["emitted_confidence"]
    with pytest.raises(CalibrationContractError):
        parse_raw_report(canonical_bytes(raw))


def test_report_parser_rejects_finite_denominator_drift() -> None:
    raw, outcome = _finite_outcome()
    counts = outcome["counts"]
    assert isinstance(counts, dict)
    counts["error_cases"] = 2
    with pytest.raises(CalibrationContractError):
        parse_raw_report(canonical_bytes(raw))
