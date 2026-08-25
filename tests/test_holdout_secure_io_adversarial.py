from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal, assert_never

import pytest

from polis.evaluation.holdout_models import HoldoutAdmissionError


def _layout(root: Path) -> tuple[Path, Path]:
    experiment = root / "experiments/a-b-one-shot"
    sealed = root / ".omo/sealed/a-b-one-shot-v1"
    experiment.mkdir(parents=True)
    sealed.mkdir(parents=True)
    (experiment / "config.json").write_bytes(b"trusted-config")
    (experiment / "dataset.manifest.json").write_bytes(b"trusted-manifest")
    (sealed / "merge-verification.json").write_bytes(b"trusted-merge")
    (sealed / "run-authorization.json").write_bytes(b"trusted-authorization")
    (sealed / "run-authorization.sig").write_bytes(b"trusted-signature")
    (sealed / "cases.json").write_bytes(b"trusted-dataset")
    return experiment, sealed


@pytest.mark.parametrize("reader", ["output", "evidence", "dataset"])
def test_workspace_rejects_hardlinked_sensitive_file(
    reader: Literal["output", "evidence", "dataset"],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, sealed = _layout(tmp_path)
    outside = tmp_path / "synthetic-outside"
    outside.write_bytes(b"synthetic-sensitive-bytes")
    match reader:
        case "output":
            destination = experiment / "report.json"
        case "evidence":
            destination = sealed / "run-authorization.json"
        case "dataset":
            destination = sealed / "cases.json"
        case unreachable:
            assert_never(unreachable)
    if destination.exists():
        destination.unlink()
    os.link(outside, destination)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    try:
        match reader:
            case "output":
                with pytest.raises(HoldoutAdmissionError):
                    workspace.read_output("report.json")
                with pytest.raises(HoldoutAdmissionError):
                    workspace.output_exists("report.json")
            case "evidence":
                with pytest.raises(HoldoutAdmissionError):
                    workspace.read_evidence("run-authorization.json")
            case "dataset":
                capability = workspace.reserve_dataset(
                    {"experiment_id": "synthetic"},
                    reserved_at="2026-08-25T00:00:00Z",
                )
                with pytest.raises(HoldoutAdmissionError):
                    workspace.read_dataset(capability)
            case unreachable:
                assert_never(unreachable)
    finally:
        workspace.close()


def test_workspace_rejects_in_place_mutation_during_secure_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    target = tmp_path / ".omo/sealed/a-b-one-shot-v1/merge-verification.json"
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    original_read: Callable[[int, int], bytes] = secure_io.os.read
    mutated = False

    def mutate_before_read(descriptor: int, size: int) -> bytes:
        nonlocal mutated
        if not mutated:
            target.write_bytes(b"mutated-merge")
            mutated = True
        return original_read(descriptor, size)

    monkeypatch.setattr(secure_io.os, "read", mutate_before_read)
    try:
        with pytest.raises(HoldoutAdmissionError, match="changed"):
            workspace.read_evidence("merge-verification.json")
    finally:
        workspace.close()
