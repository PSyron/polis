from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from scripts.verify_distribution_install import FORBIDDEN_REPOSITORY_MODULES

ROOT = Path(__file__).resolve().parents[1]
PREPARE = ROOT / "scripts/prepare_build_wheelhouse.py"
VERIFY_INSTALL = ROOT / "scripts/verify_distribution_install.py"
VERIFY_ARTIFACTS = ROOT / "scripts/verify_distribution_artifacts.py"
EXPECTED_PACKAGES = {
    "hatchling": "1.31.0",
    "packaging": "26.2",
    "pathspec": "1.1.1",
    "pluggy": "1.6.0",
    "trove-classifiers": "2026.6.1.19",
}
EVALUATION_INIT = "polis/evaluation/__init__.py"
EVALUATION_SOURCE = ROOT / "src" / "polis" / "evaluation"
EXPECTED_FORBIDDEN_REPOSITORY_MODULES = tuple(
    f"polis.evaluation.{path.stem}"
    for path in sorted(
        (
            EVALUATION_SOURCE / "__main__.py",
            *EVALUATION_SOURCE.glob("calibration_*.py"),
            *EVALUATION_SOURCE.glob("holdout_*.py"),
        )
    )
)


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


@pytest.fixture(scope="session")
def repository_module_mutation_inputs(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, Path, Path]:
    return _prepare_release_inputs(tmp_path_factory.mktemp("repository-module-inputs"))


def _empty_smoke_cwd(base: Path) -> Path:
    smoke_cwd = base / "smoke-cwd"
    smoke_cwd.mkdir(exist_ok=True)
    return smoke_cwd


def _remove_distribution_member(dist: Path, member: str) -> None:
    wheel = next(dist.glob("*.whl"))
    changed_wheel = dist / "changed.whl"
    with (
        zipfile.ZipFile(wheel) as original,
        zipfile.ZipFile(changed_wheel, "w") as changed,
    ):
        for name in original.namelist():
            if name != member.removeprefix("src/"):
                changed.writestr(name, original.read(name))
    wheel.unlink()
    changed_wheel.rename(wheel)

    sdist = next(dist.glob("*.tar.gz"))
    changed_sdist = dist / "changed.tar.gz"
    with (
        tarfile.open(sdist) as original,
        tarfile.open(changed_sdist, "w:gz") as changed,
    ):
        for archive_member in original.getmembers():
            if archive_member.name.endswith(f"/{member}"):
                continue
            source = original.extractfile(archive_member)
            changed.addfile(archive_member, source)
    sdist.unlink()
    changed_sdist.rename(sdist)


def _add_distribution_member(dist: Path, member: str) -> None:
    wheel = next(dist.glob("*.whl"))
    changed_wheel = dist / "changed.whl"
    with (
        zipfile.ZipFile(wheel) as original,
        zipfile.ZipFile(changed_wheel, "w") as changed,
    ):
        for name in original.namelist():
            changed.writestr(name, original.read(name))
        payload = b"repository_only_test_module = True\n"
        if member.endswith(".py") or member.endswith("__main__.py"):
            payload = b'"repository-only-sentinel"\n'
        changed.writestr(member.removeprefix("src/"), payload)
    wheel.unlink()
    changed_wheel.rename(wheel)

    sdist = next(dist.glob("*.tar.gz"))
    changed_sdist = dist / "changed.tar.gz"
    with (
        tarfile.open(sdist) as original,
        tarfile.open(changed_sdist, "w:gz") as changed,
    ):
        for archive_member in original.getmembers():
            source = original.extractfile(archive_member)
            changed.addfile(archive_member, source)
        root = original.getnames()[0].split("/", 1)[0]
        content = b"repository_only_test_module = True\n"
        if member.endswith(".py") or member.endswith("__main__.py"):
            content = b'"repository-only-sentinel"\n'
        extra = tarfile.TarInfo(f"{root}/{member}")
        extra.size = len(content)
        changed.addfile(extra, BytesIO(content))
    sdist.unlink()
    changed_sdist.rename(sdist)


@pytest.mark.parametrize(
    "member",
    (
        pytest.param("src/polis/evaluation/quality_protocol.py", id="quality_module"),
        pytest.param(
            "src/polis/evaluation/datasets/quality/v1/cases.json",
            id="quality_cases",
        ),
        pytest.param(
            "src/polis/evaluation/datasets/quality/v1/manifest.json",
            id="quality_manifest",
        ),
        pytest.param(
            "src/polis/evaluation/datasets/quality/v2/cases.json",
            id="quality_v2_cases",
        ),
        pytest.param(
            "src/polis/evaluation/datasets/quality/v2/manifest.json",
            id="quality_v2_manifest",
        ),
        pytest.param(
            "src/polis/evaluation/datasets/quality/v3/cases.json",
            id="quality_v3_cases",
        ),
        pytest.param(
            "src/polis/evaluation/datasets/quality/v3/manifest.json",
            id="quality_v3_manifest",
        ),
    ),
)
def test_distribution_artifact_verifier_rejects_missing_quality_members(
    tmp_path: Path, member: str
) -> None:
    dist, _, _ = _prepare_release_inputs(tmp_path)
    _remove_distribution_member(dist, member)

    result = _run([sys.executable, str(VERIFY_ARTIFACTS), "--dist", str(dist)])

    assert result.returncode != 0
    assert f"missing package member: {member}" in result.stderr


