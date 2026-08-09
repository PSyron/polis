from __future__ import annotations

import hashlib
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
    workspace_commitment,
    write_workspace,
)
from tests.calibration_test_helpers import canonical_bytes

import polis.evaluation.calibration_runner_io as runner_io
from polis.evaluation.calibration_models import CalibrationContractError
from polis.evaluation.calibration_runner import (
    _run_calibration_for_test,
    _run_calibration_with_commitment_for_test,
    run_calibration,
)
from polis.evaluation.calibration_sources import SOURCE_ROWS


@pytest.fixture(autouse=True)
def _stable_sources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runner_io, "validate_live_sources", lambda: SOURCE_ROWS)


@pytest.mark.parametrize("mutation", ["text", "gold"])
def test_refreshed_content_bundle_cannot_replace_reviewed_case_payload(
    tmp_path: Path,
    mutation: Literal["text", "gold"],
) -> None:
    config_path = write_workspace(tmp_path)
    commitment = workspace_commitment(tmp_path)
    dataset_path = tmp_path / ".omo/sealed/a-b-calibration-v2-v1/cases.json"
    dataset = read_json(dataset_path)
    cases = dataset["cases"]
    assert isinstance(cases, list) and isinstance(cases[0], dict)
    if mutation == "text":
        cases[0]["text"] = "Błąd🙂 zastąpiony przypadek."
    else:
        findings = cases[0]["expected_findings"]
        assert isinstance(findings, list) and isinstance(findings[0], dict)
        findings[0]["suggestion"] = "Fałsz"
    refresh_dataset_binding(tmp_path, dataset)
    factory = RecordingFactory(RecordingAnalyzer({}, failure_call=1))

    with pytest.raises(CalibrationContractError, match="frozen commitment"):
        _run_calibration_with_commitment_for_test(
            config_path, factory, tmp_path, commitment
        )

    assert factory.calls == 0
    assert all(not path.exists() for path in output_paths(tmp_path))


@pytest.mark.parametrize("mutation", ["text", "gold"])
def test_review_payload_digest_is_recomputed_from_actual_case_content(
    tmp_path: Path,
    mutation: Literal["text", "gold"],
) -> None:
    config_path = write_workspace(tmp_path)
    experiment = tmp_path / "experiments/a-b-qualification-v2"
    dataset_path = tmp_path / ".omo/sealed/a-b-calibration-v2-v1/cases.json"
    dataset = read_json(dataset_path)
    cases = dataset["cases"]
    assert isinstance(cases, list) and isinstance(cases[0], dict)
    if mutation == "text":
        cases[0]["text"] = "Błąd🙂 inna zawartość."
    else:
        findings = cases[0]["expected_findings"]
        assert isinstance(findings, list) and isinstance(findings[0], dict)
        findings[0]["suggestion"] = "Inaczej"
    dataset_bytes = canonical_bytes(dataset)
    dataset_path.write_bytes(dataset_bytes)
    review = read_json(experiment / "calibration.review.json")
    review["dataset_sha256"] = hashlib.sha256(dataset_bytes).hexdigest()
    refresh_review_binding(tmp_path, review)
    manifest_path = experiment / "calibration.dataset.manifest.json"
    manifest = read_json(manifest_path)
    manifest["dataset_sha256"] = hashlib.sha256(dataset_bytes).hexdigest()
    manifest["dataset_size_bytes"] = len(dataset_bytes)
    manifest_path.write_bytes(canonical_bytes(manifest))
    factory = RecordingFactory(RecordingAnalyzer({}, failure_call=1))

    with pytest.raises(CalibrationContractError, match="membership"):
        _run_calibration_for_test(config_path, factory, tmp_path)

    assert factory.calls == 0
    assert all(not path.exists() for path in output_paths(tmp_path))


def test_public_runner_rejects_artifacts_outside_the_frozen_commitment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config_path = write_workspace(tmp_path)
    labels: list[str] = []

    def forbidden_factory() -> None:
        raise SyntheticAnalyzerError("mismatched commitment reached factory")

    def observe_read(path: Path, label: str) -> bytes:
        labels.append(label)
        return path.read_bytes()

    monkeypatch.setattr(
        runner_io,
        "require_canonical_calibration_config",
        lambda path, *, repository_root=None: path,
    )
    monkeypatch.setattr(runner_io, "_default_factory", forbidden_factory)
    monkeypatch.setattr(runner_io, "_read", observe_read)
    with pytest.raises(
        CalibrationContractError,
        match="artifacts do not match the frozen commitment",
    ):
        run_calibration(config_path)

    assert "calibration dataset" not in labels
    assert all(not path.exists() for path in output_paths(tmp_path))
