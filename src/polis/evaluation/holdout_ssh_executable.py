from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from polis.evaluation.holdout_models import HoldoutAdmissionError


def _secure_flags(*, directory: bool) -> int:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        raise HoldoutAdmissionError("required POSIX no-follow flags are unavailable")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    return flags | os.O_DIRECTORY if directory else flags


@dataclass(frozen=True, slots=True)
class _VerifiedExecutable:
    path: Path
    descriptor: int
    device: int
    inode: int
    sha256: str
    system: str


def _open_posix_absolute(path: Path) -> int:
    parts = path.parts
    if not parts or parts[0] != "/":
        raise HoldoutAdmissionError("ssh-keygen path must be absolute")
    try:
        current = os.open("/", _secure_flags(directory=True))
    except OSError as error:
        raise HoldoutAdmissionError(
            "trusted ssh-keygen executable is unavailable"
        ) from error
    try:
        _validate_parent_directory(current)
        for component in parts[1:-1]:
            following = os.open(
                component, _secure_flags(directory=True), dir_fd=current
            )
            os.close(current)
            current = following
            _validate_parent_directory(current)
        return os.open(parts[-1], _secure_flags(directory=False), dir_fd=current)
    except OSError as error:
        raise HoldoutAdmissionError(
            "trusted ssh-keygen executable is unavailable"
        ) from error
    finally:
        os.close(current)


def _validate_parent_directory(descriptor: int) -> None:
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != 0
        or metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    ):
        raise HoldoutAdmissionError("trusted ssh-keygen parent directory is unsafe")


def _digest(descriptor: int) -> str:
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    while chunk := os.read(descriptor, 65536):
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest()


def _validate_identity(
    path: Path, descriptor: int, expected_sha256: str, system: str
) -> _VerifiedExecutable:
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        raise HoldoutAdmissionError("trusted ssh-keygen executable is not regular")
    if metadata.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise HoldoutAdmissionError("trusted ssh-keygen executable is writable")
    if metadata.st_uid != 0:
        raise HoldoutAdmissionError("trusted ssh-keygen executable owner is invalid")
    if system in {"Darwin", "Linux"} and not metadata.st_mode & stat.S_IXUSR:
        raise HoldoutAdmissionError("trusted ssh-keygen executable is not executable")
    observed = _digest(descriptor)
    if observed != expected_sha256:
        raise HoldoutAdmissionError("trusted ssh-keygen executable digest mismatch")
    path_metadata = os.stat(path, follow_symlinks=False)
    if (path_metadata.st_dev, path_metadata.st_ino) != (
        metadata.st_dev,
        metadata.st_ino,
    ):
        raise HoldoutAdmissionError("trusted ssh-keygen executable identity mismatch")
    return _VerifiedExecutable(
        path, descriptor, metadata.st_dev, metadata.st_ino, observed, system
    )


@contextmanager
def _verified_executable(
    path: Path, expected_sha256: str, system: str
) -> Iterator[_VerifiedExecutable]:
    if system != "Darwin":
        raise HoldoutAdmissionError("SSH executable platform is unsupported")
    descriptor = _open_posix_absolute(path)
    try:
        yield _validate_identity(path, descriptor, expected_sha256, system)
    except OSError as error:
        raise HoldoutAdmissionError(
            "trusted ssh-keygen identity check failed"
        ) from error
    finally:
        os.close(descriptor)


def _assert_stable(executable: _VerifiedExecutable) -> None:
    try:
        metadata = os.stat(executable.path, follow_symlinks=False)
        observed = _digest(executable.descriptor)
    except OSError as error:
        raise HoldoutAdmissionError("trusted ssh-keygen executable changed") from error
    if (metadata.st_dev, metadata.st_ino) != (
        executable.device,
        executable.inode,
    ) or observed != executable.sha256:
        raise HoldoutAdmissionError("trusted ssh-keygen executable changed")
