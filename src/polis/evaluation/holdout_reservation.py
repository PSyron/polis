from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Final, Protocol

from polis.evaluation.holdout_models import JsonObject


class HoldoutAlreadyConsumedError(RuntimeError):
    pass


class DurabilityFilesystem(Protocol):
    def open_exclusive(self, directory: int, name: str, content: bytes) -> int: ...
    def open_directory(self, path: Path) -> int: ...
    def fsync(self, descriptor: int) -> None: ...
    def close(self, descriptor: int) -> None: ...


class _ReservationSeal:
    pass


class _CanonicalWorkspaceIdentity:
    pass


@dataclass(frozen=True, slots=True)
class _ReservationClaims:
    seal: _ReservationSeal
    workspace_identity: _CanonicalWorkspaceIdentity | None
    marker_path: Path
    dataset_identity: str | None


class _ReservationToken:
    __slots__ = ()

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("reservation token is immutable")


_RESERVATION_SEAL = _ReservationSeal()
CANONICAL_MARKER = Path("holdout.started")
_RESERVATION_LOCK = Lock()
_ISSUED_CLAIMS: Final[dict[_ConsumptionCapability, _ReservationClaims]] = {}
_CONSUMED_CAPABILITIES: Final[set[_ConsumptionCapability]] = set()


class _ConsumptionCapability:
    __slots__ = ("_token",)

    def __init__(self, token: _ReservationToken) -> None:
        object.__setattr__(self, "_token", token)

    def __setattr__(self, _name: str, _value: object) -> None:
        raise AttributeError("reservation capability is immutable")

    @property
    def marker_path(self) -> Path:
        with _RESERVATION_LOCK:
            claims = _ISSUED_CLAIMS.get(self)
            if claims is None:
                raise HoldoutAlreadyConsumedError(
                    "reservation capability is no longer active"
                )
            return claims.marker_path

    @property
    def consumed(self) -> bool:
        with _RESERVATION_LOCK:
            return self in _CONSUMED_CAPABILITIES


class _OperatingSystemFilesystem:
    def open_exclusive(self, directory: int, name: str, content: bytes) -> int:
        if not hasattr(os, "O_NOFOLLOW"):
            raise OSError("O_NOFOLLOW support is unavailable")
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory,
        )
        try:
            offset = 0
            while offset < len(content):
                offset += os.write(descriptor, content[offset:])
        except OSError:
            os.close(descriptor)
            raise
        return descriptor

    def open_directory(self, path: Path) -> int:
        if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
            raise OSError("secure directory flags are unavailable")
        flags = (
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
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
    if ".." in marker.parts:
        raise HoldoutAlreadyConsumedError("reservation marker path is not canonical")
    if marker.parent.is_symlink():
        raise HoldoutAlreadyConsumedError("reservation marker path is not canonical")
    if not marker.parent.is_dir():
        raise HoldoutAlreadyConsumedError(
            "reservation marker parent directory is unavailable"
        )
    payload = {**identity, "reserved_at": reserved_at}
    content = (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    try:
        directory_descriptor = fs.open_directory(marker.parent)
    except OSError as error:
        raise HoldoutAlreadyConsumedError(
            "reservation marker parent directory is unavailable"
        ) from error
    try:
        try:
            marker_descriptor = fs.open_exclusive(
                directory_descriptor, marker.name, content
            )
        except FileExistsError as error:
            raise HoldoutAlreadyConsumedError("holdout already consumed") from error
        except OSError as error:
            raise HoldoutAlreadyConsumedError(
                "reservation marker is unavailable"
            ) from error
        try:
            fs.fsync(marker_descriptor)
        finally:
            fs.close(marker_descriptor)
        fs.fsync(directory_descriptor)
    finally:
        fs.close(directory_descriptor)
    return _issue_capability(_ReservationClaims(_RESERVATION_SEAL, None, marker, None))


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
    return _issue_capability(
        _ReservationClaims(
            _RESERVATION_SEAL,
            workspace_identity,
            marker,
            dataset_identity,
        )
    )


def _issue_capability(claims: _ReservationClaims) -> _ConsumptionCapability:
    token = _ReservationToken()
    capability = _ConsumptionCapability(token)
    with _RESERVATION_LOCK:
        _ISSUED_CLAIMS[capability] = claims
    return capability


def invalidate_consumption_capabilities(
    workspace_identity: _CanonicalWorkspaceIdentity,
) -> None:
    with _RESERVATION_LOCK:
        invalidated = [
            capability
            for capability, claims in _ISSUED_CLAIMS.items()
            if claims.workspace_identity is workspace_identity
        ]
        for capability in invalidated:
            del _ISSUED_CLAIMS[capability]
            _CONSUMED_CAPABILITIES.add(capability)


def consume_consumption_capability(
    value: _ConsumptionCapability | None,
    *,
    expected_marker: Path | None = None,
    expected_workspace_identity: _CanonicalWorkspaceIdentity | None = None,
    expected_dataset_identity: str | None = None,
) -> None:
    with _RESERVATION_LOCK:
        if not isinstance(value, _ConsumptionCapability):
            raise HoldoutAlreadyConsumedError("reservation capability is invalid")
        claims = _ISSUED_CLAIMS.get(value)
        if claims is None:
            if value in _CONSUMED_CAPABILITIES:
                raise HoldoutAlreadyConsumedError(
                    "reservation capability already consumed"
                )
            raise HoldoutAlreadyConsumedError("reservation capability is invalid")
        if (
            (expected_marker is not None and claims.marker_path != expected_marker)
            or (
                expected_workspace_identity is not None
                and claims.workspace_identity is not expected_workspace_identity
            )
            or (
                expected_dataset_identity is not None
                and claims.dataset_identity != expected_dataset_identity
            )
        ):
            raise HoldoutAlreadyConsumedError("reservation capability is invalid")
        del _ISSUED_CLAIMS[value]
        _CONSUMED_CAPABILITIES.add(value)


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
        return isinstance(value, _ConsumptionCapability) and value in _ISSUED_CLAIMS
