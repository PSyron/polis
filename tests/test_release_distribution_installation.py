from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "scripts/prepare_build_wheelhouse.py"
VERIFY_INSTALL = ROOT / "scripts/verify_distribution_install.py"
EXPECTED_PACKAGES = {
    "hatchling": "1.31.0",
    "packaging": "26.2",
    "pathspec": "1.1.1",
    "pluggy": "1.6.0",
    "trove-classifiers": "2026.6.1.19",
}


def _run(
    command: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        timeout=120,
        env=env,
    )


def _prepare_release_inputs(base: Path) -> tuple[Path, Path, Path]:
    dist = base / "dist"
    wheelhouse = base / "wheelhouse"
    manifest = base / "wheelhouse-manifest.json"
    prepare = _run(
        [
            sys.executable,
            str(PREPARE),
            "--lock",
            str(ROOT / "uv.lock"),
            "--output",
            str(wheelhouse),
            "--manifest",
            str(manifest),
        ]
    )
    assert prepare.returncode == 0, prepare.stderr + prepare.stdout
    build = _run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(dist),
        ]
    )
    assert build.returncode == 0, build.stderr + build.stdout
    return dist, wheelhouse, manifest


def test_public_wheelhouse_preparer_records_exact_locked_universal_wheels(
    tmp_path: Path,
) -> None:
    _, wheelhouse, manifest = _prepare_release_inputs(tmp_path)

    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert len(payload["lock_sha256"]) == 64
    assert {item["name"]: item["version"] for item in payload["wheels"]} == (
        EXPECTED_PACKAGES
    )
    assert {path.name for path in wheelhouse.iterdir()} == {
        item["filename"] for item in payload["wheels"]
    }
    assert all(
        item["filename"].endswith("-py3-none-any.whl") for item in payload["wheels"]
    )
    assert all(
        item["size"] > 0 and len(item["sha256"]) == 64 for item in payload["wheels"]
    )


