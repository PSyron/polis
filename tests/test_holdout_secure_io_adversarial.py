from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Literal, assert_never

import pytest

from polis.evaluation.holdout_models import DatasetIdentity, HoldoutAdmissionError
from polis.evaluation.holdout_reservation import is_valid_consumption_capability


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


def _synthetic_dataset_identity(sha256: str = "synthetic-dataset") -> DatasetIdentity:
    return DatasetIdentity(
        sha256,
        0,
        0,
        0,
        "synthetic",
        "synthetic",
        "APPROVE",
        0,
        "0600",
    )


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
                workspace.bind_approved_dataset_identity(_synthetic_dataset_identity())
                capability = workspace.reserve_dataset(
                    {
                        "experiment_id": "synthetic",
                        "dataset_sha256": "synthetic-dataset",
                    },
                    reserved_at="2026-08-25T00:00:00Z",
                )
                with pytest.raises(HoldoutAdmissionError):
                    workspace.read_dataset(capability)
            case unreachable:
                assert_never(unreachable)
    finally:
        workspace.close()


@pytest.mark.parametrize("mutation", ["content", "size", "mode"])
def test_create_output_rejects_mutation_before_atomic_publication(
    mutation: Literal["content", "size", "mode"],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    original_fsync = secure_io.os.fsync
    mutated = False

    def mutate_after_fsync(descriptor: int) -> None:
        nonlocal mutated
        original_fsync(descriptor)
        if not mutated:
            match mutation:
                case "content":
                    os.pwrite(descriptor, b"ATTACK!", 0)
                case "size":
                    os.ftruncate(descriptor, 0)
                case "mode":
                    os.fchmod(descriptor, 0o644)
                case unreachable:
                    assert_never(unreachable)
            mutated = True

    monkeypatch.setattr(secure_io.os, "fsync", mutate_after_fsync)
    try:
        with pytest.raises(HoldoutAdmissionError, match="changed"):
            workspace.create_output("report.json", b"TRUSTED")
    finally:
        workspace.close()

    assert not (experiment / "report.json").exists()


def test_create_output_publishes_only_after_complete_file_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    original_link = secure_io.os.link
    target_states: list[bool] = []

    def observe_publication(
        source: str,
        destination: str,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        target_states.append((experiment / destination).exists())
        original_link(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(secure_io.os, "link", observe_publication)
    try:
        workspace.create_output("report.json", b"TRUSTED")
    finally:
        workspace.close()

    assert target_states == [False]
    assert (experiment / "report.json").read_bytes() == b"TRUSTED"


def test_dataset_capability_rejects_identity_not_matching_approved_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    workspace.bind_approved_dataset_identity(_synthetic_dataset_identity())
    try:
        with pytest.raises(HoldoutAdmissionError, match="dataset identity"):
            workspace.reserve_dataset(
                {
                    "experiment_id": "synthetic",
                    "dataset_sha256": "attacker-dataset",
                },
                reserved_at="2026-08-25T00:00:00Z",
            )
    finally:
        workspace.close()

    assert not (tmp_path / "experiments/a-b-one-shot/holdout.started").exists()


def test_close_invalidates_unconsumed_workspace_capability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    issuing_workspace = SecureHoldoutWorkspace.open(tmp_path)
    try:
        issuing_workspace.bind_approved_dataset_identity(_synthetic_dataset_identity())
        capability = issuing_workspace.reserve_dataset(
            {
                "experiment_id": "synthetic",
                "dataset_sha256": "synthetic-dataset",
            },
            reserved_at="2026-08-25T00:00:00Z",
        )
    finally:
        issuing_workspace.close()

    assert not is_valid_consumption_capability(capability)

    reading_workspace = SecureHoldoutWorkspace.open(tmp_path)
    try:
        reading_workspace.bind_approved_dataset_identity(_synthetic_dataset_identity())
        with pytest.raises(HoldoutAdmissionError, match="authorization"):
            reading_workspace.read_dataset(capability)
    finally:
        reading_workspace.close()


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
