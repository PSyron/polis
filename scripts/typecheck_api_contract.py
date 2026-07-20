"""Run the typing-only public API contract check portably."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STUBS = ROOT / "tests/typecheck/stubs"
EXAMPLES = ROOT / "tests/typecheck/api_contract_examples.py"


def main() -> int:
    """Type-check the contract examples against only the dedicated stub tree."""

    environment = os.environ.copy()
    environment["MYPYPATH"] = str(STUBS)
    completed = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(EXAMPLES)],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