def test_distribution_artifact_verifier_rejects_unexpected_quality_member(
    tmp_path: Path,
) -> None:
    dist, _, _ = _prepare_release_inputs(tmp_path)
    member = "src/polis/evaluation/quality_unapproved.py"
    _add_distribution_member(dist, member)

    result = _run([sys.executable, str(VERIFY_ARTIFACTS), "--dist", str(dist)])

    assert result.returncode != 0
    assert f"wheel member outside release surface: {member}" in result.stderr


def _replace_evaluation_exports(dist: Path, replacement: str) -> None:
    wheel = next(dist.glob("*.whl"))
    changed_wheel = dist / "changed.whl"
    with zipfile.ZipFile(wheel) as original:
        with zipfile.ZipFile(changed_wheel, "w") as changed:
            for name in original.namelist():
                wheel_content = original.read(name)
                if name == EVALUATION_INIT:
                    wheel_content = replacement.encode("utf-8")
                changed.writestr(name, wheel_content)
    wheel.unlink()
    changed_wheel.rename(wheel)

    sdist = next(dist.glob("*.tar.gz"))
    changed_sdist = dist / "changed.tar.gz"
    with tarfile.open(sdist) as original:
        with tarfile.open(changed_sdist, "w:gz") as changed:
            for member in original.getmembers():
                source = original.extractfile(member) if member.isfile() else None
                tar_content: bytes | None = (
                    source.read() if source is not None else None
                )
                if member.name.endswith(f"src/{EVALUATION_INIT}"):
                    tar_content = replacement.encode("utf-8")
                    member.size = len(tar_content)
                changed.addfile(
                    member,
                    BytesIO(tar_content) if tar_content is not None else None,
                )
    sdist.unlink()
    changed_sdist.rename(sdist)


@pytest.mark.parametrize(
    ("variant", "needle", "replacement"),
    (
        (
            "seventeen",
            '    "validate_safety_corpus",\n',
            "",
        ),
        (
            "nineteen",
            '    "validate_safety_corpus",\n]',
            '    "validate_safety_corpus",\n    "unexpected_public_export",\n]',
        ),
    ),
)
def test_public_install_verifier_rejects_evaluation_export_count_variants(
    tmp_path: Path, variant: str, needle: str, replacement: str
) -> None:
    dist, wheelhouse, manifest = _prepare_release_inputs(tmp_path)
    source = (ROOT / "src" / EVALUATION_INIT).read_text(encoding="utf-8")
    assert needle in source
    _replace_evaluation_exports(dist, source.replace(needle, replacement, 1))

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
            "--smoke-cwd",
            str(_empty_smoke_cwd(tmp_path)),
        ]
    )

    assert result.returncode != 0, f"{variant}: {result.stdout}{result.stderr}"
    assert "evaluation export contract" in result.stderr


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
    inherited_pythonpath = tmp_path / "inherited-pythonpath"
    inherited_pythonpath.mkdir()
    inherited_marker = tmp_path / "inherited-pythonpath-used"
    (inherited_pythonpath / "sitecustomize.py").write_text(
        "import os\n"
        "import sys\n"
        "from pathlib import Path\n"
        "if not sys.argv[0].endswith('verify_distribution_install.py'):\n"
        "    Path(os.environ['POLIS_INHERITED_PYTHONPATH_MARKER']).write_text(\n"
        "        os.getcwd(), encoding='utf-8'\n"
        "    )\n",
        encoding="utf-8",
    )

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
            "--smoke-cwd",
            str(_empty_smoke_cwd(tmp_path)),
        ],
        env=os.environ
        | {
            "PYTHONIOENCODING": "cp1252",
            "PYTHONPATH": str(inherited_pythonpath),
            "POLIS_INHERITED_PYTHONPATH_MARKER": str(inherited_marker),
        },
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "socket.connect=blocked" in result.stdout
    assert "socket.connect_ex=blocked" in result.stdout
    assert "socket.create_connection=blocked" in result.stdout
    assert "socket.sendto=blocked" in result.stdout
    if hasattr(socket.socket, "sendmsg"):
        assert "socket.sendmsg=blocked" in result.stdout
    else:
        assert "socket.sendmsg=blocked" not in result.stdout
    assert "artifact=wheel version=0.2.0 issues=1" in result.stdout
    assert "artifact=sdist version=0.2.0 issues=1" in result.stdout
    assert result.stdout.count("public_dataset_imports=ok") == 2
    assert result.stdout.count("repository_only_modules=absent") == 2
    assert result.stdout.count("public_resource=") == 10
    assert result.stdout.count("forbidden_module=") == (
        2 * len(EXPECTED_FORBIDDEN_REPOSITORY_MODULES)
    )
    assert result.stdout.count("repository_only_evaluation_cli=absent") == 2
    assert '"text":"Witaj,świecie."' in result.stdout
    assert "http://" not in result.stdout.lower()
    assert "https://" not in result.stdout.lower()
    assert not inherited_marker.exists()


