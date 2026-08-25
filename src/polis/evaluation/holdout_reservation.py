from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
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


class _CanonicalWorkspaceIdentity:
    pass


class _ReservationToken:
    __slots__ = (
        "_seal",
        "_workspace_identity",
        "_marker_path",
        "_dataset_identity",
        "consumed",
    )

    def __init__(
        self,
        seal: _ReservationSeal,
        workspace_identity: _CanonicalWorkspaceIdentity | None,
        marker_path: Path,
        dataset_identity: str | None,
    ) -> None:
        self._seal = seal
        self._workspace_identity = workspace_identity
        self._marker_path = marker_path
        self._dataset_identity = dataset_identity
        self.consumed = False

    @property
    def seal(self) -> _ReservationSeal:
        return self._seal

    @property
    def workspace_identity(self) -> _CanonicalWorkspaceIdentity | None:
        return self._workspace_identity

    @property
    def marker_path(self) -> Path:
        return self._marker_path

    @property
    def dataset_identity(self) -> str | None:
        return self._dataset_identity


_RESERVATION_SEAL = _ReservationSeal()
CANONICAL_MARKER = Path("holdout.started")
_RESERVATION_LOCK = Lock()
_ISSUED_TOKENS: set[_ReservationToken] = set()


@dataclass(frozen=True, slots=True)
class _ConsumptionCapability:
    marker_path: Path
    _workspace_identity: _CanonicalWorkspaceIdentity | None
    _dataset_identity: str | None
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
    token = _ReservationToken(_RESERVATION_SEAL, None, marker, None)
    with _RESERVATION_LOCK:
        _ISSUED_TOKENS.add(token)
    return _ConsumptionCapability(marker, None, None, token)


def reserve_consumption_secure(
    marker: Path,
    identity: JsonObject,
    *,
    reserved_at: str,
    write_marker: Callable[[str, bytes], None],
    workspace_identity: _CanonicalWorkspaceIdentity,
    dataset_identity: str,
) -> _ConsumptionCapability:
    if marker != CANONICAL_MARKER:
        raise HoldoutAlreadyConsumedError("reservation marker is not canonical")
    payload = {**identity, "reserved_at": reserved_at}
    content = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    try:
        write_marker(marker.name, content)
    except FileExistsError as error:
        raise HoldoutAlreadyConsumedError("holdout already consumed") from error
    token = _ReservationToken(
        _RESERVATION_SEAL,
        workspace_identity,
        marker,
        dataset_identity,
    )
    with _RESERVATION_LOCK:
        _ISSUED_TOKENS.add(token)
    return _ConsumptionCapability(marker, workspace_identity, dataset_identity, token)


def invalidate_consumption_capabilities(
    workspace_identity: _CanonicalWorkspaceIdentity,
) -> None:
    with _RESERVATION_LOCK:
        invalidated = [
            token
            for token in _ISSUED_TOKENS
            if token.workspace_identity is workspace_identity
        ]
        for token in invalidated:
            _ISSUED_TOKENS.remove(token)
            token.consumed = True


def consume_consumption_capability(
    value: _ConsumptionCapability | None,
    *,
    expected_marker: Path | None = None,
    expected_workspace_identity: _CanonicalWorkspaceIdentity | None = None,
    expected_dataset_identity: str | None = None,
) -> None:
    with _RESERVATION_LOCK:
        if (
            not isinstance(value, _ConsumptionCapability)
            or value._token.seal is not _RESERVATION_SEAL
            or value._token not in _ISSUED_TOKENS
            or (
                expected_marker is not None
                and value._token.marker_path != expected_marker
            )
            or (
                expected_workspace_identity is not None
                and value._token.workspace_identity is not expected_workspace_identity
            )
            or (
                expected_dataset_identity is not None
                and value._token.dataset_identity != expected_dataset_identity
            )
        ):
            if isinstance(value, _ConsumptionCapability) and value._token.consumed:
                raise HoldoutAlreadyConsumedError(
                    "reservation capability already consumed"
                )
            raise HoldoutAlreadyConsumedError("reservation capability is invalid")
        _ISSUED_TOKENS.remove(value._token)
        value._token.consumed = True


def load_reserved_dataset[T](
    capability: _ConsumptionCapability,
    loader: Callable[[], T],
) -> T:
    consume_consumption_capability(capability)
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
    with _RESERVATION_LOCK:
        return (
            isinstance(value, _ConsumptionCapability)
            and value._token.seal is _RESERVATION_SEAL
            and value._token in _ISSUED_TOKENS
            and not value._token.consumed
        )
