"""Freeze and verify one immutable identity for every Polis release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
import tomllib
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Self

_VERSION = re.compile(
    r"(?P<major>0|[1-9]\d*)\."
    r"(?P<minor>0|[1-9]\d*)\."
    r"(?P<patch>0|[1-9]\d*)"
    r"(?:(?P<rc>rc(?:[1-9]\d*))|(?P<dev>\.dev0))?\Z"
)
_PROJECT = "polis-nlp"
_PYPI_URL = f"https://pypi.org/pypi/{_PROJECT}"
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_Opener = Callable[..., Any]


@dataclass(frozen=True)
class ReleaseVersion:
    """A canonical version in the Polis dev0 -> rcN -> stable lifecycle."""

    major: int
    minor: int
    patch: int
    stage: str
    rc_number: int | None = None

    @classmethod
    def parse(cls, value: str) -> Self:
        match = _VERSION.fullmatch(value)
        if match is None:
            raise ValueError(
                f"{value!r} is not in the canonical release lifecycle "
                "MAJOR.MINOR.PATCH.dev0, MAJOR.MINOR.PATCHrcN, or "
                "MAJOR.MINOR.PATCH"
            )
        rc = match.group("rc")
        return cls(
            major=int(match.group("major")),
            minor=int(match.group("minor")),
            patch=int(match.group("patch")),
            stage="dev" if match.group("dev") else "rc" if rc else "stable",
            rc_number=int(rc[2:]) if rc else None,
        )

    @property
    def base(self) -> tuple[int, int, int]:
        return self.major, self.minor, self.patch

    @property
    def ordering_key(self) -> tuple[int, int, int, int, int]:
        stage_order = {"dev": 0, "rc": 1, "stable": 2}[self.stage]
        return (*self.base, stage_order, self.rc_number or 0)


def validate_transition(current: str, requested: str) -> None:
    """Validate one adjacent step in a release's source-version lifecycle."""

    old = ReleaseVersion.parse(current)
    new = ReleaseVersion.parse(requested)
    if new.ordering_key <= old.ordering_key:
        raise ValueError("requested release version must strictly advance")
    if old.stage == "stable":
        raise ValueError("stable source must move to the next dev0 before release work")
    if new.base != old.base:
        raise ValueError("an active release sequence must keep the same base version")
    if old.stage == "dev":
        if new.stage == "stable":
            raise ValueError("a stable release must pass through an rc")
        if new.stage != "rc" or new.rc_number != 1:
            raise ValueError("the first candidate must be rc1")
        return
    if new.stage == "stable":
        return
    if new.stage != "rc" or new.rc_number != (old.rc_number or 0) + 1:
        raise ValueError("release candidates must advance by exactly one rc number")


def validate_candidate(
    requested: str, *, latest_stable: str, published_versions: set[str]
) -> None:
    """Reject non-release, reused, or non-increasing public versions."""

    candidate = ReleaseVersion.parse(requested)
    previous = ReleaseVersion.parse(latest_stable)
    if candidate.stage == "dev":
        raise ValueError("development versions cannot be published")
    if previous.stage != "stable":
        raise ValueError("latest stable must identify a stable release")
    if published_versions:
        published_stables = [
            (ReleaseVersion.parse(version), version)
            for version in published_versions
            if ReleaseVersion.parse(version).stage == "stable"
        ]
        if not published_stables:
            raise ValueError("published history has no canonical stable release")
        _, actual_latest = max(published_stables, key=lambda item: item[0].ordering_key)
        if latest_stable != actual_latest:
            raise ValueError(
                f"latest published stable is {actual_latest}, not {latest_stable}"
            )
    if candidate.base <= previous.base:
        raise ValueError("candidate base version must be higher than latest stable")
    if requested in published_versions:
        raise ValueError(f"release version {requested} is already published")


