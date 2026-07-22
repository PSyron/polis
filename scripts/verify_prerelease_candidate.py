"""End-to-end prerelease verification for build, quality, and offline gates."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING or __package__:
    from scripts import release_identity
else:
    import release_identity


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd, check=True)


def _require_clean_output(dist: Path, manifest: Path) -> None:
    stale = sorted((*dist.glob("*.whl"), *dist.glob("*.tar.gz")))
    if stale or manifest.exists():
        names = [path.name for path in stale]
        if manifest.exists():
            names.append(str(manifest))
        raise SystemExit(
            "release output must be empty before the single build: " + ", ".join(names)
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify prerelease readiness")
    parser.add_argument(
        "--dist",
        type=Path,
        default=Path("dist"),
        help="Artifact directory",
    )
    parser.add_argument("--version", required=True, help="Exact candidate version")
    parser.add_argument("--tag", required=True, help="Exact requested v<version> tag")
    parser.add_argument(
        "--previous-version",
        required=True,
        help="Immediately preceding source lifecycle version",
    )
    parser.add_argument("--latest-stable", required=True)
    parser.add_argument(
        "--manifest", type=Path, required=True, help="Frozen manifest output path"
    )
    parser.add_argument(
        "--check-pypi",
        action="store_true",
        required=True,
        help="Release-only network check for version reuse",
    )
    args = parser.parse_args()
    dist = args.dist
    root = Path.cwd()
    manifest_path = args.manifest.resolve()
    release_identity.require_clean_worktree(root)
    _require_clean_output(dist, manifest_path)
    published_versions = release_identity.fetch_published_versions()
    existing_tags = release_identity.list_local_tags(root)
    if args.tag in existing_tags:
        raise SystemExit(f"requested release tag already exists: {args.tag}")
    latest_stable_tag = f"v{args.latest_stable}"
    if latest_stable_tag not in existing_tags:
        raise SystemExit(f"latest stable tag is missing locally: {latest_stable_tag}")
    for historical_tag in sorted(existing_tags):
        if historical_tag.startswith("v"):
            release_identity.verify_tagged_evidence(root, historical_tag)
    release_identity.validate_published_history(
        previous=args.previous_version,
        requested=args.version,
        published_versions=published_versions,
    )
    release_identity.validate_candidate(
        args.version,
        latest_stable=args.latest_stable,
        published_versions=published_versions,
    )

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
            "--outdir",
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

    manifest = release_identity.freeze_manifest(
        root=Path.cwd(),
        dist=dist.resolve(),
        manifest_path=args.manifest.resolve(),
        requested_version=args.version,
        requested_tag=args.tag,
        previous_version=args.previous_version,
        latest_stable=args.latest_stable,
        published_versions=published_versions,
        existing_tags=existing_tags,
        source_commit=release_identity.current_commit(root),
    )
    for artifact in manifest["artifacts"]:
        print(f"{artifact['filename']} sha256={artifact['sha256']}")


if __name__ == "__main__":
    main()
