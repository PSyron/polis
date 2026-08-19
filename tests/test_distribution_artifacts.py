from __future__ import annotations

import re
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
EXCLUDED_ARTIFACT_PREFIXES = (
    "experiments/",
    "data/finetuning/",
    "tests/",
    "third_party/",
    "docs/superpowers/",
    ".superpowers/",
)
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
REPOSITORY_ONLY_SDIST_MEMBERS = (
    "scripts/generate_safety_corpus_candidates.py",
    "scripts/run_sentence_safety_case.py",
    "docs/project/issue-62-implementation-plan.md",
    "docs/performance-baseline.md",
    "docs/quality-baseline.md",
)
REQUIRED_SDIST_MEMBERS = artifact_verifier.REQUIRED_SDIST_MEMBERS
ADR_0023_MEMBER = "docs/architecture/decisions/0023-evaluation-namespace-1-0.md"
EXPECTED_SOURCE_MEMBERS = tuple(
    path.relative_to(ROOT).as_posix()
    for path in sorted((ROOT / "src/polis").rglob("*"))
    if path.is_file()
    and "__pycache__" not in path.parts
    and path != ROOT / "src/polis/evaluation/__main__.py"
    and not path.name.startswith("holdout_")
    and not path.name.startswith("calibration_")
    and path != ROOT / "src/polis/evaluation/rule_family_qualification.py"
)


def _is_repository_only_calibration_member(name: str) -> bool:
    return (
        name == "polis/evaluation/__main__.py"
        or name.startswith("polis/evaluation/calibration_")
        or "/src/polis/evaluation/calibration_" in name
        or "polis-a-b-calibration-v2-v1" in name
        or "polis-a-b-qualification-v2-v1" in name
    )


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
    assert not any(
        name == "polis/evaluation/__main__.py"
        or name.startswith("polis/evaluation/holdout_")
        or name.startswith("experiments/a-b-one-shot/")
        for name in wheel_names
    )
    assert not any(_is_repository_only_calibration_member(name) for name in wheel_names)
    assert not any(
        name.endswith("/src/polis/evaluation/__main__.py")
        or "/src/polis/evaluation/holdout_" in name
        or "/experiments/a-b-one-shot/" in name
        for name in sdist_names
    )
    assert not any(_is_repository_only_calibration_member(name) for name in sdist_names)
    assert EXPECTED_SOURCE_MEMBERS == artifact_verifier.EXPECTED_SOURCE_MEMBERS
    assert len(EXPECTED_SOURCE_MEMBERS) == 75


def _mutate_wheel(
    source: Path, target: Path, *, add: str | None = None, remove: str | None = None
) -> None:
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "w") as changed:
        for name in original.namelist():
            if name != remove:
                changed.writestr(name, original.read(name))
        if add is not None:
            changed.writestr(add, b"unexpected\n")


def _rename_wheel_dist_info(source: Path, target: Path) -> None:
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "w") as changed:
        prefix = next(
            name.split("/", 1)[0]
            for name in original.namelist()
            if ".dist-info/" in name
        )
        for name in original.namelist():
            changed.writestr(
                name.replace(prefix, "evil-9.9.dist-info"), original.read(name)
            )


def _rewrite_wheel_identity(
    source: Path,
    target: Path,
    *,
    dist_info_prefix: str | None = None,
    metadata_changes: dict[str, str] | None = None,
) -> None:
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(target, "w") as changed:
        for name in original.namelist():
            rewritten_name = name
            if dist_info_prefix and ".dist-info/" in name:
                rewritten_name = name.replace(
                    name.split("/", 1)[0], dist_info_prefix, 1
                )
            content = original.read(name)
            if metadata_changes and rewritten_name.endswith(".dist-info/METADATA"):
                text = content.decode()
                for field, value in metadata_changes.items():
                    text = re.sub(
                        rf"^{field}: .*$", f"{field}: {value}", text, flags=re.MULTILINE
                    )
                content = text.encode()
            changed.writestr(rewritten_name, content)


