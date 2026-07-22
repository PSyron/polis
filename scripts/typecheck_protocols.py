"""Run the protocol conformance examples with the project strict settings."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "tests" / "typecheck" / "protocol_examples.py"


def main() -> int:
    """Return mypy's status for the protocol conformance examples."""

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--strict",
            "--follow-imports=normal",
            str(EXAMPLES),
        ],
        cwd=ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
