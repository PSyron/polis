from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from typing import Literal, assert_never

import pytest
from tests.holdout_config_fixture import synthetic_config
from tests.test_holdout_manifest import synthetic_manifest

from polis.evaluation.holdout_admission import (
    ExternalAdmission,
    _register_external_admission,
)
from polis.evaluation.holdout_contract import canonical_sha256, parse_holdout_config
from polis.evaluation.holdout_models import (
    AdmissionEvidence,
    DatasetIdentity,
    HoldoutAdmissionError,
)
from polis.evaluation.holdout_reservation import is_valid_consumption_capability
from polis.evaluation.holdout_sources import source_sha256

TRUSTED_DATASET = b"trusted-dataset"
TRUSTED_DATASET += b"\0" * (17370 - len(TRUSTED_DATASET))
TRUSTED_DATASET_SHA256 = hashlib.sha256(TRUSTED_DATASET).hexdigest()
MERGE_COMMIT = "a" * 40
VERIFICATION_PAYLOAD = {
    "verified": True,
    "reason": "valid",
    "signature": "synthetic-signature",
    "payload": "synthetic-payload",
    "verified_at": "2026-08-25T00:00:00Z",
}


@pytest.fixture(autouse=True)
def _patch_synthetic_dataset_hash(monkeypatch: pytest.MonkeyPatch) -> None:
    import polis.evaluation.holdout_config_dataset as config_dataset

    monkeypatch.setattr(config_dataset, "DATASET_SHA256", TRUSTED_DATASET_SHA256)


def _layout(root: Path) -> tuple[Path, Path]:
    trusted_dataset = TRUSTED_DATASET
    trusted_dataset_sha256 = hashlib.sha256(trusted_dataset).hexdigest()
    experiment = root / "experiments/a-b-one-shot"
    sealed = root / ".omo/sealed/a-b-one-shot-v1"
    experiment.mkdir(parents=True)
    sealed.mkdir(parents=True)
    config = synthetic_config()
    dataset_config = config["dataset"]
    assert isinstance(dataset_config, dict)
    dataset_config["sha256"] = trusted_dataset_sha256
    dataset_config["size_bytes"] = len(trusted_dataset)
    (experiment / "config.json").write_text(json.dumps(config), encoding="utf-8")
    manifest = synthetic_manifest()
    manifest["sha256"] = trusted_dataset_sha256
    manifest["size_bytes"] = len(trusted_dataset)
    (experiment / "dataset.manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (sealed / "merge-verification.json").write_text(
        json.dumps(
            {
                "schema_id": "polis.a-b-one-shot.merge-verification",
                "schema_version": 1,
                "evaluated_source_sha": MERGE_COMMIT,
                "evaluated_source_tree_sha256": "b" * 40,
                "github_verification": VERIFICATION_PAYLOAD,
                "github_verification_sha256": canonical_sha256(VERIFICATION_PAYLOAD),
            }
        ),
        encoding="utf-8",
    )
    (sealed / "run-authorization.json").write_bytes(b"trusted-authorization")
    (sealed / "run-authorization.sig").write_bytes(b"trusted-signature")
    (sealed / "cases.json").write_bytes(trusted_dataset)
    (sealed / "cases.json").chmod(0o600)
    return experiment, sealed


def _admission() -> ExternalAdmission:
    config = synthetic_config()
    dataset = config["dataset"]
    assert isinstance(dataset, dict)
    dataset["sha256"] = TRUSTED_DATASET_SHA256
    dataset["size_bytes"] = len(TRUSTED_DATASET)
    parsed = parse_holdout_config(config)
    return _register_external_admission(
        ExternalAdmission(
            AdmissionEvidence(
                canonical_sha256(config),
                source_sha256(parsed),
                "b" * 40,
                TRUSTED_DATASET_SHA256,
                MERGE_COMMIT,
                True,
                "valid",
                canonical_sha256(VERIFICATION_PAYLOAD),
            ),
            "c" * 64,
            "d" * 64,
            "e" * 64,
        ),
    )


def _synthetic_dataset_identity(
    sha256: str = TRUSTED_DATASET_SHA256,
) -> DatasetIdentity:
    return DatasetIdentity(
        sha256,
        len(TRUSTED_DATASET),
        0,
        0,
        "synthetic",
        "synthetic",
        "APPROVE",
        0,
        "0600",
    )