def validate_published_history(
    *, previous: str, requested: str, published_versions: set[str]
) -> None:
    """Bind an rc/stable transition to the versions already present on PyPI."""

    validate_transition(previous, requested)
    if not published_versions:
        return
    old = ReleaseVersion.parse(previous)
    new = ReleaseVersion.parse(requested)
    active = [
        (ReleaseVersion.parse(version), version)
        for version in published_versions
        if ReleaseVersion.parse(version).base == new.base
    ]
    if old.stage == "rc" and previous not in published_versions:
        raise ValueError(f"previous rc must already be published: {previous}")
    if old.stage == "dev":
        if active:
            raise ValueError(
                "rc1 requires no existing publication for its base version"
            )
        return
    if not active:
        raise ValueError("published history is missing the previous rc")
    _, latest_active = max(active, key=lambda item: item[0].ordering_key)
    if latest_active != previous:
        raise ValueError(
            f"previous version must be latest published candidate {latest_active}"
        )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_version_from_text(content: str) -> str:
    payload = tomllib.loads(content)
    project = payload.get("project")
    if not isinstance(project, dict):
        raise ValueError("pyproject [project].version is missing")
    version = project.get("version")
    if not isinstance(version, str):
        raise ValueError("pyproject [project].version is missing")
    return version


def _project_version(root: Path) -> str:
    return _project_version_from_text(
        (root / "pyproject.toml").read_text(encoding="utf-8")
    )


def _artifact_metadata(path: Path) -> bytes:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            names = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            if len(names) != 1:
                raise ValueError(f"artifact {path.name} must contain one METADATA file")
            return archive.read(names[0])
    with tarfile.open(path, "r:gz") as archive:
        members = [
            member
            for member in archive.getmembers()
            if member.name.endswith("/PKG-INFO")
        ]
        if len(members) != 1:
            raise ValueError(f"artifact {path.name} must contain one PKG-INFO file")
        source = archive.extractfile(members[0])
        if source is None:
            raise ValueError(f"artifact {path.name} metadata cannot be read")
        return source.read()


def _verify_artifacts(dist: Path, version: str) -> list[Path]:
    normalized = version.replace("-", "_")
    expected_names = {
        f"polis_nlp-{normalized}-py3-none-any.whl",
        f"polis_nlp-{version}.tar.gz",
    }
    artifacts = sorted((*dist.glob("*.whl"), *dist.glob("*.tar.gz")))
    actual_names = {path.name for path in artifacts}
    if actual_names != expected_names or len(artifacts) != 2:
        raise ValueError(
            f"artifact identity mismatch: expected {sorted(expected_names)}, "
            f"found {sorted(actual_names)}"
        )
    for artifact in artifacts:
        metadata = BytesParser().parsebytes(_artifact_metadata(artifact))
        if metadata["Name"] != _PROJECT or metadata["Version"] != version:
            raise ValueError(
                f"artifact {artifact.name} metadata must identify {_PROJECT} {version}"
            )
    return artifacts


def _changelog_section(content: bytes, version: str) -> bytes:
    marker = f"## {version} (".encode()
    matches = list(re.finditer(rb"(?m)^" + re.escape(marker), content))
    if len(matches) != 1:
        raise ValueError(
            f"changelog must contain exactly one changelog section for {version}"
        )
    start = matches[0].start()
    next_heading = content.find(b"\n## ", start + len(marker))
    return content[start:] if next_heading < 0 else content[start : next_heading + 1]


def _verify_document_identity(root: Path, version: str) -> tuple[Path, bytes, bytes]:
    notes = root / f"docs/release-notes/{version}.md"
    try:
        notes_bytes = notes.read_bytes()
    except FileNotFoundError as error:
        raise ValueError(f"release notes are missing for {version}") from error
    if not notes_bytes.startswith(f"# Release notes: {version}\n".encode()):
        raise ValueError(f"release notes identity does not match {version}")
    changelog_bytes = (root / "CHANGELOG.md").read_bytes()
    section = _changelog_section(changelog_bytes, version)
    return notes, notes_bytes, section


