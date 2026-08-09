from __future__ import annotations

import socket
from collections.abc import Iterable, Iterator
from contextlib import ExitStack, contextmanager
from threading import Lock
from typing import BinaryIO, Final, NoReturn
from unittest.mock import patch

from polis.evaluation.calibration_models import CalibrationIntegrityError

type SocketAddress = tuple[str, int] | tuple[str, int, int, int] | str | bytes

_SOCKET_BOUNDARY_LOCK: Final = Lock()


def _network_forbidden() -> NoReturn:
    raise CalibrationIntegrityError("calibration network access is forbidden")


def _blocked_connect(_socket: socket.socket, _address: SocketAddress) -> NoReturn:
    _network_forbidden()


def _blocked_connect_ex(_socket: socket.socket, _address: SocketAddress) -> NoReturn:
    _network_forbidden()


def _blocked_create_connection(
    _address: tuple[str, int],
    _timeout: float | None = None,
    _source_address: tuple[str, int] | None = None,
    *,
    all_errors: bool = False,
) -> NoReturn:
    _network_forbidden()


def _blocked_send(_socket: socket.socket, _data: bytes, _flags: int = 0) -> NoReturn:
    _network_forbidden()


def _blocked_sendall(_socket: socket.socket, _data: bytes, _flags: int = 0) -> NoReturn:
    _network_forbidden()


def _blocked_sendto(
    _socket: socket.socket,
    _data: bytes,
    _address_or_flags: SocketAddress | int,
    _address: SocketAddress | None = None,
) -> NoReturn:
    _network_forbidden()


def _blocked_sendmsg(
    _socket: socket.socket,
    _buffers: Iterable[bytes],
    _ancillary: Iterable[tuple[int, int, bytes]] = (),
    _flags: int = 0,
    _address: SocketAddress | None = None,
) -> NoReturn:
    _network_forbidden()


def _blocked_sendfile(
    _socket: socket.socket,
    _file: BinaryIO,
    _offset: int = 0,
    _count: int | None = None,
) -> NoReturn:
    _network_forbidden()


@contextmanager
def _offline_socket_boundary() -> Iterator[None]:
    with _SOCKET_BOUNDARY_LOCK:
        with ExitStack() as stack:
            stack.enter_context(
                patch.object(socket.socket, "connect", _blocked_connect)
            )
            stack.enter_context(
                patch.object(socket.socket, "connect_ex", _blocked_connect_ex)
            )
            stack.enter_context(
                patch.object(socket, "create_connection", _blocked_create_connection)
            )
            stack.enter_context(patch.object(socket.socket, "send", _blocked_send))
            stack.enter_context(
                patch.object(socket.socket, "sendall", _blocked_sendall)
            )
            stack.enter_context(patch.object(socket.socket, "sendto", _blocked_sendto))
            stack.enter_context(
                patch.object(socket.socket, "sendfile", _blocked_sendfile)
            )
            if hasattr(socket.socket, "sendmsg"):
                stack.enter_context(
                    patch.object(socket.socket, "sendmsg", _blocked_sendmsg)
                )
            yield