def test_public_install_verifier_installs_both_artifacts_with_socket_denied(
    tmp_path: Path,
) -> None:
    dist, wheelhouse, manifest = _prepare_release_inputs(tmp_path)

    result = _run(
        [
            sys.executable,
            str(VERIFY_INSTALL),
            "--dist",
            str(dist),
            "--wheelhouse",
            str(wheelhouse),
            "--wheelhouse-manifest",
            str(manifest),
        ],
        env=os.environ | {"PYTHONIOENCODING": "cp1252"},
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "socket.connect=blocked" in result.stdout
    assert "socket.connect_ex=blocked" in result.stdout
    assert "socket.create_connection=blocked" in result.stdout
    assert "artifact=wheel version=0.2.0.dev0 issues=1" in result.stdout
    assert "artifact=sdist version=0.2.0.dev0 issues=1" in result.stdout
    assert '"text":"Witaj,świecie."' in result.stdout
    assert "http://" not in result.stdout.lower()
    assert "https://" not in result.stdout.lower()


@pytest.mark.parametrize("mutation", ["missing", "tampered", "extra"])
def test_public_install_verifier_rejects_invalid_wheelhouse(
    tmp_path: Path, mutation: str
) -> None:
    dist, wheelhouse, manifest = _prepare_release_inputs(tmp_path)
    first = next(wheelhouse.iterdir())
    if mutation == "missing":
        first.unlink()
    elif mutation == "tampered":
        first.write_bytes(first.read_bytes() + b"tampered")
    else:
        shutil.copyfile(first, wheelhouse / "unexpected.whl")

    result = _run(
        [
            sys.executable,
            str(VERIFY_INSTALL),
            "--dist",
            str(dist),
            "--wheelhouse",
            str(wheelhouse),
            "--wheelhouse-manifest",
            str(manifest),
        ]
    )

    assert result.returncode != 0
    assert "wheelhouse" in result.stderr.lower()


@pytest.mark.parametrize("mutation", ["directory", "symlink"])
def test_public_install_verifier_rejects_nonregular_wheelhouse_members(
    tmp_path: Path, mutation: str
) -> None:
    dist, wheelhouse, manifest = _prepare_release_inputs(tmp_path)
    if mutation == "directory":
        (wheelhouse / "unexpected").mkdir()
    else:
        wheel = next(wheelhouse.iterdir())
        outside = tmp_path / "outside.whl"
        shutil.copyfile(wheel, outside)
        wheel.unlink()
        wheel.symlink_to(outside)

    result = _run(
        [
            sys.executable,
            str(VERIFY_INSTALL),
            "--dist",
            str(dist),
            "--wheelhouse",
            str(wheelhouse),
            "--wheelhouse-manifest",
            str(manifest),
        ]
    )

    assert result.returncode != 0
    assert "wheelhouse" in result.stderr.lower()


def test_public_install_verifier_requires_wheelhouse_inputs(tmp_path: Path) -> None:
    result = _run([sys.executable, str(VERIFY_INSTALL), "--dist", str(tmp_path)])

    assert result.returncode != 0
    assert "--wheelhouse" in result.stderr
    assert "--wheelhouse-manifest" in result.stderr


def test_public_install_verifier_rejects_malformed_cli_json(tmp_path: Path) -> None:
    dist, wheelhouse, manifest = _prepare_release_inputs(tmp_path)
    wheel = next(dist.glob("*.whl"))
    replacement = dist / "changed.whl"
    with (
        zipfile.ZipFile(wheel) as original,
        zipfile.ZipFile(replacement, "w") as changed,
    ):
        for name in original.namelist():
            content = (
                b"def main():\n    print('not-json')\n"
                if name == "polis/cli/__init__.py"
                else original.read(name)
            )
            changed.writestr(name, content)
    wheel.unlink()
    replacement.rename(wheel)

    result = _run(
        [
            sys.executable,
            str(VERIFY_INSTALL),
            "--dist",
            str(dist),
            "--wheelhouse",
            str(wheelhouse),
            "--wheelhouse-manifest",
            str(manifest),
        ]
    )

    assert result.returncode != 0
    assert "malformed JSON" in result.stderr


def test_public_install_verifier_rejects_malformed_wheelhouse_manifest(
    tmp_path: Path,
) -> None:
    dist, wheelhouse, manifest = _prepare_release_inputs(tmp_path)
    manifest.write_text("{not-json", encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(VERIFY_INSTALL),
            "--dist",
            str(dist),
            "--wheelhouse",
            str(wheelhouse),
            "--wheelhouse-manifest",
            str(manifest),
        ]
    )

    assert result.returncode != 0
    assert "manifest is malformed" in result.stderr


def test_public_wheelhouse_preparer_rejects_lock_version_drift(
    tmp_path: Path,
) -> None:
    lock = tmp_path / "uv.lock"
    lock.write_text(
        (ROOT / "uv.lock")
        .read_text(encoding="utf-8")
        .replace(
            'name = "hatchling"\nversion = "1.31.0"',
            'name = "hatchling"\nversion = "1.30.0"',
        ),
        encoding="utf-8",
    )

    result = _run(
        [
            sys.executable,
            str(PREPARE),
            "--lock",
            str(lock),
            "--output",
            str(tmp_path / "wheelhouse"),
            "--manifest",
            str(tmp_path / "manifest.json"),
        ]
    )

    assert result.returncode != 0
    assert "uv.lock version mismatch" in result.stderr


def test_public_install_verifier_rejects_joint_wheel_and_manifest_tampering(
    tmp_path: Path,
) -> None:
    dist, wheelhouse, manifest = _prepare_release_inputs(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    entry = payload["wheels"][0]
    wheel = wheelhouse / entry["filename"]
    wheel.write_bytes(wheel.read_bytes() + b"tampered")
    entry["size"] = wheel.stat().st_size
    entry["sha256"] = hashlib.sha256(wheel.read_bytes()).hexdigest()
    payload["lock_sha256"] = "0" * 64
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    result = _run(
        [
            sys.executable,
            str(VERIFY_INSTALL),
            "--dist",
            str(dist),
            "--wheelhouse",
            str(wheelhouse),
            "--wheelhouse-manifest",
            str(manifest),
        ]
    )

    assert result.returncode != 0
    assert "manifest does not match uv.lock" in result.stderr