def freeze_manifest(
    *,
    root: Path,
    dist: Path,
    manifest_path: Path,
    requested_version: str,
    requested_tag: str,
    previous_version: str,
    latest_stable: str,
    published_versions: set[str],
    existing_tags: set[str],
    source_commit: str,
) -> dict[str, Any]:
    """Validate all local identities, hash the built files, and freeze a manifest."""

    if manifest_path.exists():
        raise ValueError(f"release manifest already exists: {manifest_path}")
    validate_published_history(
        previous=previous_version,
        requested=requested_version,
        published_versions=published_versions,
    )
    validate_candidate(
        requested_version,
        latest_stable=latest_stable,
        published_versions=published_versions,
    )
    source_version = _project_version(root)
    if source_version != requested_version:
        raise ValueError(
            f"pyproject version {source_version} does not match requested "
            f"release {requested_version}"
        )
    expected_tag = f"v{requested_version}"
    if requested_tag != expected_tag:
        raise ValueError(f"requested tag must be {expected_tag}")
    if requested_tag in existing_tags:
        raise ValueError(f"requested tag already exists: {requested_tag}")
    latest_stable_tag = f"v{latest_stable}"
    if latest_stable_tag not in existing_tags:
        raise ValueError(f"latest stable tag is missing locally: {latest_stable_tag}")
    if _GIT_COMMIT.fullmatch(source_commit) is None:
        raise ValueError("source commit must be a full lowercase Git commit ID")
    notes, notes_bytes, changelog_section = _verify_document_identity(
        root, requested_version
    )
    artifacts = _verify_artifacts(dist, requested_version)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "project": _PROJECT,
        "previous_version": previous_version,
        "version": requested_version,
        "tag": requested_tag,
        "release_notes": notes.relative_to(root).as_posix(),
        "release_notes_sha256": _sha256_bytes(notes_bytes),
        "changelog_section_sha256": _sha256_bytes(changelog_section),
        "source_commit": source_commit,
        "artifacts": [
            {"filename": artifact.name, "sha256": _sha256(artifact)}
            for artifact in artifacts
        ],
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest


def verify_manifest(*, root: Path, dist: Path, manifest_path: Path) -> None:
    """Verify that source evidence and local artifacts still match a frozen manifest."""

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("release manifest must be a JSON object")
    version, expected = _validate_manifest_payload(manifest)
    if _project_version(root) != version:
        raise ValueError("release manifest and pyproject identity mismatch")
    notes, notes_bytes, changelog_section = _verify_document_identity(root, version)
    if manifest.get("release_notes") != notes.relative_to(root).as_posix():
        raise ValueError("release manifest notes path mismatch")
    if manifest.get("release_notes_sha256") != _sha256_bytes(notes_bytes):
        raise ValueError("release notes changed after manifest freeze")
    if manifest.get("changelog_section_sha256") != _sha256_bytes(changelog_section):
        raise ValueError("changelog section changed after manifest freeze")
    artifacts = _verify_artifacts(dist, version)
    actual = {artifact.name: _sha256(artifact) for artifact in artifacts}
    if expected != actual:
        raise ValueError("artifacts changed after manifest freeze")


def _read_json(url: str, *, opener: _Opener) -> dict[str, Any]:
    with opener(url, timeout=10.0) as response:
        payload = json.loads(response.read())
    if not isinstance(payload, dict):
        raise ValueError("PyPI returned a non-object response")
    return payload


def fetch_published_versions(*, opener: _Opener = urllib.request.urlopen) -> set[str]:
    """Fetch published versions; callers must opt into this network operation."""

    payload = _read_json(f"{_PYPI_URL}/json", opener=opener)
    releases = payload.get("releases")
    if not isinstance(releases, dict) or not all(
        isinstance(version, str) for version in releases
    ):
        raise ValueError("PyPI response has no valid releases mapping")
    return set(releases)


def _manifest_artifact_map(value: object) -> dict[str, str]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("release manifest must contain exactly two artifact entries")
    result: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict) or set(item) != {"filename", "sha256"}:
            raise ValueError("manifest artifact entry must contain filename and sha256")
        filename = item["filename"]
        digest = item["sha256"]
        if not isinstance(filename, str) or not isinstance(digest, str):
            raise ValueError("manifest artifact entry values must be strings")
        if _SHA256.fullmatch(digest) is None:
            raise ValueError("manifest artifact entry has an invalid SHA-256 digest")
        if filename in result:
            raise ValueError(f"duplicate manifest artifact filename: {filename}")
        result[filename] = digest
    return result


