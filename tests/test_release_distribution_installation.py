from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _venv_python(venv_dir: Path) -> Path:
    bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    candidates = [bin_dir / "python", bin_dir / "python3", bin_dir / "python.exe"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError(f"failed to locate venv python in {venv_dir}")


def _build_artifacts(dist: Path) -> tuple[Path, Path]:
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(dist),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr

    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    assert len(wheels) == 1
    assert len(sdists) == 1
    return wheels[0], sdists[0]


def _run(
    command: list[str], *, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )


def _smoke_install(venv_dir: Path, artifact: Path) -> None:
    python = _venv_python(venv_dir)

    install = _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-input",
            "--disable-pip-version-check",
            str(artifact),
        ]
    )
    assert install.returncode == 0, install.stderr + install.stdout

    version_check = _run(
        [
            str(python),
            "-c",
            "from importlib.metadata import version; print(version('polis-nlp'))",
        ]
    )
    assert version_check.returncode == 0, version_check.stderr + version_check.stdout
    assert version_check.stdout.strip()

    api_check = _run(
        [
            str(python),
            "-c",
            (
                "from polis import Analyzer, AnalyzerConfig; "
                "result = Analyzer(AnalyzerConfig(use_local_heuristic_backend=False))"
                ".analyze("
                "'Zeby nauczyc sie polskiego.'); "
                "print(len(result.issues), result.text)"
            ),
        ]
    )
    assert api_check.returncode == 0, api_check.stderr + api_check.stdout

    legacy_stdio_env = os.environ.copy()
    legacy_stdio_env["PYTHONIOENCODING"] = "cp1252"
    cli_run = subprocess.run(
        [
            str(python),
            "-m",
            "polis.cli",
            "analyze",
            "--json",
            "Witaj,świecie.",
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        env=legacy_stdio_env,
    )
    assert cli_run.returncode == 0, cli_run.stderr + cli_run.stdout
    payload = json.loads(cli_run.stdout)
    assert "issues" in payload
    assert payload["text"] == "Witaj,świecie."


def test_release_distribution_installation_path() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        dist = Path(workdir) / "dist"
        wheelsdist, sdist = _build_artifacts(dist)

        for artifact in (wheelsdist, sdist):
            with tempfile.TemporaryDirectory() as venv_tmp:
                venv_dir = Path(venv_tmp)
                create_venv = _run([sys.executable, "-m", "venv", str(venv_dir)])
                assert create_venv.returncode == 0, create_venv.stderr
                _smoke_install(venv_dir, artifact)
