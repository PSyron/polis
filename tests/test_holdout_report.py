from __future__ import annotations

import json
from copy import deepcopy

import pytest
from tests.holdout_report_fixture import raw_report as _raw_report
from tests.holdout_report_fixture import report_api as _report
from tests.holdout_test_helpers import NOTICE_SHA256


def test_raw_report_contains_required_aggregate_and_per_source_outcomes() -> None:
    parsed = _report().parse_raw_report(_raw_report())

    assert parsed.quality.precision == 1.0
    assert parsed.performance.peak_rss_bytes == 123456
    assert len(parsed.per_source) == 20
    assert parsed.per_source[-1].verdict == "insufficient_evidence"


@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("root", "experiment_id"),
        ("identities", "config_sha256"),
        ("identities", "dataset_sha256"),
        ("identities", "source_sha256"),
        ("identities", "wheel_sha256"),
        ("identities", "sdist_sha256"),
        ("identities", "lock_sha256"),
        ("environment", "os"),
        ("environment", "release"),
        ("environment", "machine"),
        ("environment", "python"),
        ("environment", "package"),
        ("environment", "morfeusz_dictionary"),
        ("environment", "morfeusz_notice_sha256"),
    ],
)
@pytest.mark.parametrize(
    "forbidden", ["Poufne zdanie przypadku testowego.", "/Users/private/cases.json"]
)
def test_every_accepted_report_string_slot_rejects_private_content(
    section: str, field: str, forbidden: str
) -> None:
    raw = _raw_report()
    if section == "root":
        raw[field] = forbidden
    else:
        nested = raw[section]
        assert isinstance(nested, dict)
        nested[field] = forbidden

    with pytest.raises(_report().HoldoutReportError):
        _report().parse_raw_report(raw)


@pytest.mark.parametrize("identity_index", range(5))
def test_nested_source_identity_slots_reject_private_content(
    identity_index: int,
) -> None:
    raw = _raw_report()
    per_source = raw["per_source"]
    assert isinstance(per_source, list)
    item = per_source[0]
    assert isinstance(item, dict)
    identity = item["identity"]
    assert isinstance(identity, list)
    identity[identity_index] = "Poufne zdanie przypadku testowego."

    with pytest.raises(_report().HoldoutReportError):
        _report().parse_raw_report(raw)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize(
    ("section", "field"),
    [
        ("quality", "precision"),
        ("quality", "recall"),
        ("quality", "f1"),
        ("quality", "exact_span_accuracy"),
        ("quality", "exact_correction_accuracy"),
        ("quality", "correct_sentence_false_alarm_rate"),
        ("throughput", "cases_per_second"),
        ("throughput", "code_points_per_second"),
    ],
)
def test_report_rejects_non_finite_numbers(
    section: str, field: str, value: float
) -> None:
    raw = _raw_report()
    if section == "throughput":
        performance = raw["performance"]
        assert isinstance(performance, dict)
        nested = performance[section]
    else:
        nested = raw[section]
    assert isinstance(nested, dict)
    nested[field] = value

    with pytest.raises(_report().HoldoutReportError, match="finite"):
        _report().parse_raw_report(raw)


def test_normalized_rebuild_is_byte_identical_despite_timing_and_host_drift() -> None:
    first = _raw_report()
    second = deepcopy(first)
    second["performance"] = {
        "latency_ns": {"min": 999, "mean": 999, "p50": 999, "p95": 999, "max": 999},
        "throughput": {"cases_per_second": 1.0, "code_points_per_second": 1.0},
        "peak_rss_bytes": 999999,
    }
    second["environment"] = {
        "os": "Linux",
        "release": "6.8.12-test",
        "machine": "x86_64",
        "python": "3.14.3",
        "package": "0.2.0",
        "morfeusz_dictionary": "pl.sgjp",
        "morfeusz_notice_sha256": NOTICE_SHA256,
    }

    first_bytes = _report().normalized_report_bytes(_report().parse_raw_report(first))
    second_bytes = _report().normalized_report_bytes(_report().parse_raw_report(second))

    assert first_bytes == second_bytes
    normalized = json.loads(first_bytes)
    assert "performance" not in normalized
    assert "environment" not in normalized


@pytest.mark.parametrize(
    "verdict", ["pass", "fail_threshold", "insufficient_evidence", "invalid"]
)
def test_failure_policy_accepts_only_total_verdict_variants(verdict: str) -> None:
    raw = _raw_report()
    raw["verdict"] = verdict

    assert _report().parse_raw_report(raw).verdict == verdict


def test_source_without_cases_can_never_pass() -> None:
    raw = _raw_report()
    per_source = raw["per_source"]
    assert isinstance(per_source, list)
    item = per_source[-1]
    assert isinstance(item, dict)
    item["verdict"] = "pass"

    with pytest.raises(_report().HoldoutReportError, match="coverage"):
        _report().parse_raw_report(raw)
