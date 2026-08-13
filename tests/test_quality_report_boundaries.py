from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from tests.quality_report_helpers import _result, _write_proposal

from polis.evaluation.quality_protocol import QualityProtocolResult
from polis.evaluation.quality_report import (
    QualityReportError,
    load_quality_report,
    quality_report_json,
)


@pytest.mark.parametrize(
    "result",
    (
        replace(_result(), dataset_id="unrelated_dataset"),
        replace(
            _result(),
            run_identity=replace(
                _result().run_identity, dataset_schema_id="unrelated.schema"
            ),
        ),
        replace(
            _result(),
            run_identity=replace(
                _result().run_identity, manifest_schema_id="unrelated.manifest"
            ),
        ),
    ),
)
def test_quality_report_json_rejects_foreign_dataset_identity(
    result: QualityProtocolResult,
) -> None:
    with pytest.raises(QualityReportError, match="active dataset identity mismatch"):
        quality_report_json(result)


def test_quality_report_json_rejects_cross_mismatched_dataset_identity() -> None:
    result = replace(
        _result(), baseline=replace(_result().baseline, dataset_id="unrelated_dataset")
    )

    with pytest.raises(QualityReportError, match="active dataset identity mismatch"):
        quality_report_json(result)


@pytest.mark.parametrize(
    ("section", "field", "forged_value"),
    (
        ("dataset", "id", "unrelated_dataset"),
        ("dataset", "schema_id", "unrelated.schema"),
        ("dataset", "schema_version", 2),
        ("dataset", "sha256", "e" * 64),
        ("dataset", "source", "unrelated-source"),
        ("manifest", "schema_id", "unrelated.manifest"),
        ("manifest", "schema_version", 2),
        ("manifest", "sha256", "e" * 64),
    ),
)
def test_quality_report_load_rejects_foreign_dataset_identity(
    tmp_path: Path,
    section: str,
    field: str,
    forged_value: str | int,
) -> None:
    payload = json.loads(quality_report_json(_result()))
    dataset = payload["dataset"]
    assert isinstance(dataset, dict)
    manifest = dataset["manifest"]
    assert isinstance(manifest, dict)
    target = dataset if section == "dataset" else manifest
    target[field] = forged_value
    baseline = tmp_path / "foreign-identity.json"
    _write_proposal(baseline, payload)

    expected_message = (
        "schema version mismatch"
        if section == "dataset" and field == "schema_version"
        else "active dataset identity mismatch"
    )
    with pytest.raises(QualityReportError, match=expected_message):
        load_quality_report(baseline)


def test_quality_report_json_rejects_more_correct_cases_than_dataset_cases() -> None:
    valid = _result()
    counts = replace(
        valid.baseline.aggregate,
        correct_cases=valid.baseline.dataset_cases + 1,
    )
    result = replace(valid, baseline=replace(valid.baseline, aggregate=counts))

    with pytest.raises(QualityReportError, match="counts are inconsistent"):
        quality_report_json(result)


def test_quality_report_load_rejects_more_correct_cases_than_dataset_cases(
    tmp_path: Path,
) -> None:
    payload = json.loads(quality_report_json(_result()))
    quality = payload["quality"]
    assert isinstance(quality, dict)
    counts = quality["counts"]
    assert isinstance(counts, dict)
    dataset = payload["dataset"]
    assert isinstance(dataset, dict)
    dataset_cases = dataset["cases"]
    assert isinstance(dataset_cases, int)
    invalid_correct_cases = dataset_cases + 1
    counts["correct_cases"] = invalid_correct_cases
    quality["false_alarm_rate"] = 1 / invalid_correct_cases
    baseline = tmp_path / "impossible-counts.json"
    _write_proposal(baseline, payload)

    with pytest.raises(QualityReportError, match="counts are inconsistent"):
        load_quality_report(baseline)
