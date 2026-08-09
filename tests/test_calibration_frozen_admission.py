from __future__ import annotations

from pathlib import Path
from typing import Literal

import pytest
from tests.calibration_runner_test_helpers import (
    RecordingAnalyzer,
    RecordingFactory,
    SyntheticAnalyzerError,
    output_paths,
    read_json,
    refresh_dataset_binding,
    refresh_review_binding,
    synthetic_run_inputs,
    write_legacy_workspace,
    write_workspace,
)
from tests.calibration_test_helpers import canonical_bytes

import polis.evaluation.calibration_runner as calibration_runner
import polis.evaluation.calibration_runner_io as runner_io
from polis.evaluation.calibration_models import (
    CalibrationContractError,
    JsonObject,
    JsonValue,
)
from polis.evaluation.calibration_runner import _run_calibration_for_test
from polis.evaluation.calibration_sources import SOURCE_ROWS


@pytest.fixture(autouse=True)
def _stable_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner_io, "validate_live_sources", lambda: SOURCE_ROWS)


def _json(path: Path) -> JsonObject:
    return read_json(path)


def _case_for(values: list[JsonValue], source: str, role: str) -> JsonObject:
    for value in values:
        if (
            isinstance(value, dict)
            and value.get("primary_source_identity") == source
            and value.get("role") == role
        ):
            return value
    raise AssertionError("synthetic case is absent")


def test_legacy_manifest_is_rejected_before_dataset_read_or_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = write_legacy_workspace(tmp_path)
    _, _, _, findings = synthetic_run_inputs()
    factory = RecordingFactory(RecordingAnalyzer(findings))
    labels: list[str] = []

    def observe_read(path: Path, label: str) -> bytes:
        labels.append(label)
        if label == "calibration dataset":
            raise SyntheticAnalyzerError("legacy admission reached dataset")
        return path.read_bytes()

    monkeypatch.setattr(runner_io, "_read", observe_read)
    with pytest.raises(CalibrationContractError):
        _run_calibration_for_test(config_path, factory, tmp_path)

    assert labels == ["calibration config", "calibration manifest"]
    assert factory.calls == 0
    assert all(not path.exists() for path in output_paths(tmp_path))


def test_public_module_exposes_no_in_memory_legacy_runner() -> None:
    assert not hasattr(calibration_runner, "run_synthetic_calibration")


def test_frozen_v2_review_bound_workspace_reaches_factory(tmp_path: Path) -> None:
    config_path = write_workspace(tmp_path)
    _, _, _, findings = synthetic_run_inputs()
    factory = RecordingFactory(RecordingAnalyzer(findings))

    assert _run_calibration_for_test(config_path, factory, tmp_path) == 0
    assert factory.calls == 1


@pytest.mark.parametrize("mutation", ["id", "order", "role", "source"])
def test_actual_dataset_rows_must_match_ordered_review_before_factory(
    tmp_path: Path,
    mutation: Literal["id", "order", "role", "source"],
) -> None:
    config_path = write_workspace(tmp_path)
    dataset_path = tmp_path / ".omo/sealed/a-b-calibration-v2-v1/cases.json"
    dataset = _json(dataset_path)
    cases = dataset["cases"]
    assert isinstance(cases, list)
    first = cases[0]
    second_source = _case_for(cases, SOURCE_ROWS[1].source, "error")
    first_correct = _case_for(cases, SOURCE_ROWS[0].source, "correct")
    assert isinstance(first, dict)
    if mutation == "id":
        first["id"] = "noncanonical-id"
    elif mutation == "order":
        cases[0], cases[1] = cases[1], cases[0]
    elif mutation == "role":
        first["role"] = "correct"
        first["expected_findings"] = []
        first_correct["role"] = "error"
        first_correct["expected_findings"] = [
            {
                "source": SOURCE_ROWS[0].source,
                "category": SOURCE_ROWS[0].category,
                "start": 0,
                "end": 4,
                "original": "Popr",
                "suggestion": "Błąd",
            }
        ]
    else:
        first["primary_source_identity"] = SOURCE_ROWS[1].source
        first_findings = first["expected_findings"]
        second_findings = second_source["expected_findings"]
        assert (
            isinstance(first_findings, list)
            and isinstance(first_findings[0], dict)
            and isinstance(second_findings, list)
            and isinstance(second_findings[0], dict)
        )
        first_findings[0]["source"] = SOURCE_ROWS[1].source
        first_findings[0]["category"] = SOURCE_ROWS[1].category
        second_source["primary_source_identity"] = SOURCE_ROWS[0].source
        second_findings[0]["source"] = SOURCE_ROWS[0].source
        second_findings[0]["category"] = SOURCE_ROWS[0].category
    refresh_dataset_binding(tmp_path, dataset)
    _, _, _, findings = synthetic_run_inputs()
    factory = RecordingFactory(RecordingAnalyzer(findings))

    with pytest.raises(CalibrationContractError):
        _run_calibration_for_test(config_path, factory, tmp_path)

    assert factory.calls == 0
    assert all(not path.exists() for path in output_paths(tmp_path))


@pytest.mark.parametrize(
    "boundary",
    ["denominator", "missing_review", "role", "comment", "review_payload"],
)
def test_frozen_admission_drift_fails_before_dataset_factory_and_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    boundary: Literal[
        "denominator", "missing_review", "role", "comment", "review_payload"
    ],
) -> None:
    config_path = write_workspace(tmp_path)
    experiment = tmp_path / "experiments/a-b-qualification-v2"
    review_path = experiment / "calibration.review.json"
    if boundary == "denominator":
        manifest_path = experiment / "calibration.dataset.manifest.json"
        manifest = _json(manifest_path)
        rows = manifest["per_source_counts"]
        assert isinstance(rows, list) and isinstance(rows[2], dict)
        rows[2]["error_case_count"] = 2
        manifest_path.write_bytes(canonical_bytes(manifest))
    elif boundary == "missing_review":
        review_path.unlink()
    elif boundary == "review_payload":
        payload = tmp_path / ".omo/sealed/a-b-calibration-v2-v1/review.payload.json"
        payload.write_bytes(b"[]\n")
    else:
        review = _json(review_path)
        field = (
            "reviewer_identity"
            if boundary == "role"
            else "denominator_approval_body_sha256"
        )
        review[field] = "0" * 64
        refresh_review_binding(tmp_path, review)
    _, _, _, findings = synthetic_run_inputs()
    factory = RecordingFactory(RecordingAnalyzer(findings))
    labels: list[str] = []

    def observe_read(path: Path, label: str) -> bytes:
        labels.append(label)
        if label == "calibration dataset":
            raise SyntheticAnalyzerError("failed admission reached dataset")
        try:
            return path.read_bytes()
        except OSError as error:
            raise CalibrationContractError(f"{label} is unavailable") from error

    monkeypatch.setattr(runner_io, "_read", observe_read)
    with pytest.raises(CalibrationContractError):
        _run_calibration_for_test(config_path, factory, tmp_path)

    assert "calibration dataset" not in labels
    assert factory.calls == 0
    assert all(not path.exists() for path in output_paths(tmp_path))
