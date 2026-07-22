"""End-to-end prerelease verification for build, quality, and offline gates."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
from pathlib import Path


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


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
    args = parser.parse_args()
    dist = args.dist
    manifest = args.manifest or dist / "release-manifest.json"

    _run(
        [
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "pytest",
            "-m",
            "not slow and not model",
        ]
    )

    _run(["uv", "run", "--locked", "--extra", "dev", "ruff", "check", "."])
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
        ]
    )
    _run(["uv", "run", "--locked", "--extra", "dev", "mypy", "."])
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
        ]
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
        ]
    )
    _run(
        [
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "pytest",
            "-q",
            "tests/test_offline_verification.py",
        ]
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
        ]
    )

    wheel, sdist = _collect_artifacts(dist)
    _print_hashes(wheel, sdist)
    print(f"publish only the manifest artifact set: {manifest}")


if __name__ == "__main__":
    main()