def test_bind_rejects_manifest_identity_not_bound_to_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    manifest_path = tmp_path / "experiments/a-b-one-shot/dataset.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    try:
        with pytest.raises(HoldoutAdmissionError, match="manifest is invalid"):
            workspace.bind_approved_dataset_identity()
    finally:
        workspace.close()


def test_reserve_rejects_forged_complete_admission_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    workspace.bind_approved_dataset_identity()
    admission = _admission()
    forged = replace(
        admission, evidence=replace(admission.evidence, source_sha256="forged")
    )
    try:
        with pytest.raises(HoldoutAdmissionError, match="admission"):
            workspace.reserve_dataset(forged, reserved_at="2026-08-25T00:00:00Z")
    finally:
        workspace.close()

    assert not (experiment / "holdout.started").exists()


def test_reserve_rejects_caller_forged_admission_with_matching_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    workspace.bind_approved_dataset_identity()
    trusted = _admission()
    forged = ExternalAdmission(
        trusted.evidence,
        "f" * 64,
        "f" * 64,
        "f" * 64,
    )
    try:
        with pytest.raises(HoldoutAdmissionError, match="proof"):
            workspace.reserve_dataset(forged, reserved_at="2026-08-25T00:00:00Z")
    finally:
        workspace.close()

    assert not (tmp_path / "experiments/a-b-one-shot/holdout.started").exists()


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
                workspace.bind_approved_dataset_identity()
                capability = workspace.reserve_dataset(
                    _admission(),
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


def test_read_output_rejects_mutated_output_after_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    try:
        workspace.create_output("report.json", b"TRUSTED")
        (experiment / "report.json").write_bytes(b"ATTACK!")
        with pytest.raises(HoldoutAdmissionError, match="output"):
            workspace.read_output("report.json")
    finally:
        workspace.close()


def test_output_exists_rejects_mutated_output_after_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    try:
        workspace.create_output("report.json", b"REPORT")
        (tmp_path / "experiments/a-b-one-shot/report.json").write_bytes(b"MUTATE")
        with pytest.raises(HoldoutAdmissionError, match="trusted holdout output"):
            workspace.output_exists("report.json")
    finally:
        workspace.close()


def test_read_output_rejects_unregistered_preexisting_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    (experiment / "report.json").write_bytes(b"ATTACKER")
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    try:
        with pytest.raises(HoldoutAdmissionError, match="unregistered"):
            workspace.read_output("report.json")
    finally:
        workspace.close()


def test_publication_failure_blocks_other_workspace_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    first = SecureHoldoutWorkspace.open(tmp_path)
    second = SecureHoldoutWorkspace.open(tmp_path)
    first_in_publication = Event()
    release_first = Event()
    original_verify = secure_io._verify_published_destination

    def fail_first_publication(
        parent: int,
        name: str,
        source_descriptor: int,
        expected_content: bytes,
        expected_links: int,
        expected_state: tuple[int, ...],
    ) -> None:
        if name == "report.json":
            first_in_publication.set()
            assert release_first.wait(timeout=2)
            raise HoldoutAdmissionError("synthetic publication failure")
        original_verify(
            parent,
            name,
            source_descriptor,
            expected_content,
            expected_links,
            expected_state,
        )

    monkeypatch.setattr(
        secure_io, "_verify_published_destination", fail_first_publication
    )

    def publish_second() -> str:
        try:
            second.create_output("normalized-report.json", b"SECOND")
        except HoldoutAdmissionError as error:
            return str(error)
        return "published"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first_future = executor.submit(first.create_output, "report.json", b"FIRST")
            assert first_in_publication.wait(timeout=2)
            second_future = executor.submit(publish_second)
            assert not second_future.done()
            release_first.set()
            with pytest.raises(HoldoutAdmissionError, match="publication failure"):
                first_future.result(timeout=2)
            assert "permanent" in second_future.result(timeout=2)
    finally:
        first.close()
        second.close()

    assert (experiment / "holdout.publication.failed").exists()
    assert not (experiment / "normalized-report.json").exists()


def test_create_output_rejects_destination_removed_after_source_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    original_verify = secure_io._verify_output
    removed = False

    def remove_destination_after_verification(
        descriptor: int,
        expected_content: bytes,
        expected_links: int,
        expected_state: tuple[int, ...],
    ) -> None:
        nonlocal removed
        original_verify(descriptor, expected_content, expected_links, expected_state)
        if expected_links == 2 and not removed:
            (experiment / "report.json").unlink()
            removed = True

    monkeypatch.setattr(
        secure_io, "_verify_output", remove_destination_after_verification
    )
    try:
        with pytest.raises(HoldoutAdmissionError, match="destination"):
            workspace.create_output("report.json", b"TRUSTED")
    finally:
        workspace.close()

    assert not (experiment / "report.json").exists()
    assert (experiment / "holdout.publication.failed").exists()


def test_create_output_replaces_attacker_destination_after_post_link_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    original_verify = secure_io._verify_output
    attacker = tmp_path / "synthetic-attacker-output"
    replaced = False

    def replace_destination_after_verification(
        descriptor: int,
        expected_content: bytes,
        expected_links: int,
        expected_state: tuple[int, ...],
    ) -> None:
        nonlocal replaced
        original_verify(descriptor, expected_content, expected_links, expected_state)
        if expected_links == 2 and not replaced:
            attacker.write_bytes(b"ATTACKER")
            (experiment / "report.json").unlink()
            os.link(attacker, experiment / "report.json")
            replaced = True

    monkeypatch.setattr(
        secure_io, "_verify_output", replace_destination_after_verification
    )
    try:
        with pytest.raises(HoldoutAdmissionError, match="destination"):
            workspace.create_output("report.json", b"TRUSTED")
    finally:
        workspace.close()

    assert (experiment / "report.json").read_bytes() == b"ATTACKER"
    assert (experiment / "holdout.publication.failed").exists()


def test_create_output_rejects_destination_replacement_after_temp_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    original_unlink = secure_io.os.unlink
    attacker = tmp_path / "synthetic-attacker-output"
    attacker.write_bytes(b"ATTACKER")
    replaced = False

    def replace_after_temp_cleanup(
        name: str | bytes,
        *,
        dir_fd: int | None = None,
    ) -> None:
        nonlocal replaced
        original_unlink(name, dir_fd=dir_fd)
        if not replaced and isinstance(name, str) and name.startswith(".report.json."):
            destination = experiment / "report.json"
            destination.unlink()
            os.link(attacker, destination)
            replaced = True

    monkeypatch.setattr(secure_io.os, "unlink", replace_after_temp_cleanup)
    try:
        with pytest.raises(HoldoutAdmissionError, match="ownership changed"):
            workspace.create_output("report.json", b"TRUSTED")
    finally:
        workspace.close()

    assert (experiment / "report.json").read_bytes() == b"ATTACKER"
    assert (experiment / "holdout.publication.failed").exists()


def test_successful_publication_fsyncs_parent_after_temp_hardlink_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    original_fsync = secure_io.os.fsync
    original_unlink = secure_io.os.unlink
    events: list[str] = []

    def record_fsync(descriptor: int) -> None:
        if descriptor == workspace._experiment:
            events.append("fsync")
        original_fsync(descriptor)

    def record_unlink(name: str | bytes, *, dir_fd: int | None = None) -> None:
        if isinstance(name, str) and name.startswith(".report.json."):
            events.append("unlink-temp")
        original_unlink(name, dir_fd=dir_fd)

    monkeypatch.setattr(secure_io.os, "fsync", record_fsync)
    monkeypatch.setattr(secure_io.os, "unlink", record_unlink)
    try:
        workspace.create_output("report.json", b"TRUSTED")
    finally:
        workspace.close()

    unlink_index = events.index("unlink-temp")
    assert "fsync" in events[unlink_index + 1 :]


def test_post_publication_oserror_creates_permanent_failure_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)

    def fail_after_publication(*_args: object, **_kwargs: object) -> None:
        raise OSError("synthetic post-publication I/O failure")

    monkeypatch.setattr(
        secure_io, "_verify_published_destination", fail_after_publication
    )
    try:
        with pytest.raises(HoldoutAdmissionError, match="exclusive holdout output"):
            workspace.create_output("report.json", b"TRUSTED")
        assert (experiment / "holdout.publication.failed").exists()
        with pytest.raises(HoldoutAdmissionError, match="permanent"):
            workspace.create_output("report.json", b"RETRY")
    finally:
        workspace.close()


