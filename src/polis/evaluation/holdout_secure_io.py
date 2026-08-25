from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from polis.evaluation.holdout_models import HoldoutAdmissionError, JsonObject
from polis.evaluation.holdout_reservation import (
    CANONICAL_MARKER,
    HoldoutAlreadyConsumedError,
    _CanonicalWorkspaceIdentity,
    _ConsumptionCapability,
    consume_consumption_capability,
    reserve_consumption_secure,
)

_OUTPUT_NAMES: Final = frozenset(
    {
        "holdout.started",
        "report.json",
        "normalized-report.json",
        "result.manifest.json",
    }
)


def _secure_flags(*, directory: bool) -> int:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise HoldoutAdmissionError("required O_NOFOLLOW support is unavailable")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    return flags | os.O_DIRECTORY if directory else flags


def _open_directory(parent: int, name: str) -> int:
    try:
        descriptor = os.open(name, _secure_flags(directory=True), dir_fd=parent)
    except OSError as error:
        raise HoldoutAdmissionError(
            "secure holdout directory is unavailable"
        ) from error
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode):
        os.close(descriptor)
        raise HoldoutAdmissionError("secure holdout directory is invalid")
    return descriptor


@dataclass(frozen=True, slots=True)
class SecureFile:
    content: bytes
    mode: str


def _file_state(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        *_file_identity(metadata),
        metadata.st_mode,
        metadata.st_size,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def _file_identity(metadata: os.stat_result) -> tuple[int, ...]:
    return (metadata.st_dev, metadata.st_ino, metadata.st_nlink, metadata.st_mode)


def _read_file(parent: int, name: str) -> SecureFile:
    try:
        descriptor = os.open(name, _secure_flags(directory=False), dir_fd=parent)
    except OSError as error:
        raise HoldoutAdmissionError("secure holdout file is unavailable") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise HoldoutAdmissionError("secure holdout file is invalid")
        if before.st_nlink != 1:
            raise HoldoutAdmissionError("secure holdout file has multiple links")
        before_state = _file_state(before)
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 65536):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if _file_state(after) != before_state:
            raise HoldoutAdmissionError("secure holdout file changed during read")
        return SecureFile(b"".join(chunks), f"{stat.S_IMODE(before.st_mode):04o}")
    except OSError as error:
        raise HoldoutAdmissionError("secure holdout file read failed") from error
    finally:
        os.close(descriptor)


def _require_output_name(name: str) -> None:
    if name not in _OUTPUT_NAMES:
        raise HoldoutAdmissionError("unregistered holdout output")


class SecureHoldoutWorkspace:
    __slots__ = (
        "_config",
        "_experiment",
        "_reservation_workspace",
        "_root",
        "_sealed",
    )

    def __init__(
        self, root: int, experiment: int, sealed: int, config: SecureFile
    ) -> None:
        self._root = root
        self._experiment = experiment
        self._sealed = sealed
        self._config = config
        self._reservation_workspace = _CanonicalWorkspaceIdentity()

    @classmethod
    def open(cls, repository_root: Path) -> SecureHoldoutWorkspace:
        flags = _secure_flags(directory=True)
        try:
            root = os.open(repository_root, flags)
        except OSError as error:
            raise HoldoutAdmissionError("repository root is unavailable") from error
        opened = [root]
        try:
            root_identity = os.fstat(root)
            cwd_identity = os.stat(".", follow_symlinks=False)
            if (root_identity.st_dev, root_identity.st_ino) != (
                cwd_identity.st_dev,
                cwd_identity.st_ino,
            ):
                raise HoldoutAdmissionError(
                    "repository descriptor does not match current directory"
                )
            experiments = _open_directory(root, "experiments")
            opened.append(experiments)
            experiment = _open_directory(experiments, "a-b-one-shot")
            opened.append(experiment)
            omo = _open_directory(root, ".omo")
            opened.append(omo)
            sealed_root = _open_directory(omo, "sealed")
            opened.append(sealed_root)
            sealed = _open_directory(sealed_root, "a-b-one-shot-v1")
            opened.append(sealed)
            config = _read_file(experiment, "config.json")
        except (HoldoutAdmissionError, OSError):
            for descriptor in reversed(opened):
                os.close(descriptor)
            raise
        os.close(experiments)
        os.close(omo)
        os.close(sealed_root)
        return cls(root, experiment, sealed, config)

    def read_config(self) -> bytes:
        return self._config.content

    def read_manifest(self) -> bytes:
        return _read_file(self._experiment, "dataset.manifest.json").content

    def read_evidence(self, name: str) -> bytes:
        if name not in {
            "merge-verification.json",
            "run-authorization.json",
            "run-authorization.sig",
        }:
            raise HoldoutAdmissionError("unregistered evidence file")
        return _read_file(self._sealed, name).content

    def read_dataset(
        self, capability: _ConsumptionCapability | None = None
    ) -> SecureFile:
        try:
            consume_consumption_capability(
                capability,
                expected_marker=CANONICAL_MARKER,
                expected_workspace_identity=self._reservation_workspace,
            )
        except HoldoutAlreadyConsumedError as error:
            raise HoldoutAdmissionError(
                "sealed dataset read requires an active reservation authorization"
            ) from error
        return _read_file(self._sealed, "cases.json")

    def reserve_dataset(
        self, identity: JsonObject, *, reserved_at: str
    ) -> _ConsumptionCapability:
        return reserve_consumption_secure(
            CANONICAL_MARKER,
            identity,
            reserved_at=reserved_at,
            write_marker=self.create_output,
            workspace_identity=self._reservation_workspace,
        )

    def read_output(self, name: str) -> bytes:
        _require_output_name(name)
        return _read_file(self._experiment, name).content

    def output_exists(self, name: str) -> bool:
        _require_output_name(name)
        try:
            descriptor = os.open(
                name, _secure_flags(directory=False), dir_fd=self._experiment
            )
        except FileNotFoundError:
            return False
        except OSError as error:
            raise HoldoutAdmissionError("holdout output state is invalid") from error
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise HoldoutAdmissionError("holdout output state is invalid")
        finally:
            os.close(descriptor)
        return True

    def create_output(self, name: str, content: bytes) -> None:
        _require_output_name(name)
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | (_secure_flags(directory=False) & os.O_NOFOLLOW),
                0o600,
                dir_fd=self._experiment,
            )
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise HoldoutAdmissionError("exclusive holdout output failed")
            offset = 0
            while offset < len(content):
                offset += os.write(descriptor, content[offset:])
            os.fsync(descriptor)
            if _file_identity(os.fstat(descriptor)) != _file_identity(metadata):
                raise HoldoutAdmissionError("exclusive holdout output changed")
            os.fsync(self._experiment)
        except FileExistsError:
            raise
        except OSError as error:
            raise HoldoutAdmissionError("exclusive holdout output failed") from error
        finally:
            if "descriptor" in locals():
                os.close(descriptor)

    def close(self) -> None:
        for descriptor in (self._sealed, self._experiment, self._root):
            os.close(descriptor)
