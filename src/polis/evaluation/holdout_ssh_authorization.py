from __future__ import annotations

import base64
import binascii
import hashlib
import os
import platform
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from polis.evaluation.holdout_models import HoldoutAdmissionError
from polis.evaluation.holdout_preregistration import (
    AUTHORIZATION_FINGERPRINT,
    AUTHORIZATION_HOST_MACHINE,
    AUTHORIZATION_HOST_SYSTEM,
    AUTHORIZATION_IDENTITY,
    AUTHORIZATION_NAMESPACE,
    AUTHORIZATION_PUBLIC_KEY,
    SSH_KEYGEN_PATH,
)
from polis.evaluation.holdout_ssh_executable import (
    _assert_stable,
    _verified_executable,
    _VerifiedExecutable,
)

_TIMEOUT_SECONDS = 10.0
_PRINCIPAL = re.compile(r"[A-Za-z0-9._-]+")


@dataclass(frozen=True, slots=True)
class _SshCommandResult:
    returncode: int
    stderr: bytes


def _platform_adapter() -> tuple[str, str]:
    return platform.system(), platform.machine()


def _run_ssh_verification(
    executable: _VerifiedExecutable,
    arguments: tuple[str, ...],
    payload: bytes,
    timeout_seconds: float,
) -> _SshCommandResult:
    _assert_stable(executable)
    completed = subprocess.run(
        arguments,
        executable=str(executable.path),
        input=payload,
        capture_output=True,
        check=False,
        timeout=timeout_seconds,
        env={"LANG": "C", "LC_ALL": "C"},
        close_fds=True,
        cwd=Path(arguments[4]).parent,
    )
    return _SshCommandResult(completed.returncode, completed.stderr)


def _ssh_public_key_fingerprint(public_key: str) -> str:
    parts = public_key.split(" ")
    if len(parts) != 3 or parts[0] != "ssh-ed25519" or not parts[2]:
        raise HoldoutAdmissionError("trusted SSH public key is invalid")
    try:
        blob = base64.b64decode(parts[1], validate=True)
    except (binascii.Error, ValueError) as error:
        raise HoldoutAdmissionError("trusted SSH public key is invalid") from error
    encoded = base64.b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
    return f"SHA256:{encoded}"


@dataclass(frozen=True, slots=True)
class _SshAuthorizationVerifier:
    executable_sha256: str

    def verify(self, payload: bytes, signature: bytes) -> bool:
        _validate_frozen_authority()
        if _platform_adapter() != (
            AUTHORIZATION_HOST_SYSTEM,
            AUTHORIZATION_HOST_MACHINE,
        ):
            raise HoldoutAdmissionError("SSH authorization host class is unsupported")
        allowed = (
            f'{AUTHORIZATION_IDENTITY} namespaces="{AUTHORIZATION_NAMESPACE}" '
            f"{AUTHORIZATION_PUBLIC_KEY}\n"
        ).encode()
        try:
            with (
                _verified_executable(
                    Path(SSH_KEYGEN_PATH),
                    self.executable_sha256,
                    AUTHORIZATION_HOST_SYSTEM,
                ) as executable,
                tempfile.TemporaryDirectory(prefix="polis-holdout-auth-") as directory,
            ):
                root = Path(directory)
                allowed_path = root / "allowed_signers"
                signature_path = root / "authorization.sig"
                _write_private(allowed_path, allowed)
                _write_private(signature_path, signature)
                result = _run_ssh_verification(
                    executable,
                    (
                        SSH_KEYGEN_PATH,
                        "-Y",
                        "verify",
                        "-f",
                        str(allowed_path),
                        "-I",
                        AUTHORIZATION_IDENTITY,
                        "-n",
                        AUTHORIZATION_NAMESPACE,
                        "-s",
                        str(signature_path),
                    ),
                    payload,
                    _TIMEOUT_SECONDS,
                )
                _assert_stable(executable)
        except subprocess.TimeoutExpired as error:
            raise HoldoutAdmissionError(
                "SSH authorization verifier timed out"
            ) from error
        except OSError as error:
            raise HoldoutAdmissionError(
                "SSH authorization verifier is unavailable"
            ) from error
        if result.returncode == 0:
            return True
        if not result.stderr.strip():
            raise HoldoutAdmissionError(
                "SSH authorization verifier failed without diagnostics"
            )
        raise HoldoutAdmissionError("SSH authorization signature verification failed")


def _validate_frozen_authority() -> None:
    if (
        _ssh_public_key_fingerprint(AUTHORIZATION_PUBLIC_KEY)
        != AUTHORIZATION_FINGERPRINT
    ):
        raise HoldoutAdmissionError("trusted SSH public key fingerprint mismatch")
    if (
        _PRINCIPAL.fullmatch(AUTHORIZATION_IDENTITY) is None
        or _PRINCIPAL.fullmatch(AUTHORIZATION_NAMESPACE) is None
    ):
        raise HoldoutAdmissionError("SSH authorization identity is invalid")


def _write_private(path: Path, content: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        offset = 0
        while offset < len(content):
            offset += os.write(descriptor, content[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _authorization_verifier(executable_sha256: str) -> _SshAuthorizationVerifier:
    return _SshAuthorizationVerifier(executable_sha256)
