from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

import scripts.verify_distribution_artifacts as artifact_verifier

ROOT = Path(__file__).resolve().parents[1]
PIN = "morfeusz2==1.99.15"
RUNTIME_MODULES = (
    "src/polis/rules/_morfeusz.py",
    "src/polis/rules/subject_verb.py",
)


def _build_distributions(tmp_path: Path) -> tuple[Path, Path]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(tmp_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr + result.stdout
    return next(tmp_path.glob("*.whl")), next(tmp_path.glob("*.tar.gz"))


def test_optional_extra_keeps_default_runtime_dependency_free() -> None:
    # Given
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)["project"]

    # When
    dependencies = project["dependencies"]
    extras = project["optional-dependencies"]

    # Then
    assert dependencies == []
    assert extras["morphology"] == [PIN]
    assert PIN in extras["dev"]


def test_distributions_declare_extra_and_include_morphology_consumers(
    tmp_path: Path,
) -> None:
    # Given
    wheel, sdist = _build_distributions(tmp_path)

    # When
    with zipfile.ZipFile(wheel) as wheel_archive:
        wheel_names = wheel_archive.namelist()
        metadata_name = next(
            name for name in wheel_names if name.endswith(".dist-info/METADATA")
        )
        wheel_metadata = wheel_archive.read(metadata_name).decode("utf-8")
    with tarfile.open(sdist) as sdist_archive:
        sdist_names = sdist_archive.getnames()
        pkg_info_name = next(name for name in sdist_names if name.endswith("/PKG-INFO"))
        pkg_info_file = sdist_archive.extractfile(pkg_info_name)
        assert pkg_info_file is not None
        sdist_metadata = pkg_info_file.read().decode("utf-8")

    # Then
    requirement = f"Requires-Dist: {PIN}; extra == 'morphology'"
    assert requirement in wheel_metadata
    assert requirement in sdist_metadata
    for runtime_module in RUNTIME_MODULES:
        assert runtime_module.removeprefix("src/") in wheel_names
        assert any(name.endswith(f"/{runtime_module}") for name in sdist_names)
        assert runtime_module in artifact_verifier.EXPECTED_SOURCE_MEMBERS


def test_clean_wheel_without_extra_abstains_offline(
    tmp_path: Path,
) -> None:
    # Given
    wheel, _ = _build_distributions(tmp_path / "dist")
    environment = tmp_path / "environment"
    uv = shutil.which("uv")
    assert uv is not None
    create = subprocess.run(
        [uv, "venv", "--python", sys.executable, str(environment)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert create.returncode == 0, create.stderr + create.stdout
    interpreter = environment / "bin" / "python"
    install = subprocess.run(
        [uv, "pip", "install", "--python", str(interpreter), "--no-deps", str(wheel)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert install.returncode == 0, install.stderr + install.stdout
    empty_cwd = tmp_path / "empty"
    empty_cwd.mkdir()
    script = "\n".join(
        (
            "import socket",
            "def reject_network(*arguments, **keywords):",
            "    raise AssertionError('network access attempted')",
            "socket.socket.connect = reject_network",
            "socket.socket.connect_ex = reject_network",
            "socket.create_connection = reject_network",
            "from polis.cli import run",
            "raise SystemExit(run(['analyze', '--json', 'Oni czyta książkę.']))",
        )
    )
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)

    # When
    completed = subprocess.run(
        [str(interpreter), "-I", "-c", script],
        cwd=empty_cwd,
        env=clean_env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    # Then
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert json.loads(completed.stdout)["issues"] == []
