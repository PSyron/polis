"""End-to-end prerelease verification for build, quality, and offline gates."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    executable = shutil.which(cmd[0])
    if executable is None:
        raise SystemExit(f"could not resolve prerequisite command: {cmd[0]}")
    subprocess.run([executable, *cmd[1:]], cwd=cwd, check=True)


def _git_output(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit("could not inspect prerelease source state")
    return result.stdout.strip()


def _require_source_state(source_commit: str) -> Path:
    root = Path(__file__).resolve().parents[1]
    head = _git_output(root, "rev-parse", "HEAD")
    if source_commit != head:
        raise SystemExit("source commit must equal current repository HEAD")
    if _git_output(root, "status", "--porcelain", "--untracked-files=all"):
        raise SystemExit("repository worktree must be clean")
    return root


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_artifacts(dist: Path) -> tuple[Path, Path]:
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit("dist must contain exactly one wheel and one source archive")
    return wheels[0], sdists[0]


def _print_hashes(wheel: Path, sdist: Path) -> None:
    print(f"wheel {wheel.name} sha256={_sha256(wheel)}")
    print(f"sdist {sdist.name} sha256={_sha256(sdist)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify prerelease readiness")
    parser.add_argument(
        "--dist",
        type=Path,
        default=Path("dist"),
        help="Artifact directory",
    )
    parser.add_argument(
        "--source-commit",
        required=True,
        help="Immutable commit SHA bound to the build-once release manifest",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Output path for the build-once release manifest",
    )
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--wheelhouse-manifest", type=Path, required=True)
    args = parser.parse_args()
    root = _require_source_state(args.source_commit)
    dist = (root / args.dist).resolve()
    manifest = (
        (root / args.manifest).resolve()
        if args.manifest
        else dist / "release-manifest.json"
    )
    wheelhouse = (root / args.wheelhouse).resolve()
    wheelhouse_manifest = (root / args.wheelhouse_manifest).resolve()

    _run(
        [
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "pytest",
            "-m",
            "not research and not slow",
        ],
        cwd=root,
    )

    _run(
        ["uv", "run", "--locked", "--extra", "dev", "ruff", "check", "."],
        cwd=root,
    )
    _run(
        [
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "ruff",
            "format",
            "--check",
            ".",
        ],
        cwd=root,
    )
    _run(["uv", "run", "--locked", "--extra", "dev", "mypy", "."], cwd=root)
    _run(
        [
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "python",
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(dist),
        ],
        cwd=root,
    )
    _run(
        [
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "python",
            "scripts/verify_distribution_artifacts.py",
            "--dist",
            str(dist),
        ],
        cwd=root,
    )
    with tempfile.TemporaryDirectory(prefix="polis-prerelease-smoke-") as smoke_cwd:
        _run(
            [
                "uv",
                "run",
                "--locked",
                "--extra",
                "dev",
                "python",
                "scripts/verify_distribution_install.py",
                "--dist",
                str(dist),
                "--wheelhouse",
                str(wheelhouse),
                "--wheelhouse-manifest",
                str(wheelhouse_manifest),
                "--smoke-cwd",
                smoke_cwd,
            ],
            cwd=root,
        )

    _run(
        [
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "python",
            "scripts/release_identity.py",
            "manifest",
            "--source-commit",
            args.source_commit,
            "--dist",
            str(dist),
            "--output",
            str(manifest),
        ],
        cwd=root,
    )

    wheel, sdist = _collect_artifacts(dist)
    _print_hashes(wheel, sdist)
    print(f"publish only the manifest artifact set: {manifest}")


if __name__ == "__main__":
    main()