def _rewrite_sdist_identity(
    source: Path,
    target: Path,
    *,
    root: str | None = None,
    metadata_changes: dict[str, str] | None = None,
) -> None:
    with tarfile.open(source) as original, tarfile.open(target, "w:gz") as changed:
        old_root = original.getnames()[0].split("/", 1)[0]
        new_root = root or old_root
        for member in original.getmembers():
            member.name = member.name.replace(old_root, new_root, 1)
            member_file = original.extractfile(member) if member.isfile() else None
            content = member_file.read() if member_file is not None else None
            if metadata_changes and member.name.endswith("/PKG-INFO"):
                assert content is not None
                text = content.decode()
                for field, value in metadata_changes.items():
                    text = re.sub(
                        rf"^{field}: .*$", f"{field}: {value}", text, flags=re.MULTILINE
                    )
                content = text.encode()
                member.size = len(content)
            changed.addfile(member, BytesIO(content) if content is not None else None)


def _mutate_sdist(
    source: Path, target: Path, *, add: str | None = None, remove: str | None = None
) -> None:
    with tarfile.open(source) as original, tarfile.open(target, "w:gz") as changed:
        for member in original.getmembers():
            if member.name.endswith(remove or "\0"):
                continue
            extracted = original.extractfile(member) if member.isfile() else None
            changed.addfile(member, extracted)
        if add is not None:
            root = original.getnames()[0].split("/", 1)[0]
            content = b"unexpected\n"
            info = tarfile.TarInfo(f"{root}/{add}")
            info.size = len(content)
            changed.addfile(info, BytesIO(content))


