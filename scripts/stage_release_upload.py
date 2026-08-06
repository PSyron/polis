from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.release_identity_authority import project_is_absent, read_json
from scripts.release_identity_models import (
    COMMIT_RE,
    ArtifactDigest,
    ReleaseIdentityError,
    ReleaseManifest,
)
from scripts.release_identity_policy import GateReceiptBinding, validate_gate_receipt


def _read_run(path: Path, *, run_id: int, source_commit: str) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ReleaseIdentityError("run metadata is unreadable") from error
    repository = payload.get("repository") if isinstance(payload, dict) else None
    expected = (
        payload.get("id") == run_id
        and payload.get("head_sha") == source_commit
        and payload.get("conclusion") == "success"
        and payload.get("event") == "workflow_dispatch"
        and payload.get("path") == ".github/workflows/release.yml"
        and isinstance(repository, dict)
        and repository.get("full_name") == "PSyron/polis"
    )
    if not expected:
        raise ReleaseIdentityError("run metadata does not match the qualify run")


def _receipt_file(raw: str, directory: Path) -> Path:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReleaseIdentityError("gate receipt JSON is invalid") from error
    if not isinstance(payload, dict):
        raise ReleaseIdentityError("gate receipt JSON must be an object")
    compact = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if raw != compact:
        raise ReleaseIdentityError("gate receipt JSON must be canonical compact JSON")
    path = directory / "receipt.json"
    path.write_text(raw + "\n", encoding="utf-8")
    return path


def _require_empty_output(output: Path) -> None:
    if not output.is_dir() or any(output.iterdir()):
        raise ReleaseIdentityError("publish output must be an existing empty directory")


def _require_exact_dist(dist: Path, manifest: ReleaseManifest) -> None:
    try:
        members = list(dist.iterdir())
    except OSError as error:
        raise ReleaseIdentityError(
            "release manifest distribution directory is unreadable"
        ) from error
    expected = {artifact.filename for artifact in manifest.artifacts}
    if {member.name for member in members} != expected or any(
        member.is_symlink() or not member.is_file() for member in members
    ):
        raise ReleaseIdentityError("release manifest distribution set is not exact")


def _recovery_artifact(
    package_index_url: str,
    manifest: ReleaseManifest,
    recovery_filename: str,
) -> ArtifactDigest:
    payload = read_json(package_index_url)
    if not isinstance(payload, dict):
        raise ReleaseIdentityError("package index project JSON has an invalid schema")
    releases = payload.get("releases")
    if not isinstance(releases, dict):
        raise ReleaseIdentityError("package index project JSON has an invalid schema")
    files = releases.get(str(manifest.identity.version))
    if not isinstance(files, list):
        raise ReleaseIdentityError("package index release files have an invalid schema")
    if len(files) != 1:
        raise ReleaseIdentityError(
            "recovery requires exactly one existing package index file"
        )
    file = files[0]
    if not isinstance(file, dict):
        raise ReleaseIdentityError("package index release file has an invalid schema")
    filename = file.get("filename")
    size = file.get("size")
    digests = file.get("digests")
    sha256 = digests.get("sha256") if isinstance(digests, dict) else None
    expected = {artifact.filename: artifact for artifact in manifest.artifacts}
    if not isinstance(filename, str) or filename not in expected:
        raise ReleaseIdentityError("package index file is absent from release manifest")
    existing = expected[filename]
    if not isinstance(size, int) or isinstance(size, bool) or size != existing.size:
        raise ReleaseIdentityError(
            "package index file size differs from release manifest"
        )
    if not isinstance(sha256, str) or sha256 != existing.sha256:
        raise ReleaseIdentityError(
            "package index file SHA-256 differs from release manifest"
        )
    missing = set(expected).difference((filename,))
    if recovery_filename not in expected or missing != {recovery_filename}:
        raise ReleaseIdentityError(
            "recovery filename must identify the one missing manifest artifact"
        )
    return expected[recovery_filename]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify release bindings and stage an allowlisted upload."
    )
    parser.add_argument("--mode", choices=("publish", "recover"), required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--artifact-run-id", type=int, required=True)
    parser.add_argument("--run-metadata", type=Path, required=True)
    parser.add_argument("--receipt-json", required=True)
    parser.add_argument("--release-manifest", type=Path, required=True)
    parser.add_argument("--wheelhouse-manifest", type=Path, required=True)
    parser.add_argument("--release-policy", type=Path, required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package-index-url", required=True)
    parser.add_argument("--recovery-filename", default="")
    args = parser.parse_args(argv)
    if not COMMIT_RE.fullmatch(args.source_commit):
        raise ReleaseIdentityError("publish source commit is invalid")
    _read_run(
        args.run_metadata,
        run_id=args.artifact_run_id,
        source_commit=args.source_commit,
    )
    manifest = ReleaseManifest.from_json(
        args.release_manifest.read_text(encoding="utf-8")
    )
    if manifest.identity.source_commit != args.source_commit:
        raise ReleaseIdentityError("release manifest source commit is wrong")
    _require_exact_dist(args.dist, manifest)
    manifest.verify_artifacts(args.dist)
    _require_empty_output(args.output)
    with tempfile.TemporaryDirectory(prefix="polis-release-receipt-") as temporary:
        receipt = _receipt_file(args.receipt_json, Path(temporary))
        validate_gate_receipt(
            receipt,
            GateReceiptBinding(
                source_commit=args.source_commit,
                release_manifest=args.release_manifest,
                wheelhouse_manifest=args.wheelhouse_manifest,
                qualify_run_id=args.artifact_run_id,
                plan=args.plan,
                release_policy=args.release_policy,
                approvals=("APPROVE", "APPROVE", "APPROVE", "APPROVE"),
                user_approval="okay",
            ),
        )
    match args.mode:
        case "publish":
            if args.recovery_filename:
                raise ReleaseIdentityError("publish forbids a recovery filename")
            if not project_is_absent(args.package_index_url):
                raise ReleaseIdentityError("configured package project already exists")
            artifacts = manifest.artifacts
        case "recover":
            artifacts = (
                _recovery_artifact(
                    args.package_index_url, manifest, args.recovery_filename
                ),
            )
        case unreachable:
            raise AssertionError(unreachable)
    for artifact in artifacts:
        shutil.copyfile(args.dist / artifact.filename, args.output / artifact.filename)
    if args.mode == "publish":
        print("staged=2 mode=publish")
    else:
        print(f"staged=1 mode=recover filename={artifacts[0].filename}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ReleaseIdentityError) as error:
        raise SystemExit(f"release upload staging failed: {error}") from error
