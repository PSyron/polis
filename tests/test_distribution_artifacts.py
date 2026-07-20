from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts/verify_distribution_artifacts.py"


def test_built_distributions_declare_mit_metadata_and_contain_license(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    build = subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr

    verification = subprocess.run(
        [sys.executable, str(VERIFIER), "--dist", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert verification.returncode == 0, verification.stderr
    assert (
        "distribution artifacts declare MIT metadata and contain LICENSE"
        in verification.stdout
    )
