from __future__ import annotations

import os
import platform
import subprocess
import sys
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from experiments.sentence_release_gate.run_evaluation import (
    InstalledRunnerSession,
    _network_denial_prefix,
    audit_release_artifacts,
    install_artifact_offline,
    preflight_release_capabilities,
)

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "run_sentence_release_case.py"
FAKE_STDIO = ROOT / "tests" / "fixtures" / "fake_languagetool_stdio.py"
MACOS_ARM64_RELEASE_PROFILE = sys.platform == "darwin" and platform.machine() == "arm64"


def _build(tmp_path: Path) -> tuple[Path, Path]:
    dist = tmp_path / "dist"
    completed = subprocess.run(
        (sys.executable, "-m", "build", "--no-isolation", "--outdir", os.fspath(dist)),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return next(dist.glob("*.whl")), next(dist.glob("*.tar.gz"))


def _fake_stdio(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-languagetool"
    executable.write_text(
        f"#!{sys.executable}\n" + FAKE_STDIO.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


@pytest.mark.skipif(
    not MACOS_ARM64_RELEASE_PROFILE,
    reason="owned by the explicit macos-arm64-v1 sentence-release profile",
)
def test_clean_wheel_runs_public_sentence_paths_from_external_cwd(
    tmp_path: Path,
) -> None:
    wheel, sdist = _build(tmp_path)
    audit = audit_release_artifacts(wheel, sdist)
    assert audit.qualified is True

    environment = tmp_path / "installed"
    python = install_artifact_offline(wheel, environment)
    with InstalledRunnerSession(
        python=python,
        runner=RUNNER,
        vendored_stdio=_fake_stdio(tmp_path),
        working_directory=tmp_path / "outside-repository",
        timeout_seconds=2.0,
    ) as session:
        response, elapsed_ms = session.exchange(1, "Wiem że wróciła.")

    assert response["status"] == "complete"
    assert response["corrected_text"] == "Wiem, że wróciła."
    assert response["model_calls"] == 0
    assert elapsed_ms > 0


def test_artifact_audit_scans_large_members_for_private_paths(tmp_path: Path) -> None:
    wheel = tmp_path / "polis-0-py3-none-any.whl"
    sdist = tmp_path / "polis-0.tar.gz"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("polis/__init__.py", "")
        archive.writestr("polis-0.dist-info/METADATA", "")
    payload = b"x" * 2_100_000 + os.fspath(Path.home()).encode()
    with tarfile.open(sdist, "w:gz") as archive:
        info = tarfile.TarInfo("polis-0/README.md")
        info.size = len(payload)
        archive.addfile(info, BytesIO(payload))

    with pytest.raises(ValueError, match="private home path"):
        audit_release_artifacts(wheel, sdist)


def test_artifact_audit_rejects_unexpected_top_level_content(tmp_path: Path) -> None:
    wheel = tmp_path / "polis-0-py3-none-any.whl"
    sdist = tmp_path / "polis-0.tar.gz"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("unexpected.txt", "surprise")
    with tarfile.open(sdist, "w:gz") as archive:
        info = tarfile.TarInfo("polis-0/README.md")
        info.size = 0
        archive.addfile(info, BytesIO())

    with pytest.raises(ValueError, match="unexpected wheel member"):
        audit_release_artifacts(wheel, sdist)


@pytest.mark.skipif(
    not MACOS_ARM64_RELEASE_PROFILE,
    reason="owned by the explicit macos-arm64-v1 sentence-release profile",
)
def test_release_network_sandbox_denies_socket_creation() -> None:
    code = (
        "import socket,sys\n"
        "try:\n socket.socket().bind(('127.0.0.1', 0))\n"
        "except PermissionError:\n sys.exit(0)\n"
        "sys.exit(1)\n"
    )

    completed = subprocess.run(
        (*_network_denial_prefix(), sys.executable, "-c", code),
        check=False,
    )

    assert completed.returncode == 0


@pytest.mark.skipif(
    not MACOS_ARM64_RELEASE_PROFILE,
    reason="owned by the explicit macos-arm64-v1 sentence-release profile",
)
def test_release_platform_capabilities_pass_pre_reservation_probe() -> None:
    preflight_release_capabilities()
