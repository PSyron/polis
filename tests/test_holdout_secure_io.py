from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

import pytest

from polis.evaluation.holdout_models import HoldoutAdmissionError
from polis.evaluation.holdout_reservation import reserve_consumption


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


def test_open_workspace_keeps_config_and_outputs_on_verified_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    replacement = tmp_path / "replacement-config"
    replacement.write_bytes(b"attacker-replacement")
    replacement.replace(experiment / "config.json")
    original = experiment.with_name("a-b-one-shot.original")
    experiment.rename(original)
    alternate = tmp_path / "alternate-experiment"
    alternate.mkdir()
    (alternate / "config.json").write_bytes(b"attacker-config")
    experiment.symlink_to(alternate, target_is_directory=True)
    try:
        assert workspace.read_config() == b"trusted-config"
        workspace.create_output("holdout.started", b"reserved\n")
    finally:
        workspace.close()

    assert (original / "holdout.started").read_bytes() == b"reserved\n"
    assert not (alternate / "holdout.started").exists()


def test_open_workspace_keeps_evidence_and_dataset_on_verified_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _experiment, sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    original = sealed.with_name("a-b-one-shot-v1.original")
    sealed.rename(original)
    alternate = tmp_path / "alternate-sealed"
    alternate.mkdir()
    for name in (
        "merge-verification.json",
        "run-authorization.json",
        "run-authorization.sig",
        "cases.json",
    ):
        (alternate / name).write_bytes(b"attacker")
    sealed.symlink_to(alternate, target_is_directory=True)
    try:
        assert workspace.read_evidence("merge-verification.json") == b"trusted-merge"
        assert workspace.read_evidence("run-authorization.json") == (
            b"trusted-authorization"
        )
        assert workspace.read_evidence("run-authorization.sig") == b"trusted-signature"
        with pytest.raises(HoldoutAdmissionError, match="authorization"):
            workspace.read_dataset()
    finally:
        workspace.close()


def test_dataset_capability_is_consumed_before_a_second_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    capability = reserve_consumption(
        tmp_path / "holdout.started",
        {"experiment_id": "synthetic"},
        reserved_at="2026-08-25T00:00:00Z",
    )
    try:
        assert workspace.read_dataset(capability).content == b"trusted-dataset"
        with pytest.raises(HoldoutAdmissionError, match="authorization"):
            workspace.read_dataset(capability)
    finally:
        workspace.close()


def test_concurrent_dataset_reads_allow_only_one_secure_file_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureFile, SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    capability = reserve_consumption(
        tmp_path / "holdout.started",
        {"experiment_id": "synthetic"},
        reserved_at="2026-08-25T00:00:00Z",
    )
    barrier = Barrier(2)
    read_started = Event()
    release_read = Event()
    original_read_file = secure_io._read_file

    def blocked_read(parent: int, name: str) -> SecureFile:
        if name == "cases.json":
            read_started.set()
            if not release_read.wait(timeout=2):
                raise AssertionError("synthetic dataset read was not released")
        return original_read_file(parent, name)

    monkeypatch.setattr(secure_io, "_read_file", blocked_read)

    def read_dataset() -> tuple[str, bytes | str]:
        barrier.wait(timeout=2)
        try:
            return "read", workspace.read_dataset(capability).content
        except HoldoutAdmissionError as error:
            return "denied", str(error)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(read_dataset) for _ in range(2)]
            assert read_started.wait(timeout=2)
            release_read.set()
            results = [future.result(timeout=2) for future in futures]
    finally:
        workspace.close()

    assert [result[0] for result in results].count("read") == 1
    assert [result[0] for result in results].count("denied") == 1


def test_workspace_rejects_symlinked_sensitive_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    (experiment / "config.json").unlink()
    outside = tmp_path / "outside-config"
    outside.write_bytes(b"attacker")
    (experiment / "config.json").symlink_to(outside)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(HoldoutAdmissionError):
        SecureHoldoutWorkspace.open(tmp_path)


@pytest.mark.parametrize(
    ("name", "reader"),
    [
        ("merge-verification.json", "evidence"),
        ("run-authorization.json", "evidence"),
        ("run-authorization.sig", "evidence"),
        ("cases.json", "dataset"),
    ],
)
def test_workspace_rejects_symlinked_sealed_files(
    name: str,
    reader: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _experiment, sealed = _layout(tmp_path)
    (sealed / name).unlink()
    outside = tmp_path / f"outside-{name}"
    outside.write_bytes(b"attacker")
    (sealed / name).symlink_to(outside)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    try:
        with pytest.raises(HoldoutAdmissionError):
            if reader == "dataset":
                workspace.read_dataset()
            else:
                workspace.read_evidence(name)
    finally:
        workspace.close()


@pytest.mark.parametrize("flag", ["O_NOFOLLOW", "O_DIRECTORY"])
def test_workspace_fails_closed_without_required_descriptor_support(
    flag: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.delattr(os, flag)

    with pytest.raises(HoldoutAdmissionError, match="required"):
        SecureHoldoutWorkspace.open(tmp_path)


def test_workspace_rejects_repository_descriptor_outside_current_directory(
    tmp_path: Path,
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)

    with pytest.raises(HoldoutAdmissionError, match="does not match current directory"):
        SecureHoldoutWorkspace.open(tmp_path)
