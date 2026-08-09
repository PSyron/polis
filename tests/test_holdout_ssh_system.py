from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

from polis.evaluation.holdout_models import HoldoutAdmissionError
from polis.evaluation.holdout_ssh_authorization import (
    _authorization_verifier,
    _run_ssh_verification,
)
from polis.evaluation.holdout_ssh_executable import _verified_executable

_IDENTITY = "ephemeral"
_NAMESPACE = "polis-holdout-authorization-v1"


def _executable_path() -> Path:
    return Path("/usr/bin/ssh-keygen")


def _executable_sha256() -> str:
    return hashlib.sha256(_executable_path().read_bytes()).hexdigest()


def _signed_material(tmp_path: Path) -> tuple[str, bytes, bytes, Path]:
    executable = _executable_path()
    key = tmp_path / "ephemeral"
    subprocess.run(
        [str(executable), "-q", "-t", "ed25519", "-N", "", "-f", str(key)],
        executable=str(executable),
        check=True,
    )
    payload_path = tmp_path / "payload.json"
    payload_path.write_bytes(b'{"run_authorization":"approved"}\n')
    subprocess.run(
        [
            str(executable),
            "-Y",
            "sign",
            "-f",
            str(key),
            "-n",
            _NAMESPACE,
            str(payload_path),
        ],
        executable=str(executable),
        check=True,
        capture_output=True,
    )
    public_key = key.with_suffix(".pub").read_text(encoding="utf-8").strip()
    signature = (tmp_path / "payload.json.sig").read_bytes()
    return public_key, payload_path.read_bytes(), signature, key


def test_system_verifier_accepts_ephemeral_ed25519_signature(tmp_path: Path) -> None:
    public_key, payload, signature, key = _signed_material(tmp_path)
    allowed = tmp_path / "allowed"
    allowed.write_text(
        f'{_IDENTITY} namespaces="{_NAMESPACE}" {public_key}\n', encoding="utf-8"
    )
    signature_path = tmp_path / "signature"
    signature_path.write_bytes(signature)

    with _verified_executable(
        _executable_path(), _executable_sha256(), "Darwin"
    ) as executable:
        result = _run_ssh_verification(
            executable,
            (
                str(_executable_path()),
                "-Y",
                "verify",
                "-f",
                str(allowed),
                "-I",
                _IDENTITY,
                "-n",
                _NAMESPACE,
                "-s",
                str(signature_path),
            ),
            payload,
            10.0,
        )

    assert result.returncode == 0

    key.unlink()


@pytest.mark.parametrize("mutation", ["payload", "signature"])
def test_system_verifier_rejects_mutated_signed_material(
    mutation: str, tmp_path: Path
) -> None:
    public_key, payload, signature, key = _signed_material(tmp_path)
    if mutation == "payload":
        payload = b'{"run_authorization":"rejected"}\n'
    else:
        changed = bytearray(signature)
        changed[len(changed) // 2] ^= 1
        signature = bytes(changed)
    allowed = tmp_path / "allowed"
    allowed.write_text(
        f'{_IDENTITY} namespaces="{_NAMESPACE}" {public_key}\n', encoding="utf-8"
    )
    signature_path = tmp_path / "signature"
    signature_path.write_bytes(signature)
    with _verified_executable(
        _executable_path(), _executable_sha256(), "Darwin"
    ) as executable:
        result = _run_ssh_verification(
            executable,
            (
                str(_executable_path()),
                "-Y",
                "verify",
                "-f",
                str(allowed),
                "-I",
                _IDENTITY,
                "-n",
                _NAMESPACE,
                "-s",
                str(signature_path),
            ),
            payload,
            10.0,
        )

    assert result.returncode != 0

    key.unlink()


def test_malicious_path_cannot_replace_the_pinned_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attacker = tmp_path / "ssh-keygen"
    attacker.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    attacker.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path))
    verifier = _authorization_verifier(_executable_sha256())

    with pytest.raises(HoldoutAdmissionError):
        verifier.verify(b"{}\n", b"invalid-signature")

    assert os.environ["PATH"] == str(tmp_path)


def test_wrong_executable_digest_fails_before_signature_verification() -> None:
    verifier = _authorization_verifier("0" * 64)

    with pytest.raises(HoldoutAdmissionError, match="digest mismatch"):
        verifier.verify(b"{}\n", b"invalid-signature")


def test_symlinked_executable_path_is_rejected(tmp_path: Path) -> None:
    link = tmp_path / "ssh-keygen"
    link.symlink_to(_executable_path())

    with pytest.raises(HoldoutAdmissionError, match="trusted ssh-keygen"):
        with _verified_executable(link, _executable_sha256(), "Darwin"):
            raise AssertionError("symlink must never produce a capability")


def test_non_darwin_executable_platform_fails_before_open() -> None:
    with pytest.raises(HoldoutAdmissionError, match="unsupported"):
        with _verified_executable(_executable_path(), _executable_sha256(), "Linux"):
            raise AssertionError("unsupported platform must never produce a capability")


@pytest.mark.parametrize("flag", ["O_NOFOLLOW", "O_DIRECTORY"])
def test_executable_verification_fails_closed_without_required_descriptor_support(
    flag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delattr(os, flag)

    with pytest.raises(HoldoutAdmissionError, match="required"):
        with _verified_executable(_executable_path(), _executable_sha256(), "Darwin"):
            raise AssertionError("missing no-follow must never produce a capability")