def test_create_output_keeps_published_marker_after_post_publication_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    original_verify = secure_io._verify_output

    def fail_after_publication(
        descriptor: int,
        expected_content: bytes,
        expected_links: int,
        expected_state: tuple[int, ...],
    ) -> None:
        original_verify(descriptor, expected_content, expected_links, expected_state)
        if expected_links == 2:
            raise HoldoutAdmissionError("synthetic post-publication failure")

    monkeypatch.setattr(secure_io, "_verify_output", fail_after_publication)
    try:
        with pytest.raises(HoldoutAdmissionError, match="post-publication"):
            workspace.create_output("holdout.started", b"reserved\n")
    finally:
        workspace.close()

    assert (experiment / "holdout.started").read_bytes() == b"reserved\n"


def test_post_publication_failure_removes_temporary_hardlink_and_syncs_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    original_verify = secure_io._verify_output
    original_fsync = secure_io.os.fsync
    parent_syncs: list[int] = []

    def record_fsync(descriptor: int) -> None:
        if descriptor == workspace._experiment:
            parent_syncs.append(descriptor)
        original_fsync(descriptor)

    def fail_after_publication(
        descriptor: int,
        expected_content: bytes,
        expected_links: int,
        expected_state: tuple[int, ...],
    ) -> None:
        original_verify(descriptor, expected_content, expected_links, expected_state)
        if expected_links == 2:
            raise HoldoutAdmissionError("synthetic post-publication failure")

    monkeypatch.setattr(secure_io.os, "fsync", record_fsync)
    monkeypatch.setattr(secure_io, "_verify_output", fail_after_publication)
    try:
        with pytest.raises(HoldoutAdmissionError, match="post-publication"):
            workspace.create_output("holdout.started", b"reserved\n")
    finally:
        workspace.close()

    marker = experiment / "holdout.started"
    assert marker.read_bytes() == b"reserved\n"
    assert marker.stat().st_nlink == 1
    assert not list(experiment.glob(".holdout.started.*"))
    assert parent_syncs


