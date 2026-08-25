from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

import pytest

from polis.evaluation.holdout_models import HoldoutAdmissionError
from polis.evaluation.holdout_reservation import (
    CANONICAL_MARKER,
    HoldoutAlreadyConsumedError,
    _CanonicalWorkspaceIdentity,
    _ConsumptionCapability,
    consume_consumption_capability,
    reserve_consumption,
)

TRUSTED_DATASET = b"trusted-dataset"
TRUSTED_DATASET_SHA256 = hashlib.sha256(TRUSTED_DATASET).hexdigest()


def _layout(root: Path) -> tuple[Path, Path]:
    experiment = root / "experiments/a-b-one-shot"
    sealed = root / ".omo/sealed/a-b-one-shot-v1"
    experiment.mkdir(parents=True)
    sealed.mkdir(parents=True)
    (experiment / "config.json").write_bytes(b"trusted-config")
    manifest = {
        "schema_id": "polis.a-b-one-shot.dataset-manifest",
        "schema_version": 1,
        "dataset_id": "synthetic",
        "dataset_schema": "polis.a-b-one-shot.dataset/1",
        "sha256": TRUSTED_DATASET_SHA256,
        "size_bytes": len(TRUSTED_DATASET),
        "mode": "0600",
        "case_count": 0,
        "source_count": 0,
        "expected_finding_count": 0,
        "role_counts": {"error": 0, "correct": 0, "abstain": 0, "conflict": 0},
        "license": "CC0-1.0",
        "provenance": "synthetic",
        "review": {
            "reviewer_role": "synthetic-reviewer",
            "verdict": "APPROVE",
            "reviewed_case_count": 0,
            "total_case_count": 0,
            "reviewed_source_count": 0,
            "review_manifest_sha256": "0" * 64,
            "review_payload_sha256": "1" * 64,
            "analyzer_executed": False,
            "protected_artifacts_used": False,
        },
        "plaintext_in_repository": False,
    }
    (experiment / "dataset.manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (sealed / "merge-verification.json").write_bytes(b"trusted-merge")
    (sealed / "run-authorization.json").write_bytes(b"trusted-authorization")
    (sealed / "run-authorization.sig").write_bytes(b"trusted-signature")
    (sealed / "cases.json").write_bytes(TRUSTED_DATASET)
    (sealed / "cases.json").chmod(0o600)
    return experiment, sealed


def _cleanup_capability(
    capability: _ConsumptionCapability,
    workspace_identity: _CanonicalWorkspaceIdentity,
) -> None:
    try:
        consume_consumption_capability(
            capability,
            expected_marker=CANONICAL_MARKER,
            expected_workspace_identity=workspace_identity,
        )
    except HoldoutAlreadyConsumedError:
        return


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
    workspace.bind_approved_dataset_identity()
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
    workspace.bind_approved_dataset_identity()
    capability = workspace.reserve_dataset(
        {"experiment_id": "synthetic", "dataset_sha256": TRUSTED_DATASET_SHA256},
        reserved_at="2026-08-25T00:00:00Z",
    )
    try:
        assert workspace.read_dataset(capability).content == b"trusted-dataset"
        with pytest.raises(HoldoutAdmissionError, match="authorization"):
            workspace.read_dataset(capability)
    finally:
        workspace.close()


def test_arbitrary_marker_capability_cannot_read_canonical_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    workspace.bind_approved_dataset_identity()
    capability = reserve_consumption(
        tmp_path / "arbitrary.marker",
        {"experiment_id": "synthetic"},
        reserved_at="2026-08-25T00:00:00Z",
    )
    try:
        with pytest.raises(HoldoutAdmissionError, match="authorization"):
            workspace.read_dataset(capability)
    finally:
        workspace.close()


def test_capability_from_another_workspace_cannot_read_canonical_dataset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    issuing_workspace = SecureHoldoutWorkspace.open(tmp_path)
    reading_workspace = SecureHoldoutWorkspace.open(tmp_path)
    issuing_workspace.bind_approved_dataset_identity()
    reading_workspace.bind_approved_dataset_identity()
    capability = issuing_workspace.reserve_dataset(
        {"experiment_id": "synthetic", "dataset_sha256": TRUSTED_DATASET_SHA256},
        reserved_at="2026-08-25T00:00:00Z",
    )
    try:
        with pytest.raises(HoldoutAdmissionError, match="authorization"):
            reading_workspace.read_dataset(capability)
        assert issuing_workspace.read_dataset(capability).content == (
            b"trusted-dataset"
        )
    finally:
        _cleanup_capability(capability, issuing_workspace._reservation_workspace)
        reading_workspace.close()
        issuing_workspace.close()


def test_concurrent_dataset_reads_allow_only_one_secure_file_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureFile, SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    workspace.bind_approved_dataset_identity()
    capability = workspace.reserve_dataset(
        {"experiment_id": "synthetic", "dataset_sha256": TRUSTED_DATASET_SHA256},
        reserved_at="2026-08-25T00:00:00Z",
    )
    barrier = Barrier(2)
    read_started = Event()
    release_read = Event()
    original_read_file = secure_io._read_file

    def blocked_read(
        parent: int,
        name: str,
        *,
        max_size: int,
        expected_size: int | None = None,
    ) -> SecureFile:
        if name == "cases.json":
            read_started.set()
            if not release_read.wait(timeout=2):
                raise AssertionError("synthetic dataset read was not released")
        return original_read_file(
            parent,
            name,
            max_size=max_size,
            expected_size=expected_size,
        )

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
    "name",
    [
        "../../.omo/sealed/a-b-one-shot-v1/cases.json",
        "nested/report.json",
    ],
)
def test_workspace_rejects_output_path_traversal_for_output_access(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    try:
        with pytest.raises(HoldoutAdmissionError, match="unregistered holdout output"):
            workspace.read_output(name)
        with pytest.raises(HoldoutAdmissionError, match="unregistered holdout output"):
            workspace.output_exists(name)
    finally:
        workspace.close()


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
