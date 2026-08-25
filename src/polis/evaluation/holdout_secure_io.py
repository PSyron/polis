from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from polis.evaluation.holdout_models import HoldoutAdmissionError
from polis.evaluation.holdout_reservation import is_valid_consumption_capability


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


def _read_file(parent: int, name: str) -> SecureFile:
    try:
        descriptor = os.open(name, _secure_flags(directory=False), dir_fd=parent)
    except OSError as error:
        raise HoldoutAdmissionError("secure holdout file is unavailable") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise HoldoutAdmissionError("secure holdout file is invalid")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 65536):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise HoldoutAdmissionError("secure holdout file identity changed")
        return SecureFile(b"".join(chunks), f"{stat.S_IMODE(before.st_mode):04o}")
    except OSError as error:
        raise HoldoutAdmissionError("secure holdout file read failed") from error
    finally:
        os.close(descriptor)


class SecureHoldoutWorkspace:
    __slots__ = ("_config", "_experiment", "_root", "_sealed")

    def __init__(
        self, root: int, experiment: int, sealed: int, config: SecureFile
    ) -> None:
        self._root = root
        self._experiment = experiment
        self._sealed = sealed
        self._config = config

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

    def read_dataset(self, capability: object | None = None) -> SecureFile:
        if not is_valid_consumption_capability(capability):
            raise HoldoutAdmissionError(
                "sealed dataset read requires an active reservation authorization"
            )
        return _read_file(self._sealed, "cases.json")

    def read_output(self, name: str) -> bytes:
        return _read_file(self._experiment, name).content

    def output_exists(self, name: str) -> bool:
        try:
            descriptor = os.open(
                name, _secure_flags(directory=False), dir_fd=self._experiment
            )
        except FileNotFoundError:
            return False
        except OSError as error:
            raise HoldoutAdmissionError("holdout output state is invalid") from error
        os.close(descriptor)
        return True

    def create_output(self, name: str, content: bytes) -> None:
        if name not in {
            "holdout.started",
            "report.json",
            "normalized-report.json",
            "result.manifest.json",
        }:
            raise HoldoutAdmissionError("unregistered holdout output")
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
            offset = 0
            while offset < len(content):
                offset += os.write(descriptor, content[offset:])
            os.fsync(descriptor)
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
