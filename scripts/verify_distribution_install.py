"""Verify distribution artifacts by clean installation in an isolated environment."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def _venv_python(venv_dir: Path) -> Path:
    bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    for candidate in (bin_dir / "python", bin_dir / "python3", bin_dir / "python.exe"):
        if candidate.exists():
            return candidate
    raise SystemExit(f"could not locate python executable in virtualenv at {venv_dir}")


def _run(
    command: list[str],
    cwd: Path | None = None,
    *,
    env: dict[str, str] | None = None,
) -> None:
    subprocess.run(
        command,
        cwd=cwd,
        text=True,
        check=True,
        env=env,
        capture_output=True,
    )


def _smoke_commands(venv_python: Path) -> list[list[str]]:
    return [
        [
            str(venv_python),
            "-c",
            "from importlib.metadata import version; print(version('polis-nlp'));",
        ],
        [
            str(venv_python),
            "-c",
            "from polis import Analyzer, AnalyzerConfig; "
            "analyzer = Analyzer(AnalyzerConfig(use_local_heuristic_backend=False)); "
            "result = analyzer.analyze('Zeby nauczyc sie polskiego.'); "
            "print(len(result.issues), result.text)",
        ],
        [
            str(venv_python),
            "-m",
            "polis.cli",
            "analyze",
            "--json",
            "Jutro,powiem o tym jutro.",
        ],
    ]


def _validate_cli_json(python: Path) -> None:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "cp1252"
    result = subprocess.run(
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
        check=True,
        env=env,
    )
    payload = json.loads(result.stdout)
    if "issues" not in payload or "text" not in payload:
        raise SystemExit("CLI JSON output missing required keys: issues/text")
    if payload["text"] != "Witaj,świecie.":
        raise SystemExit("CLI UTF-8 text changed under inherited CP1252 stdio")


def _install_and_smoke(artifact: Path, venv_dir: Path) -> None:
    python = _venv_python(venv_dir)
    _run(
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
    for command in _smoke_commands(python):
        subprocess.run(command, text=True, capture_output=True, check=True)
    _validate_cli_json(python)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify wheel/sdist clean-install smoke path."
    )
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--python", type=Path, action="append", default=None)
    args = parser.parse_args()

    dist = args.dist
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit("dist must contain exactly one wheel and one source archive")

    py_interpreters = args.python or [Path(sys.executable)]
    for interpreter in py_interpreters:
        if not interpreter.exists():
            raise SystemExit(f"python interpreter not found: {interpreter}")

    targets = [("wheel", wheels[0]), ("sdist", sdists[0])]
    for label, artifact in targets:
        for interpreter in py_interpreters:
            with tempfile.TemporaryDirectory(
                prefix=f"polis-install-{label}-"
            ) as workdir:
                venv_dir = Path(workdir)
                _run([str(interpreter), "-m", "venv", str(venv_dir)])
                _install_and_smoke(artifact, venv_dir)

    print("distribution installation checks passed")


if __name__ == "__main__":
    main()
