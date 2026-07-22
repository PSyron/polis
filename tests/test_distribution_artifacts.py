from __future__ import annotations

import subprocess
import sys
import tarfile
import zipfile
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

    wheel = next(dist.glob("*.whl"))
    sdist = next(dist.glob("*.tar.gz"))
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
    with tarfile.open(sdist) as archive:
        sdist_names = archive.getnames()

    assert not any("tests/typecheck/" in name for name in wheel_names)
    assert not any("tests/typecheck/" in name for name in sdist_names)
    assert not any("third_party/languagetool-pl" in name for name in wheel_names)
    assert not any("third_party/languagetool-pl" in name for name in sdist_names)
    assert not any("polish_correction_corpus_v3" in name for name in wheel_names)
    assert not any("polish_correction_corpus_v3" in name for name in sdist_names)
    assert not any(
        name.endswith("/experiments/sentence_release_gate/report.json")
        for name in sdist_names
    )
    assert not any(
        name.endswith((".jar", ".gguf", ".safetensors"))
        for name in (*wheel_names, *sdist_names)
    )
    assert not any(
        "target/dependency" in name or "/.cache/" in name
        for name in (*wheel_names, *sdist_names)
    )
    assert any(name.endswith("/src/polis/__init__.py") for name in sdist_names)
    assert any(name.endswith("/tests/test_public_models.py") for name in sdist_names)
    assert any(
        name.endswith("/src/polis/evaluation/datasets/v1/cases.json")
        for name in sdist_names
    )
    assert any(
        name == "polis/evaluation/datasets/v1/cases.json" for name in wheel_names
    )
