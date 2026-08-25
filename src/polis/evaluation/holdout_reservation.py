from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from polis.evaluation.holdout_models import JsonObject


class HoldoutAlreadyConsumedError(RuntimeError):
    pass


class DurabilityFilesystem(Protocol):
    def open_exclusive(self, path: Path, content: bytes) -> int: ...
    def open_directory(self, path: Path) -> int: ...
    def fsync(self, descriptor: int) -> None: ...
    def close(self, descriptor: int) -> None: ...


class _ReservationSeal:
    pass


class _ReservationToken:
    def __init__(self, seal: _ReservationSeal) -> None:
        self.seal = seal
        self.consumed = False


_RESERVATION_SEAL = _ReservationSeal()
_ISSUED_TOKENS: set[_ReservationToken] = set()


@dataclass(frozen=True, slots=True)
class _ConsumptionCapability:
    marker_path: Path
    _token: _ReservationToken


class _OperatingSystemFilesystem:
    def open_exclusive(self, path: Path, content: bytes) -> int:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            offset = 0
            while offset < len(content):
                offset += os.write(descriptor, content[offset:])
        except OSError:
            os.close(descriptor)
            raise
        return descriptor

    def open_directory(self, path: Path) -> int:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        return os.open(path, flags)

    def fsync(self, descriptor: int) -> None:
        os.fsync(descriptor)

    def close(self, descriptor: int) -> None:
        os.close(descriptor)


def reserve_consumption(
    marker: Path,
    identity: JsonObject,
    *,
    reserved_at: str,
    filesystem: DurabilityFilesystem | None = None,
) -> _ConsumptionCapability:
    fs = filesystem or _OperatingSystemFilesystem()
    payload = {**identity, "reserved_at": reserved_at}
    content = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    marker.parent.mkdir(parents=True, exist_ok=True)
    try:
        marker_descriptor = fs.open_exclusive(marker, content)
    except FileExistsError as error:
        raise HoldoutAlreadyConsumedError("holdout already consumed") from error
    try:
        fs.fsync(marker_descriptor)
    finally:
        fs.close(marker_descriptor)
    directory_descriptor = fs.open_directory(marker.parent)
    try:
        fs.fsync(directory_descriptor)
    finally:
        fs.close(directory_descriptor)
    token = _ReservationToken(_RESERVATION_SEAL)
    _ISSUED_TOKENS.add(token)
    return _ConsumptionCapability(marker, token)


def reserve_consumption_secure(
    marker: Path,
    identity: JsonObject,
    *,
    reserved_at: str,
    write_marker: Callable[[str, bytes], None],
) -> _ConsumptionCapability:
    payload = {**identity, "reserved_at": reserved_at}
    content = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    try:
        write_marker(marker.name, content)
    except FileExistsError as error:
        raise HoldoutAlreadyConsumedError("holdout already consumed") from error
    token = _ReservationToken(_RESERVATION_SEAL)
    _ISSUED_TOKENS.add(token)
    return _ConsumptionCapability(marker, token)


def load_reserved_dataset[T](
    capability: _ConsumptionCapability,
    loader: Callable[[], T],
) -> T:
    if (
        not isinstance(capability, _ConsumptionCapability)
        or capability._token.seal is not _RESERVATION_SEAL
        or capability._token not in _ISSUED_TOKENS
    ):
        if (
            isinstance(capability, _ConsumptionCapability)
            and capability._token.consumed
        ):
            raise HoldoutAlreadyConsumedError("reservation capability already consumed")
        raise HoldoutAlreadyConsumedError("reservation capability is invalid")
    _ISSUED_TOKENS.remove(capability._token)
    capability._token.consumed = True
    return loader()


def reserve_and_load[T](
    marker: Path,
    identity: JsonObject,
    *,
    reserved_at: str,
    loader: Callable[[], T],
) -> T:
    capability = reserve_consumption(marker, identity, reserved_at=reserved_at)
    return load_reserved_dataset(capability, loader)


def is_valid_consumption_capability(value: object) -> bool:
    return (
        isinstance(value, _ConsumptionCapability)
        and value._token.seal is _RESERVATION_SEAL
        and value._token in _ISSUED_TOKENS
        and not value._token.consumed
    )