@pytest.mark.parametrize(
    ("kind", "member", "expected"),
    (
        ("wheel", "polis/model.onnx", "prohibited vendor path"),
        ("wheel", "polis/llm/adapter.py", "outside release surface"),
        ("wheel", "polis/unknown.py", "outside release surface"),
        ("sdist", "src/polis/model.onnx", "prohibited vendor path"),
        ("sdist", "src/polis/llm/adapter.py", "outside release surface"),
        ("sdist", "src/polis/unknown.py", "outside release surface"),
    ),
)
def test_public_verifier_rejects_unknown_package_members(
    tmp_path: Path, kind: str, member: str, expected: str
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
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
    if kind == "wheel":
        replacement = dist / "changed.whl"
        _mutate_wheel(wheel, replacement, add=member)
        wheel.unlink()
        replacement.rename(wheel)
    else:
        replacement = dist / "changed.tar.gz"
        _mutate_sdist(sdist, replacement, add=member)
        sdist.unlink()
        replacement.rename(sdist)

    result = subprocess.run(
        [sys.executable, str(VERIFIER), "--dist", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert expected in result.stderr


@pytest.mark.parametrize(
    ("kind", "member"),
    (
        ("wheel", "polis/analyzer.py"),
        ("sdist", "src/polis/analyzer.py"),
    ),
)
def test_public_verifier_rejects_missing_package_members(
    tmp_path: Path, kind: str, member: str
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
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
    if kind == "wheel":
        replacement = dist / "changed.whl"
        _mutate_wheel(wheel, replacement, remove=member)
        wheel.unlink()
        replacement.rename(wheel)
    else:
        replacement = dist / "changed.tar.gz"
        _mutate_sdist(sdist, replacement, remove=member)
        sdist.unlink()
        replacement.rename(sdist)

    result = subprocess.run(
        [sys.executable, str(VERIFIER), "--dist", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "missing package member" in result.stderr


def test_public_verifier_rejects_an_extra_distribution(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    build = subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr
    (dist / "unexpected.whl").write_bytes(b"extra")

    result = subprocess.run(
        [sys.executable, str(VERIFIER), "--dist", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "exactly one wheel" in result.stderr


def test_public_verifier_rejects_renamed_dist_info(tmp_path: Path) -> None:
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
    replacement = dist / "changed.whl"
    _rename_wheel_dist_info(wheel, replacement)
    wheel.unlink()
    replacement.rename(wheel)

    result = subprocess.run(
        [sys.executable, str(VERIFIER), "--dist", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "dist-info directory does not match wheel" in result.stderr


@pytest.mark.parametrize(
    "case",
    (
        "wheel-renamed",
        "wheel-metadata-name",
        "wheel-metadata-version",
        "sdist-root-renamed",
        "sdist-metadata-name",
        "sdist-metadata-version",
        "joint-wrong-identity",
    ),
)
def test_public_verifier_rejects_semantically_mismatched_identity(
    tmp_path: Path, case: str
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
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

    if case == "wheel-renamed":
        rewritten = dist / "evil-9.9-py3-none-any.whl"
        _rewrite_wheel_identity(wheel, rewritten, dist_info_prefix="evil-9.9.dist-info")
        wheel.unlink()
    elif case == "wheel-metadata-name":
        rewritten = dist / "changed.whl"
        _rewrite_wheel_identity(wheel, rewritten, metadata_changes={"Name": "evil"})
        wheel.unlink()
        rewritten.rename(wheel)
    elif case == "wheel-metadata-version":
        rewritten = dist / "changed.whl"
        _rewrite_wheel_identity(wheel, rewritten, metadata_changes={"Version": "9.9"})
        wheel.unlink()
        rewritten.rename(wheel)
    elif case == "sdist-root-renamed":
        rewritten = dist / "evil-9.9.tar.gz"
        _rewrite_sdist_identity(sdist, rewritten, root="evil-9.9")
        sdist.unlink()
    elif case == "sdist-metadata-name":
        rewritten = dist / "changed.tar.gz"
        _rewrite_sdist_identity(sdist, rewritten, metadata_changes={"Name": "evil"})
        sdist.unlink()
        rewritten.rename(sdist)
    elif case == "sdist-metadata-version":
        rewritten = dist / "changed.tar.gz"
        _rewrite_sdist_identity(sdist, rewritten, metadata_changes={"Version": "9.9"})
        sdist.unlink()
        rewritten.rename(sdist)
    else:
        rewritten_wheel = dist / "evil-9.9-py3-none-any.whl"
        _rewrite_wheel_identity(
            wheel,
            rewritten_wheel,
            dist_info_prefix="evil-9.9.dist-info",
            metadata_changes={"Name": "evil", "Version": "9.9"},
        )
        wheel.unlink()
        rewritten_sdist = dist / "evil-9.9.tar.gz"
        _rewrite_sdist_identity(
            sdist,
            rewritten_sdist,
            root="evil-9.9",
            metadata_changes={"Name": "evil", "Version": "9.9"},
        )
        sdist.unlink()

    result = subprocess.run(
        [sys.executable, str(VERIFIER), "--dist", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "distribution identity mismatch" in result.stderr


def test_public_verifier_rejects_a_duplicate_wheel_member(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    build = subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr
    wheel = next(dist.glob("*.whl"))
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(wheel, "a") as archive:
            archive.writestr("polis/analyzer.py", b"duplicate\n")

    result = subprocess.run(
        [sys.executable, str(VERIFIER), "--dist", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "duplicate archive member" in result.stderr


def test_public_verifier_rejects_an_sdist_symlink(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    build = subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr
    sdist = next(dist.glob("*.tar.gz"))
    replacement = dist / "changed.tar.gz"
    with tarfile.open(sdist) as original, tarfile.open(replacement, "w:gz") as changed:
        for member in original.getmembers():
            if member.name.endswith("/src/polis/analyzer.py"):
                member.type = tarfile.SYMTYPE
                member.linkname = "../../../../outside.py"
                member.size = 0
                changed.addfile(member)
            else:
                extracted = original.extractfile(member) if member.isfile() else None
                changed.addfile(member, extracted)
    sdist.unlink()
    replacement.rename(sdist)

    result = subprocess.run(
        [sys.executable, str(VERIFIER), "--dist", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "non-regular archive member" in result.stderr


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


def test_built_distributions_include_adr_0023(tmp_path: Path) -> None:
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
        wheel_members = set(archive.namelist())
    with tarfile.open(sdist) as archive:
        sdist_members = {_without_sdist_root(name) for name in archive.getnames()}

    assert ADR_0023_MEMBER in wheel_members
    assert ADR_0023_MEMBER in sdist_members


def test_public_verifier_rejects_a_missing_adr_0023(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
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
        members = {_without_sdist_root(name) for name in archive.getnames()}
    assert ADR_0023_MEMBER in members

    replacement = dist / "without-adr.tar.gz"
    _mutate_sdist(sdist, replacement, remove=ADR_0023_MEMBER)
    sdist.unlink()
    replacement.rename(sdist)

    result = subprocess.run(
        [sys.executable, str(VERIFIER), "--dist", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert f"missing required sdist member: {ADR_0023_MEMBER}" in result.stderr


@pytest.mark.parametrize("member", REPOSITORY_ONLY_SDIST_MEMBERS)
def test_distribution_verifier_rejects_repository_only_sdist_members(
    tmp_path: Path,
    member: str,
) -> None:
    sdist = tmp_path / "polis_nlp-0.2.0.dev0.tar.gz"
    _write_sdist(sdist, (member,))

    with pytest.raises(SystemExit):
        artifact_verifier.verify_sdist(sdist)