def test_staging_cleanup_failure_is_permanent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    original_rmdir = secure_io.os.rmdir

    def fail_staging_cleanup(path: str, *, dir_fd: int | None = None) -> None:
        if path.startswith(".holdout-staging."):
            raise OSError("synthetic staging cleanup failure")
        original_rmdir(path, dir_fd=dir_fd)

    monkeypatch.setattr(secure_io.os, "rmdir", fail_staging_cleanup)
    try:
        with pytest.raises(HoldoutAdmissionError, match="staging cleanup"):
            workspace.create_output("report.json", b"REPORT")
        assert (experiment / "holdout.publication.failed").exists()
        with pytest.raises(HoldoutAdmissionError, match="permanent"):
            workspace.create_output("normalized-report.json", b"BLOCKED")
    finally:
        workspace.close()


def test_publication_lock_serializes_processes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    parent = os.open(experiment, os.O_RDONLY | os.O_DIRECTORY)
    ready = tmp_path / "publication-lock-ready"
    script = """
import os
import sys
from pathlib import Path
from polis.evaluation.holdout_secure_io import _publication_lock

parent = os.open(sys.argv[1], os.O_RDONLY | os.O_DIRECTORY)
with _publication_lock(parent):
    Path(sys.argv[2]).write_text("ready", encoding="utf-8")
    input()
os.close(parent)
"""
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            script,
            str(experiment),
            str(ready),
        ],
        stdin=subprocess.PIPE,
        text=True,
    )
    try:
        with secure_io._publication_lock(parent):
            time.sleep(0.2)
            assert not ready.exists()
        deadline = time.monotonic() + 2
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists()
        assert process.stdin is not None
        process.stdin.write("\n")
        process.stdin.flush()
        assert process.wait(timeout=2) == 0
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=2)
        os.close(parent)


def test_create_output_keeps_published_marker_after_post_publication_fsync_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    experiment, _sealed = _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    original_fsync = secure_io.os.fsync

    def fail_experiment_fsync(descriptor: int) -> None:
        if descriptor == workspace._experiment:
            raise OSError("synthetic publication fsync failure")
        original_fsync(descriptor)

    monkeypatch.setattr(secure_io.os, "fsync", fail_experiment_fsync)
    try:
        with pytest.raises(HoldoutAdmissionError, match="exclusive holdout output"):
            workspace.create_output("holdout.started", b"reserved\n")
        assert (experiment / "holdout.started").read_bytes() == b"reserved\n"
        with pytest.raises(HoldoutAdmissionError, match="permanent"):
            workspace.create_output("holdout.started", b"replacement\n")
    finally:
        workspace.close()


