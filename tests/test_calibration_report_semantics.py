from __future__ import annotations

import pytest
from tests.calibration_test_helpers import canonical_bytes, nonfinite_bytes
from tests.test_calibration_report import _first_outcome, _json, _result

from polis.evaluation.calibration_models import CalibrationContractError
from polis.evaluation.calibration_report import parse_raw_report, raw_report_bytes


@pytest.mark.parametrize("confidence", [None, 0.5])
def test_candidate_requires_observed_emitted_confidence(
    confidence: float | None,
) -> None:
    raw = _json(raw_report_bytes(_result()))
    _first_outcome(raw)["observed_confidence"] = confidence

    with pytest.raises(CalibrationContractError):
        parse_raw_report(canonical_bytes(raw))


@pytest.mark.parametrize("confidence", [None, 0.5])
def test_candidate_requires_minimum_emitted_confidence(
    confidence: float | None,
) -> None:
    raw = _json(raw_report_bytes(_result()))
    _first_outcome(raw)["minimum_confidence"] = confidence

    with pytest.raises(CalibrationContractError):
        parse_raw_report(canonical_bytes(raw))


@pytest.mark.parametrize("confidence", [float("nan"), float("inf"), -float("inf")])
def test_candidate_rejects_nonfinite_observed_confidence(confidence: float) -> None:
    raw = _json(raw_report_bytes(_result()))
    _first_outcome(raw)["observed_confidence"] = confidence

    with pytest.raises(CalibrationContractError):
        parse_raw_report(nonfinite_bytes(raw))


@pytest.mark.parametrize(
    ("metric", "failing_value"),
    [
        ("precision", 0.99),
        ("recall", 0.71),
        ("f1", 0.83),
        ("exact_span_accuracy", 0.71),
        ("exact_correction_accuracy", 0.99),
        ("correct_sentence_false_alarm_rate", 0.01),
    ],
)
def test_candidate_rejects_metric_below_active_baseline(
    metric: str,
    failing_value: float,
) -> None:
    raw = _json(raw_report_bytes(_result()))
    _first_outcome(raw)["metrics"][metric] = failing_value

    with pytest.raises(CalibrationContractError):
        parse_raw_report(canonical_bytes(raw))


@pytest.mark.parametrize(
    ("denominator", "incomplete"),
    [("error_cases", 19), ("correct_cases", 39)],
)
def test_candidate_requires_complete_denominators(
    denominator: str,
    incomplete: int,
) -> None:
    raw = _json(raw_report_bytes(_result()))
    _first_outcome(raw)["counts"][denominator] = incomplete

    with pytest.raises(CalibrationContractError):
        parse_raw_report(canonical_bytes(raw))


@pytest.mark.parametrize("verdict", ["fail_threshold", "insufficient_evidence"])
def test_non_candidate_rejects_minimum_confidence(verdict: str) -> None:
    raw = _json(raw_report_bytes(_result()))
    outcome = _first_outcome(raw)
    outcome["verdict"] = verdict
    outcome["minimum_confidence"] = 0.5

    with pytest.raises(CalibrationContractError):
        parse_raw_report(canonical_bytes(raw))
