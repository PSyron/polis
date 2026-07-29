from __future__ import annotations

import subprocess
import sys
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
import scripts.verify_distribution_artifacts as artifact_verifier

ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts/verify_distribution_artifacts.py"
EXCLUDED_ARTIFACT_PREFIXES = artifact_verifier.EXCLUDED_ARTIFACT_PREFIXES
PROHIBITED_VENDOR_MARKERS = (
    ".jar",
    ".onnx",
    ".pt",
    ".pth",
    ".bin",
    ".safetensors",
    ".m2/",
    "target/",
    "repository/",
)
REPOSITORY_ONLY_SDIST_MEMBERS = artifact_verifier.REPOSITORY_ONLY_SDIST_MEMBERS
REQUIRED_SDIST_MEMBERS = artifact_verifier.REQUIRED_SDIST_MEMBERS


def _without_sdist_root(name: str) -> str:
    parts = name.split("/", 1)
    return parts[1] if len(parts) == 2 else name


def _assert_no_prohibited_vendor_members(names: list[str], *, sdist: bool) -> None:
    for raw_name in names:
        name = _without_sdist_root(raw_name) if sdist else raw_name
        assert not any(marker in name for marker in PROHIBITED_VENDOR_MARKERS), name


def _write_sdist(path: Path, members: tuple[str, ...]) -> None:
    metadata = (
        b"Metadata-Version: 2.4\n"
        b"Name: polis-nlp\n"
        b"Version: 0.2.0.dev0\n"
        b"License-Expression: MIT\n"
        b"License-File: LICENSE\n"
    )
    with tarfile.open(path, "w:gz") as archive:
        for name, content in (
            ("polis_nlp-0.2.0.dev0/PKG-INFO", metadata),
            ("polis_nlp-0.2.0.dev0/LICENSE", b"MIT\n"),
            *(
                (f"polis_nlp-0.2.0.dev0/{member}", b"repository-only\n")
                for member in members
            ),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(content)
            archive.addfile(info, BytesIO(content))


@pytest.mark.parametrize(
    "name",
    ["target/classes/example.txt", ".m2/repository/example.pom", "repository/a/b"],
)
def test_prohibited_vendor_markers_reject_root_level_directories(name: str) -> None:
    with pytest.raises(AssertionError, match=name):
        _assert_no_prohibited_vendor_members([name], sdist=False)


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
    assert "polis/__init__.py" in wheel_names
    assert any(name.endswith("/src/polis/__init__.py") for name in sdist_names)
    assert any(name.endswith("/README.md") for name in sdist_names)
    assert any(
        name == "polis/evaluation/datasets/v1/cases.json" for name in wheel_names
    )


def test_built_distributions_exclude_repository_only_material(
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

    wheel = next(dist.glob("*.whl"))
    sdist = next(dist.glob("*.tar.gz"))
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
    with tarfile.open(sdist) as archive:
        sdist_names = archive.getnames()

    for name in wheel_names:
        assert not name.startswith(EXCLUDED_ARTIFACT_PREFIXES)
    for name in sdist_names:
        normalized = _without_sdist_root(name)
        assert not normalized.startswith(EXCLUDED_ARTIFACT_PREFIXES)

    _assert_no_prohibited_vendor_members(wheel_names, sdist=False)
    _assert_no_prohibited_vendor_members(sdist_names, sdist=True)


def test_sdist_release_surface_is_explicit_and_product_only(
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

    sdist = next(dist.glob("*.tar.gz"))
    with tarfile.open(sdist) as archive:
        normalized = {_without_sdist_root(name) for name in archive.getnames()}

    for member in REQUIRED_SDIST_MEMBERS:
        assert member in normalized
    for member in REPOSITORY_ONLY_SDIST_MEMBERS:
        assert member not in normalized


@pytest.mark.parametrize("member", REPOSITORY_ONLY_SDIST_MEMBERS)
def test_distribution_verifier_rejects_repository_only_sdist_members(
    tmp_path: Path,
    member: str,
) -> None:
    sdist = tmp_path / "polis_nlp-0.2.0.dev0.tar.gz"
    _write_sdist(sdist, (member,))

    with pytest.raises(SystemExit, match="repository-only"):
        artifact_verifier.verify_sdist(sdist)