def _validate_manifest_payload(
    manifest: Mapping[str, Any],
) -> tuple[str, dict[str, str]]:
    required = {
        "schema_version",
        "project",
        "previous_version",
        "version",
        "tag",
        "release_notes",
        "release_notes_sha256",
        "changelog_section_sha256",
        "source_commit",
        "artifacts",
    }
    if set(manifest) != required or manifest.get("schema_version") != 1:
        raise ValueError("release manifest must match schema version 1 exactly")
    if manifest.get("project") != _PROJECT:
        raise ValueError(f"release manifest project must be {_PROJECT}")
    version = manifest.get("version")
    previous = manifest.get("previous_version")
    if not isinstance(version, str) or not isinstance(previous, str):
        raise ValueError("release manifest lifecycle versions must be strings")
    ReleaseVersion.parse(version)
    validate_transition(previous, version)
    if manifest.get("tag") != f"v{version}":
        raise ValueError("release manifest version and tag identity mismatch")
    if manifest.get("release_notes") != f"docs/release-notes/{version}.md":
        raise ValueError("release manifest notes path mismatch")
    for field in ("release_notes_sha256", "changelog_section_sha256"):
        digest = manifest.get(field)
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise ValueError(f"release manifest {field} is not a SHA-256 digest")
    source_commit = manifest.get("source_commit")
    if (
        not isinstance(source_commit, str)
        or _GIT_COMMIT.fullmatch(source_commit) is None
    ):
        raise ValueError("release manifest source_commit is not a full commit ID")
    artifacts = _manifest_artifact_map(manifest.get("artifacts"))
    normalized = version.replace("-", "_")
    expected_names = {
        f"polis_nlp-{normalized}-py3-none-any.whl",
        f"polis_nlp-{version}.tar.gz",
    }
    if set(artifacts) != expected_names:
        raise ValueError("release manifest artifact filenames mismatch its version")
    return version, artifacts


def _published_artifact_map(value: object) -> dict[str, str]:
    if not isinstance(value, list):
        raise ValueError("PyPI release response has no artifact list")
    result: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("published artifact entry must be an object")
        filename = item.get("filename")
        digests = item.get("digests")
        digest = digests.get("sha256") if isinstance(digests, dict) else None
        if (
            not isinstance(filename, str)
            or not isinstance(digest, str)
            or _SHA256.fullmatch(digest) is None
        ):
            raise ValueError("published artifact entry has invalid identity fields")
        if filename in result:
            raise ValueError(f"duplicate published artifact filename: {filename}")
        result[filename] = digest
    return result


def verify_published_digests(
    manifest: Mapping[str, Any],
    *,
    version: str,
    opener: _Opener = urllib.request.urlopen,
) -> None:
    """Compare PyPI filenames and SHA-256 digests with the frozen manifest."""

    manifest_version, expected = _validate_manifest_payload(manifest)
    if version != manifest_version:
        raise ValueError("requested publication version differs from manifest")
    payload = _read_json(f"{_PYPI_URL}/{version}/json", opener=opener)
    published = _published_artifact_map(payload.get("urls"))
    if published != expected:
        raise ValueError("published artifact names and digests do not match manifest")


