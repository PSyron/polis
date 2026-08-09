from __future__ import annotations

import hashlib
import importlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import pytest

from polis.evaluation.holdout_models import HoldoutAdmissionError
from polis.evaluation.holdout_ssh_executable import _VerifiedExecutable


class _Verifier(Protocol):
    def verify(self, payload: bytes, signature: bytes) -> bool: ...


@runtime_checkable
class _Api(Protocol):
    def _authorization_verifier(self, executable_sha256: str) -> _Verifier: ...


def _api() -> _Api:
    module = importlib.import_module("polis.evaluation.holdout_ssh_authorization")
    if not isinstance(module, _Api):
        raise AssertionError("private SSH authorization API is incomplete")
    return module


def _executable_sha256() -> str:
    return hashlib.sha256(Path("/usr/bin/ssh-keygen").read_bytes()).hexdigest()


@dataclass(frozen=True, slots=True)
class _Result:
    returncode: int
    stderr: bytes


def test_private_adapter_observes_only_frozen_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[tuple[str, ...], bytes, float, bytes, bytes]] = []

    def accept(
        executable: _VerifiedExecutable,
        arguments: tuple[str, ...],
        payload: bytes,
        timeout_seconds: float,
    ) -> _Result:
        calls.append(
            (
                arguments,
                payload,
                timeout_seconds,
                Path(arguments[4]).read_bytes(),
                Path(arguments[10]).read_bytes(),
            )
        )
        return _Result(0, b"Good signature")

    monkeypatch.setattr(
        "polis.evaluation.holdout_ssh_authorization._run_ssh_verification", accept
    )
    verifier = _api()._authorization_verifier(_executable_sha256())
    payload = b'{"run_authorization":"approved"}\n'

    assert verifier.verify(payload, b"synthetic-signature") is True

    arguments, observed, timeout, allowed, signature = calls[0]
    assert arguments[0] == "/usr/bin/ssh-keygen"
    assert arguments[5:] == (
        "-I",
        "PSyron",
        "-n",
        "polis-holdout-authorization-v1",
        "-s",
        arguments[10],
    )
    assert observed == payload
    assert timeout > 0
    assert allowed.startswith(
        b'PSyron namespaces="polis-holdout-authorization-v1" ssh-ed25519'
    )
    assert signature == b"synthetic-signature"


@pytest.mark.parametrize(
    ("returncode", "stderr", "message"),
    [(1, b"bad signature", "verification failed"), (1, b"", "diagnostics")],
)
def test_private_adapter_failure_is_fail_closed(
    returncode: int,
    stderr: bytes,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject(
        executable: _VerifiedExecutable,
        arguments: tuple[str, ...],
        payload: bytes,
        timeout_seconds: float,
    ) -> _Result:
        return _Result(returncode, stderr)

    monkeypatch.setattr(
        "polis.evaluation.holdout_ssh_authorization._run_ssh_verification", reject
    )

    with pytest.raises(HoldoutAdmissionError, match=message):
        _api()._authorization_verifier(_executable_sha256()).verify(b"{}\n", b"sig")


def test_private_adapter_timeout_is_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def timeout(
        executable: _VerifiedExecutable,
        arguments: tuple[str, ...],
        payload: bytes,
        timeout_seconds: float,
    ) -> _Result:
        raise subprocess.TimeoutExpired(arguments, timeout_seconds)

    monkeypatch.setattr(
        "polis.evaluation.holdout_ssh_authorization._run_ssh_verification", timeout
    )

    with pytest.raises(HoldoutAdmissionError, match="timed out"):
        _api()._authorization_verifier(_executable_sha256()).verify(b"{}\n", b"sig")
