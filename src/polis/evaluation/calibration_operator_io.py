from __future__ import annotations

import os
import stat
from dataclasses import dataclass

from polis.evaluation.calibration_json import fail

_MAX_INPUT_BYTES = 32 * 1024 * 1024


def _flags(*, directory: bool) -> int:
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        fail("required secure filesystem flags are unavailable")
    flags = os.O_RDONLY | os.O_NOFOLLOW
    return flags | os.O_DIRECTORY if directory else flags


def _component(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        fail("operator path contract is invalid")
    return value


def _directory(parent: int, name: str) -> int:
    try:
        return os.open(_component(name), _flags(directory=True), dir_fd=parent)
    except OSError as error:
        raise OSError("secure directory admission failed") from error


def _file(parent: int, name: str) -> int:
    try:
        return os.open(_component(name), _flags(directory=False), dir_fd=parent)
    except OSError as error:
        raise OSError("secure file admission failed") from error


def _read_exact(descriptor: int, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = os.read(descriptor, min(remaining, 65_536))
        if not chunk:
            fail("operator input changed during read")
        chunks.append(chunk)
        remaining -= len(chunk)
    if os.read(descriptor, 1):
        fail("operator input changed during read")
    return b"".join(chunks)


def _write_all(descriptor: int, data: bytes) -> None:
    remaining = memoryview(data)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("secure output write failed")
        remaining = remaining[written:]


def _validate_file(info: os.stat_result, expected_mode: int) -> None:
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != expected_mode
        or not 0 < info.st_size <= _MAX_INPUT_BYTES
    ):
        fail("operator input file admission failed")


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_uid,
        stat.S_IMODE(info.st_mode),
    )


def _stable_read(parent: int, name: str, expected_mode: int) -> bytes:
    descriptor = _file(parent, name)
    try:
        before = os.fstat(descriptor)
        _validate_file(before, expected_mode)
        data = _read_exact(descriptor, before.st_size)
        after = os.fstat(descriptor)
        reopened = _file(parent, name)
        try:
            current = os.fstat(reopened)
        finally:
            os.close(reopened)
        if _identity(before) != _identity(after) or _identity(after) != _identity(
            current
        ):
            fail("operator input changed during read")
        return data
    finally:
        os.close(descriptor)


def _admit_git_marker(parent: int) -> None:
    try:
        marker = os.stat(".git", dir_fd=parent, follow_symlinks=False)
    except OSError as error:
        raise OSError("repository marker admission failed") from error
    if stat.S_ISDIR(marker.st_mode):
        directory = _directory(parent, ".git")
        os.close(directory)
        return
    if not stat.S_ISREG(marker.st_mode):
        fail("repository marker admission failed")
    raw = _stable_read(parent, ".git", 0o644)
    if (
        len(raw) > 4096
        or not raw.startswith(b"gitdir: /")
        or not raw.endswith(b"\n")
        or raw.count(b"\n") != 1
        or b"\x00" in raw
        or b"\r" in raw
    ):
        fail("repository marker admission failed")


@dataclass(frozen=True, slots=True)
class _SecureRepository:
    descriptor: int

    @classmethod
    def open(cls) -> _SecureRepository:
        try:
            descriptor = os.open(".", _flags(directory=True))
        except OSError as error:
            raise OSError("repository root admission failed") from error
        admitted = False
        try:
            root = os.fstat(descriptor)
            if root.st_uid != os.getuid():
                fail("repository root admission failed")
            _admit_git_marker(descriptor)
            project = _file(descriptor, "pyproject.toml")
            try:
                _validate_file(os.fstat(project), 0o644)
            finally:
                os.close(project)
            admitted = True
            return cls(descriptor)
        finally:
            if not admitted:
                os.close(descriptor)

    def close(self) -> None:
        os.close(self.descriptor)

    def _parent(self, parts: tuple[str, ...]) -> tuple[int, str]:
        if len(parts) < 2:
            fail("operator path contract is invalid")
        current = os.dup(self.descriptor)
        admitted = False
        try:
            for component in parts[:-1]:
                child = _directory(current, component)
                os.close(current)
                current = child
            admitted = True
            return current, _component(parts[-1])
        finally:
            if not admitted:
                os.close(current)

    def read(self, parts: tuple[str, ...], *, expected_mode: int) -> bytes:
        parent, name = self._parent(parts)
        try:
            return _stable_read(parent, name, expected_mode)
        finally:
            os.close(parent)

    def create(self, parts: tuple[str, ...], data: bytes) -> None:
        parent, name = self._parent(parts)
        descriptor: int | None = None
        created = False
        completed = False
        try:
            descriptor = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            )
            created = True
            _write_all(descriptor, data)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            os.fsync(parent)
            completed = True
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if created and not completed:
                os.unlink(name, dir_fd=parent)
                os.fsync(parent)
            os.close(parent)


def _open_repository() -> _SecureRepository:
    return _SecureRepository.open()