def _git_show(root: Path, revision_path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", revision_path],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"cannot read immutable evidence {revision_path}")
    return result.stdout


def _git_output(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError(f"git {' '.join(arguments)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def list_local_tags(root: Path) -> set[str]:
    """Return the exact local tag names used for release preflight."""

    output = _git_output(root, "tag", "--list")
    return set(output.splitlines()) if output else set()


def current_commit(root: Path) -> str:
    """Return the commit whose source is being built for the release."""

    commit = _git_output(root, "rev-parse", "HEAD")
    if _GIT_COMMIT.fullmatch(commit) is None:
        raise ValueError("HEAD is not a full lowercase Git commit ID")
    return commit


def require_clean_worktree(root: Path) -> None:
    """Reject source/evidence bytes that are not represented by the release commit."""

    status = _git_output(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise ValueError("release worktree must be clean before building:\n" + status)


def verify_tagged_evidence(
    root: Path, tag: str, *, manifest: Mapping[str, Any] | None = None
) -> None:
    """Require historical notes and changelog section to match a local release tag."""

    if not tag.startswith("v"):
        raise ValueError("historical tag must use v<version>")
    version = tag[1:]
    parsed = ReleaseVersion.parse(version)
    if parsed.stage == "dev":
        raise ValueError("historical evidence checks require an rc or stable tag")
    tagged_pyproject = _git_show(root, f"{tag}:pyproject.toml")
    try:
        tagged_version = _project_version_from_text(tagged_pyproject.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise ValueError(f"cannot read tagged pyproject version from {tag}") from error
    if tagged_version != version:
        raise ValueError(
            f"tagged pyproject version {tagged_version} does not match {tag}"
        )
    notes_path = f"docs/release-notes/{version}.md"
    tagged_notes = _git_show(root, f"{tag}:{notes_path}")
    if (root / notes_path).read_bytes() != tagged_notes:
        raise ValueError(f"release notes for {version} differ from {tag}")
    tagged_changelog = _git_show(root, f"{tag}:CHANGELOG.md")
    current_changelog = (root / "CHANGELOG.md").read_bytes()
    if _changelog_section(current_changelog, version) != _changelog_section(
        tagged_changelog, version
    ):
        raise ValueError(f"changelog section for {version} differs from {tag}")
    if manifest is not None:
        manifest_version, _ = _validate_manifest_payload(manifest)
        if manifest_version != version or manifest.get("tag") != tag:
            raise ValueError("tag and release manifest identity mismatch")
        tag_commit = _git_output(root, "rev-parse", f"{tag}^{{commit}}")
        if manifest.get("source_commit") != tag_commit:
            raise ValueError("tag commit differs from release manifest source commit")
        if manifest.get("release_notes_sha256") != _sha256_bytes(tagged_notes):
            raise ValueError("tagged release notes digest differs from manifest")
        tagged_section = _changelog_section(tagged_changelog, version)
        if manifest.get("changelog_section_sha256") != _sha256_bytes(tagged_section):
            raise ValueError("tagged changelog section digest differs from manifest")


def _load_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("release manifest must be a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    freeze = subparsers.add_parser("freeze", help="freeze local release evidence")
    freeze.add_argument("--root", type=Path, default=Path("."))
    freeze.add_argument("--dist", type=Path, default=Path("dist"))
    freeze.add_argument("--manifest", type=Path, required=True)
    freeze.add_argument("--version", required=True)
    freeze.add_argument("--tag", required=True)
    freeze.add_argument("--previous-version", required=True)
    freeze.add_argument("--latest-stable", required=True)
    freeze.add_argument("--check-pypi", action="store_true", required=True)

    verify = subparsers.add_parser("verify", help="verify frozen local evidence")
    verify.add_argument("--root", type=Path, default=Path("."))
    verify.add_argument("--dist", type=Path, default=Path("dist"))
    verify.add_argument("--manifest", type=Path, required=True)

    published = subparsers.add_parser(
        "verify-published", help="verify the published PyPI digests"
    )
    published.add_argument("--manifest", type=Path, required=True)

    historical = subparsers.add_parser(
        "verify-tagged", help="verify immutable historical release evidence"
    )
    historical.add_argument("--root", type=Path, default=Path("."))
    historical.add_argument("--tag", action="append", required=True)
    historical.add_argument("--manifest", type=Path)

    args = parser.parse_args()
    if args.command == "freeze":
        root = args.root.resolve()
        require_clean_worktree(root)
        published_versions = fetch_published_versions()
        freeze_manifest(
            root=root,
            dist=args.dist.resolve(),
            manifest_path=args.manifest.resolve(),
            requested_version=args.version,
            requested_tag=args.tag,
            previous_version=args.previous_version,
            latest_stable=args.latest_stable,
            published_versions=published_versions,
            existing_tags=list_local_tags(root),
            source_commit=current_commit(root),
        )
    elif args.command == "verify":
        verify_manifest(
            root=args.root.resolve(),
            dist=args.dist.resolve(),
            manifest_path=args.manifest.resolve(),
        )
    elif args.command == "verify-published":
        manifest = _load_manifest(args.manifest)
        version = manifest.get("version")
        if not isinstance(version, str):
            raise ValueError("release manifest has no version")
        verify_published_digests(manifest, version=version)
    else:
        historical_manifest = _load_manifest(args.manifest) if args.manifest else None
        if historical_manifest is not None and len(args.tag) != 1:
            raise ValueError("--manifest requires exactly one --tag")
        for tag in args.tag:
            verify_tagged_evidence(
                args.root.resolve(), tag, manifest=historical_manifest
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
