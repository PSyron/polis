from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from tests.quality_report_helpers import _result, _write_proposal

from polis.evaluation.quality_protocol import QualityProtocolResult
from polis.evaluation.quality_report import (
    QualityReportError,
    baseline_file_sha256,
    load_quality_report,
    quality_report_json,
    write_quality_report,
)


def test_quality_report_has_canonical_round_trip_without_text_or_thresholds(
    tmp_path: Path,
) -> None:
    encoded = quality_report_json(_result())
    baseline = tmp_path / "baseline.json"
    baseline.write_text(encoded, encoding="utf-8")

    report = load_quality_report(baseline)
    payload = json.loads(encoded)

    assert encoded.endswith("\n")
    assert (
        encoded
        == json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    assert report.quality_precision == _result().baseline.aggregate.exact_edit_precision
    assert report.dataset_sha256 == _result().dataset_sha256
    assert payload["analyzer"] == "Analyzer(AnalyzerConfig())"
    assert "thresholds" not in payload
    assert "text" not in encoded


@pytest.mark.parametrize(
    ("metric", "forged_value"),
    (
        ("precision", 0.0),
        ("recall", 0.0),
        ("f1", 0.0),
        ("span_accuracy", 0.0),
        ("correction_accuracy", 0.0),
        ("false_alarm_rate", 0.0),
    ),
)
def test_quality_report_rejects_ratio_inconsistent_with_counts(
    tmp_path: Path,
    metric: str,
    forged_value: float,
) -> None:
    payload = json.loads(quality_report_json(_result()))
    quality = payload["quality"]
    assert isinstance(quality, dict)
    quality[metric] = forged_value
    baseline = tmp_path / "forged-ratio.json"
    _write_proposal(baseline, payload)

    with pytest.raises(QualityReportError, match=f"quality report {metric} mismatch"):
        load_quality_report(baseline)


@pytest.mark.parametrize(
    "metric",
    (
        "precision",
        "recall",
        "f1",
        "span_accuracy",
        "correction_accuracy",
        "false_alarm_rate",
    ),
)
def test_quality_report_rejects_null_ratio_when_counts_produce_a_value(
    tmp_path: Path,
    metric: str,
) -> None:
    payload = json.loads(quality_report_json(_result()))
    quality = payload["quality"]
    assert isinstance(quality, dict)
    quality[metric] = None
    baseline = tmp_path / "null-ratio.json"
    _write_proposal(baseline, payload)

    with pytest.raises(QualityReportError, match=f"quality report {metric} mismatch"):
        load_quality_report(baseline)


@pytest.mark.parametrize(
    "metric",
    (
        "precision",
        "recall",
        "f1",
        "span_accuracy",
        "correction_accuracy",
        "false_alarm_rate",
    ),
)
def test_quality_report_rejects_value_ratio_when_counts_produce_null(
    tmp_path: Path,
    metric: str,
) -> None:
    payload = json.loads(quality_report_json(_result()))
    quality = payload["quality"]
    assert isinstance(quality, dict)
    counts = quality["counts"]
    assert isinstance(counts, dict)
    for name in counts:
        counts[name] = 0
    for name in (
        "precision",
        "recall",
        "f1",
        "span_accuracy",
        "correction_accuracy",
        "false_alarm_rate",
    ):
        quality[name] = None
    quality[metric] = 0.0
    baseline = tmp_path / "value-ratio.json"
    _write_proposal(baseline, payload)

    with pytest.raises(QualityReportError, match=f"quality report {metric} mismatch"):
        load_quality_report(baseline)


def test_quality_report_rejects_overflow_ratio_integer(
    tmp_path: Path,
) -> None:
    payload = json.loads(quality_report_json(_result()))
    quality = payload["quality"]
    assert isinstance(quality, dict)
    quality["precision"] = 10**400
    baseline = tmp_path / "overflow-ratio.json"
    _write_proposal(baseline, payload)

    with pytest.raises(
        QualityReportError, match="precision must be within the unit interval"
    ):
        load_quality_report(baseline)


@pytest.mark.parametrize(
    ("field", "forged_value"),
    (
        ("expected_findings", 4),
        ("predicted_findings", 3),
        ("correction_matches", 1),
        ("span_matches", 3),
        ("alarmed_correct_cases", 3),
    ),
)
def test_quality_report_rejects_counts_that_violate_generated_invariants(
    tmp_path: Path,
    field: str,
    forged_value: int,
) -> None:
    payload = json.loads(quality_report_json(_result()))
    quality = payload["quality"]
    assert isinstance(quality, dict)
    counts = quality["counts"]
    assert isinstance(counts, dict)
    counts[field] = forged_value
    baseline = tmp_path / "forged-counts.json"
    _write_proposal(baseline, payload)

    with pytest.raises(
        QualityReportError, match="quality report counts are inconsistent"
    ):
        load_quality_report(baseline)


@pytest.mark.parametrize(
    "change",
    (
        ("dataset", "cases", 0),
        ("reproducibility", "measured_repetitions", 1),
        ("reproducibility", "stable_repetitions", 1),
        ("reproducibility", "repetition_hashes", ["d" * 64]),
        ("reproducibility", "repetition_hashes", ["d" * 64, "e" * 64]),
        ("latency_ns", "sample_count", 0),
        ("latency_ns", "sample_count", 31),
        ("latency_ns", "min", 31),
        ("latency_ns", "mean", 21),
        ("latency_ns", "p50", 9),
        ("latency_ns", "p95", 19),
        ("throughput", "measured_cases", 31),
        ("throughput", "measured_code_points", 0),
        ("throughput", "measured_code_points", 33),
        ("throughput", "total_duration_ns", 0),
        ("throughput", "cases_per_second", 1.0),
        ("throughput", "code_points_per_second", 1.0),
        ("throughput", "cases_per_second", float("nan")),
        ("throughput", "cases_per_second", float("inf")),
        ("throughput", "cases_per_second", 10**400),
        ("throughput", "code_points_per_second", float("-inf")),
    ),
)
def test_quality_report_rejects_inconsistent_measurement_evidence(
    tmp_path: Path, change: tuple[str, str, int | float | list[str]]
) -> None:
    payload = json.loads(quality_report_json(_result()))
    performance = payload["performance"]
    assert isinstance(performance, dict)
    section = (
        payload[change[0]]
        if change[0] in {"dataset", "reproducibility"}
        else performance[change[0]]
    )
    assert isinstance(section, dict)
    section[change[1]] = change[2]
    baseline = tmp_path / "inconsistent-measurement.json"
    _write_proposal(baseline, payload)

    message = (
        "quality report counts are inconsistent"
        if change == ("dataset", "cases", 0)
        else "quality report measurement evidence is inconsistent"
    )
    with pytest.raises(QualityReportError, match=message):
        load_quality_report(baseline)


@pytest.mark.parametrize(
    "result",
    (
        replace(_result(), latency=replace(_result().latency, min_ns=31)),
        replace(
            _result(),
            throughput=replace(_result().throughput, cases_per_second=float("nan")),
        ),
    ),
)
def test_quality_report_json_rejects_inconsistent_measurement_evidence(
    result: QualityProtocolResult,
) -> None:
    with pytest.raises(
        QualityReportError,
        match="quality report measurement evidence is inconsistent",
    ):
        quality_report_json(result)


def test_quality_report_refuses_overwrite_unless_replacement_is_explicit(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_text("existing evidence\n", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_quality_report(_result(), baseline)

    write_quality_report(_result(), baseline, replace=True)
    assert load_quality_report(baseline).artifact_sha256 == "b" * 64


def test_baseline_sha256_uses_exact_file_bytes(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    baseline.write_bytes(b'{"schema_version":1}\r\n')

    assert (
        baseline_file_sha256(baseline)
        == hashlib.sha256(b'{"schema_version":1}\r\n').hexdigest()
    )
