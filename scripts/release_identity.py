"""Verify one immutable identity across a Polis release and its evidence."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.release_identity_artifacts import (
    artifact_metadata_version,
    create_manifest,
    require_published_digests,
    verify_published,
)
from scripts.release_identity_candidate import (
    collect_release_observations,
    require_new_candidate,
    require_recovery_candidate,
)
from scripts.release_identity_candidate import (
    require_source_commit as _candidate_require_source_commit,
)
from scripts.release_identity_download import download_pypi
from scripts.release_identity_history import (
    changelog_section,
    read_project_version,
    require_tagged_evidence,
    verify_all_tagged_evidence,
    verify_repository_tagged_evidence,
)
from scripts.release_identity_history import (
    verify_release_identity as _verify_release_identity,
)
from scripts.release_identity_history import (
    verify_tag_binding as _verify_tag_binding,
)
from scripts.release_identity_models import (
    ArtifactDigest,
    ReleaseIdentity,
    ReleaseIdentityError,
    ReleaseManifest,
    ReleaseObservations,
    TagBinding,
    release_tag,
)
from scripts.release_identity_policy import read_release_policy

_require_source_commit = _candidate_require_source_commit
__all__ = (
    "ArtifactDigest",
    "ReleaseIdentity",
    "ReleaseIdentityError",
    "ReleaseManifest",
    "ReleaseObservations",
    "TagBinding",
    "artifact_metadata_version",
    "changelog_section",
    "create_manifest",
    "main",
    "read_project_version",
    "read_release_policy",
    "release_tag",
    "require_new_candidate",
    "require_recovery_candidate",
    "require_published_digests",
    "require_tagged_evidence",
    "verify_all_tagged_evidence",
    "verify_release_identity",
    "verify_repository_tagged_evidence",
    "verify_tag_binding",
)


def verify_release_identity(
    identity: ReleaseIdentity, *, repo: Path, pyproject: Path
) -> None:
    _verify_release_identity(
        identity, repo=repo, pyproject=pyproject, source_verifier=_require_source_commit
    )


def verify_tag_binding(repo: Path, identity: ReleaseIdentity) -> None:
    _verify_tag_binding(repo, identity, source_verifier=_require_source_commit)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    candidate = commands.add_parser("candidate", help="verify a new candidate name")
    candidate.add_argument("--version", required=True)
    candidate.add_argument("--source-commit", required=True)
    candidate.add_argument(
        "--state", required=True, choices=("candidate-absent", "tag-bound")
    )
    candidate.add_argument("--repo", type=Path, default=Path("."))
    candidate.add_argument("--remote", required=True)
    candidate.add_argument("--github-repo", required=True)
    candidate.add_argument("--package-index-url", required=True)
    recovery = commands.add_parser(
        "recovery-authority", help="verify tag and project state for recovery"
    )
    recovery.add_argument("--version", required=True)
    recovery.add_argument("--source-commit", required=True)
    recovery.add_argument("--repo", type=Path, default=Path("."))
    recovery.add_argument("--remote", required=True)
    recovery.add_argument("--github-repo", required=True)
    recovery.add_argument("--package-index-url", required=True)
    manifest = commands.add_parser(
        "manifest", help="record one build-once artifact set"
    )
    manifest.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    manifest.add_argument("--repo", type=Path, default=Path("."))
    manifest.add_argument("--source-commit", required=True)
    manifest.add_argument("--dist", type=Path, default=Path("dist"))
    manifest.add_argument("--output", type=Path, required=True)
    verify_manifest = commands.add_parser(
        "verify-manifest", help="verify one build-once artifact set"
    )
    verify_manifest.add_argument("--manifest", type=Path, required=True)
    verify_manifest.add_argument("--dist", type=Path, required=True)
    verify_manifest.add_argument("--source-commit", required=True)
    download = commands.add_parser(
        "download-pypi", help="download exactly one verified artifact set"
    )
    download.add_argument("--package-index-url", required=True)
    download.add_argument("--version", required=True)
    download.add_argument("--manifest", type=Path, required=True)
    download.add_argument("--source-commit", required=True)
    download.add_argument("--output", type=Path, required=True)
    download.add_argument("--max-attempts", type=int, required=True)
    download.add_argument("--retry-seconds", type=float, required=True)
    policy = commands.add_parser("verify-policy", help="verify tracked release policy")
    policy.add_argument(
        "--policy", type=Path, default=Path("docs/project/release-policy.json")
    )
    history = commands.add_parser(
        "verify-history", help="verify immutable tagged notes"
    )
    history.add_argument("--repo", type=Path, default=Path("."))
    history.add_argument("--tag", required=True)
    history.add_argument("--version", required=True)
    history_all = commands.add_parser(
        "verify-all-history",
        help="verify every tagged release note and changelog section",
    )
    history_all.add_argument("--repo", type=Path, default=Path("."))
    published = commands.add_parser(
        "verify-published", help="compare published asset digests with one manifest"
    )
    published.add_argument("--manifest", type=Path, required=True)
    published.add_argument("--published-digests", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "candidate":
        identity = ReleaseIdentity.create(
            version=args.version, source_commit=args.source_commit
        )
        _require_source_commit(args.repo, identity.source_commit)
        observations = collect_release_observations(
            repo=args.repo,
            tag=identity.tag,
            remote=args.remote,
            github_repo=args.github_repo,
            package_index_url=args.package_index_url,
        )
        require_new_candidate(identity, state=args.state, observations=observations)
        print(f"candidate identity is available: {identity.tag}")
        return 0
    if args.command == "recovery-authority":
        identity = ReleaseIdentity.create(
            version=args.version, source_commit=args.source_commit
        )
        _require_source_commit(args.repo, identity.source_commit)
        observations = collect_release_observations(
            repo=args.repo,
            tag=identity.tag,
            remote=args.remote,
            github_repo=args.github_repo,
            package_index_url=args.package_index_url,
        )
        require_recovery_candidate(identity, observations=observations)
        print(f"recovery identity is bound: {identity.tag}")
        return 0
    if args.command == "manifest":
        identity = ReleaseIdentity.create(
            version=read_project_version(args.pyproject),
            source_commit=args.source_commit,
        )
        _require_source_commit(args.repo, identity.source_commit)
        args.output.write_text(
            create_manifest(identity, args.dist).to_json(), encoding="utf-8"
        )
        print(f"recorded build-once manifest: {args.output}")
        return 0
    if args.command == "verify-manifest":
        manifest_value = ReleaseManifest.from_json(
            args.manifest.read_text(encoding="utf-8")
        )
        if manifest_value.identity.source_commit != args.source_commit:
            raise ReleaseIdentityError("manifest source commit does not match input")
        manifest_value.verify_artifacts(args.dist)
        print(
            "verified=2 "
            f"version={manifest_value.identity.version} "
            f"source_commit={manifest_value.identity.source_commit}"
        )
        return 0
    if args.command == "download-pypi":
        manifest_value = ReleaseManifest.from_json(
            args.manifest.read_text(encoding="utf-8")
        )
        if str(manifest_value.identity.version) != args.version:
            raise ReleaseIdentityError("manifest version does not match input")
        if manifest_value.identity.source_commit != args.source_commit:
            raise ReleaseIdentityError("manifest source commit does not match input")
        download_pypi(
            package_index_url=args.package_index_url,
            manifest=manifest_value,
            output=args.output,
            max_attempts=args.max_attempts,
            retry_seconds=args.retry_seconds,
        )
        print(
            "downloaded=2 "
            f"verified=2 version={manifest_value.identity.version} "
            f"source_commit={manifest_value.identity.source_commit}"
        )
        return 0
    if args.command == "verify-policy":
        print(
            f"approved_plan_sha256={read_release_policy(args.policy).approved_plan_sha256}"
        )
        return 0
    if args.command == "verify-history":
        verify_repository_tagged_evidence(args.repo, tag=args.tag, version=args.version)
        print(f"tagged evidence is immutable: {args.tag}")
        return 0
    if args.command == "verify-all-history":
        verify_all_tagged_evidence(args.repo)
        print("all tagged release evidence is immutable")
        return 0
    if args.command == "verify-published":
        verify_published(args.manifest, args.published_digests)
        return 0
    raise AssertionError(f"unsupported release identity command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseIdentityError as error:
        raise SystemExit(f"release identity check failed: {error}") from error