def test_public_install_verifier_requires_an_explicit_empty_smoke_cwd(
    tmp_path: Path,
) -> None:
    dist, wheelhouse, manifest = _prepare_release_inputs(tmp_path)
    smoke_cwd = tmp_path / "smoke-cwd"
    smoke_cwd.mkdir()

    missing = _run(
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

    assert missing.returncode != 0
    assert "--smoke-cwd" in missing.stderr

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
            "--smoke-cwd",
            str(smoke_cwd),
        ],
        env=os.environ | {"PYTHONIOENCODING": "cp1252"},
    )

    assert result.returncode == 0, result.stderr + result.stdout
    assert "smoke-cwd=" + str(smoke_cwd.resolve()) in result.stdout
    assert list(smoke_cwd.iterdir()) == []


@pytest.mark.parametrize("kind", ["missing", "file", "nonempty"])
def test_public_install_verifier_rejects_invalid_smoke_cwd(
    tmp_path: Path, kind: str
) -> None:
    dist, wheelhouse, manifest = _prepare_release_inputs(tmp_path)
    smoke_cwd = tmp_path / "smoke-cwd"
    if kind == "file":
        smoke_cwd.write_text("not a directory", encoding="utf-8")
    elif kind == "nonempty":
        smoke_cwd.mkdir()
        (smoke_cwd / "unexpected").write_text("content", encoding="utf-8")

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
            "--smoke-cwd",
            str(smoke_cwd),
        ]
    )

    assert result.returncode != 0
    assert "smoke cwd" in result.stderr.lower()


def test_public_install_verifier_rejects_smoke_cwd_inside_checkout(
    tmp_path: Path,
) -> None:
    dist, wheelhouse, manifest = _prepare_release_inputs(tmp_path)
    smoke_cwd = ROOT / f".polis-test-smoke-cwd-{tmp_path.name}"
    smoke_cwd.mkdir()
    try:
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
                "--smoke-cwd",
                str(smoke_cwd),
            ]
        )
    finally:
        smoke_cwd.rmdir()

    assert result.returncode != 0
    assert "outside checkout" in result.stderr.lower()


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
            "--smoke-cwd",
            str(_empty_smoke_cwd(tmp_path)),
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
            "--smoke-cwd",
            str(_empty_smoke_cwd(tmp_path)),
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
            "--smoke-cwd",
            str(_empty_smoke_cwd(tmp_path)),
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
            "--smoke-cwd",
            str(_empty_smoke_cwd(tmp_path)),
        ]
    )

    assert result.returncode != 0
    assert "manifest is malformed" in result.stderr


def test_repository_only_boundary_matches_independent_source_discovery() -> None:
    assert FORBIDDEN_REPOSITORY_MODULES == EXPECTED_FORBIDDEN_REPOSITORY_MODULES


@pytest.mark.parametrize("module", EXPECTED_FORBIDDEN_REPOSITORY_MODULES)
def test_public_install_verifier_rejects_repository_only_evaluation_modules(
    tmp_path: Path,
    repository_module_mutation_inputs: tuple[Path, Path, Path],
    module: str,
) -> None:
    source_dist, source_wheelhouse, source_manifest = repository_module_mutation_inputs
    dist = shutil.copytree(source_dist, tmp_path / "dist")
    wheelhouse = shutil.copytree(source_wheelhouse, tmp_path / "wheelhouse")
    manifest = tmp_path / "wheelhouse-manifest.json"
    shutil.copy2(source_manifest, manifest)
    _add_distribution_member(dist, f"src/{module.replace('.', '/')}.py")

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
            "--smoke-cwd",
            str(_empty_smoke_cwd(tmp_path)),
        ]
    )

    assert result.returncode != 0
    assert f"exposed repository-only module: {module}" in result.stderr


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
            "--smoke-cwd",
            str(_empty_smoke_cwd(tmp_path)),
        ]
    )

    assert result.returncode != 0
    assert "manifest does not match uv.lock" in result.stderr