def test_workspace_rejects_operation_after_close_even_when_descriptor_is_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    experiment_descriptor = workspace._experiment
    workspace.close()
    workspace.close()

    attacker = tmp_path / "attacker-directory"
    attacker.mkdir()
    (attacker / "report.json").write_bytes(b"attacker")
    attacker_descriptor = os.open(attacker, os.O_RDONLY | os.O_DIRECTORY)
    os.dup2(attacker_descriptor, experiment_descriptor)
    if attacker_descriptor != experiment_descriptor:
        os.close(attacker_descriptor)
    try:
        with pytest.raises(HoldoutAdmissionError, match="closed"):
            workspace.read_output("report.json")
    finally:
        os.close(experiment_descriptor)


def test_capability_claims_cannot_be_rewrapped_for_another_workspace(
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
        _admission(),
        reserved_at="2026-08-25T00:00:00Z",
    )
    object.__setattr__(capability, "_token", object())
    try:
        with pytest.raises(HoldoutAdmissionError, match="authorization"):
            reading_workspace.read_dataset(capability)
        assert issuing_workspace.read_dataset(capability).content == TRUSTED_DATASET
    finally:
        issuing_workspace.close()
        reading_workspace.close()


def test_direct_token_claim_mutation_cannot_redirect_capability(
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
        _admission(),
        reserved_at="2026-08-25T00:00:00Z",
    )
    try:
        with pytest.raises(AttributeError):
            object.__setattr__(
                capability._token,
                "_claims",
                replace(
                    capability._token._claims,
                    workspace_identity=reading_workspace._reservation_workspace,
                ),
            )
        with pytest.raises(HoldoutAdmissionError, match="authorization"):
            reading_workspace.read_dataset(capability)
        assert issuing_workspace.read_dataset(capability).content == TRUSTED_DATASET
    finally:
        issuing_workspace.close()
        reading_workspace.close()


def test_workspace_rejects_dataset_append_before_unbounded_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import polis.evaluation.holdout_secure_io as secure_io
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    dataset_path = tmp_path / ".omo/sealed/a-b-one-shot-v1/cases.json"
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    workspace.bind_approved_dataset_identity()
    capability = workspace.reserve_dataset(
        _admission(),
        reserved_at="2026-08-25T00:00:00Z",
    )
    original_read: Callable[[int, int], bytes] = os.read
    appended = False

    def append_before_read(descriptor: int, size: int) -> bytes:
        nonlocal appended
        if not appended:
            dataset_path.write_bytes(dataset_path.read_bytes() + b"x" * 100_000)
            appended = True
        return original_read(descriptor, size)

    monkeypatch.setattr(secure_io.os, "read", append_before_read)
    try:
        with pytest.raises(HoldoutAdmissionError, match="size bound"):
            workspace.read_dataset(capability)
    finally:
        workspace.close()


def test_secure_boundary_rejects_same_size_dataset_with_forged_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    dataset_path = tmp_path / ".omo/sealed/a-b-one-shot-v1/cases.json"
    dataset_path.write_bytes(b"trusted-dataseX" + b"\0" * (17370 - 15))
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    workspace.bind_approved_dataset_identity()
    capability = workspace.reserve_dataset(
        _admission(),
        reserved_at="2026-08-25T00:00:00Z",
    )
    try:
        with pytest.raises(HoldoutAdmissionError, match="digest"):
            workspace.read_dataset(capability)
    finally:
        workspace.close()


def test_dataset_capability_rejects_identity_not_matching_approved_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polis.evaluation.holdout_secure_io import SecureHoldoutWorkspace

    _layout(tmp_path)
    monkeypatch.chdir(tmp_path)
    workspace = SecureHoldoutWorkspace.open(tmp_path)
    workspace.bind_approved_dataset_identity()
    try:
        with pytest.raises(HoldoutAdmissionError, match="admission evidence"):
            forged = replace(
                _admission(),
                evidence=replace(
                    _admission().evidence, dataset_sha256="attacker-dataset"
                ),
            )
            workspace.reserve_dataset(forged, reserved_at="2026-08-25T00:00:00Z")
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
        issuing_workspace.bind_approved_dataset_identity()
        capability = issuing_workspace.reserve_dataset(
            _admission(),
            reserved_at="2026-08-25T00:00:00Z",
        )
    finally:
        issuing_workspace.close()

    assert not is_valid_consumption_capability(capability)

    reading_workspace = SecureHoldoutWorkspace.open(tmp_path)
    try:
        reading_workspace.bind_approved_dataset_identity()
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
