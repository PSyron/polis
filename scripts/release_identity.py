"""Verify one immutable identity across a Polis release and its evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
import tomllib
import zipfile
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from packaging.version import InvalidVersion, Version

_COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_RELEASE_LINE_RE = re.compile(r"\d+\.\d+\.\d+(?:\.dev\d+|rc\d+)?\Z")


class ReleaseIdentityError(ValueError):
    """Raised when release metadata, artifacts, or evidence disagree."""


@dataclass(frozen=True)
class ReleaseObservations:
    """Release-only observations collected from explicit external authorities."""

    local_tags: tuple[str, ...]
    remote_tags: tuple[str, ...]
    github_releases: tuple[str, ...]
    package_index_versions: tuple[str, ...]


def release_tag(version: str) -> str:
    """Return the exact tag name for one canonical public PEP 440 version."""
    try:
        parsed = Version(version)
    except InvalidVersion as error:
        raise ReleaseIdentityError("version is not canonical public PEP 440") from error
    if (
        str(parsed) != version
        or parsed.local is not None
        or not _RELEASE_LINE_RE.fullmatch(version)
    ):
        raise ReleaseIdentityError("version is not canonical public PEP 440")
    return f"v{parsed}"


@dataclass(frozen=True)
class ReleaseIdentity:
    """The version, tag, and immutable source commit for one release."""

    version: Version
    tag: str
    source_commit: str

    @classmethod
    def create(cls, *, version: str, source_commit: str) -> ReleaseIdentity:
        """Build a validated identity from canonical release inputs."""
        tag = release_tag(version)
        if not _COMMIT_RE.fullmatch(source_commit):
            raise ReleaseIdentityError(
                "source commit must be a 40-character lowercase SHA"
            )
        return cls(Version(version), tag, source_commit)


@dataclass(frozen=True)
class ArtifactDigest:
    """The immutable filename and SHA-256 of one release artifact."""

    filename: str
    sha256: str

    def __post_init__(self) -> None:
        if not _SHA256_RE.fullmatch(self.sha256):
            raise ReleaseIdentityError("artifact digest must be a lowercase SHA-256")


@dataclass(frozen=True)
class ReleaseManifest:
    """One build-once artifact set bound to one release identity."""

    identity: ReleaseIdentity
    artifacts: tuple[ArtifactDigest, ...]

    def __post_init__(self) -> None:
        if len(self.artifacts) != 2:
            raise ReleaseIdentityError(
                "release manifest requires one wheel and one sdist"
            )
        if len({artifact.filename for artifact in self.artifacts}) != len(
            self.artifacts
        ):
            raise ReleaseIdentityError("release manifest artifact names must be unique")

    def to_json(self) -> str:
        """Return deterministic JSON suitable for an append-only release record."""
        return (
            json.dumps(
                {
                    "artifacts": [
                        {"filename": item.filename, "sha256": item.sha256}
                        for item in self.artifacts
                    ],
                    "source_commit": self.identity.source_commit,
                    "tag": self.identity.tag,
                    "version": str(self.identity.version),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

    @classmethod
    def from_json(cls, raw: str) -> ReleaseManifest:
        """Decode one strict manifest without accepting unknown fields."""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ReleaseIdentityError("release manifest is not valid JSON") from error
        if not isinstance(payload, dict) or set(payload) != {
            "artifacts",
            "source_commit",
            "tag",
            "version",
        }:
            raise ReleaseIdentityError("release manifest has an invalid schema")
        version = payload["version"]
        source_commit = payload["source_commit"]
        tag = payload["tag"]
        artifacts = payload["artifacts"]
        if not isinstance(version, str) or not isinstance(source_commit, str):
            raise ReleaseIdentityError(
                "release manifest identity values must be strings"
            )
        identity = ReleaseIdentity.create(version=version, source_commit=source_commit)
        if tag != identity.tag:
            raise ReleaseIdentityError(
                "release manifest tag does not match its version"
            )
        if not isinstance(artifacts, list):
            raise ReleaseIdentityError("release manifest artifacts must be a list")
        parsed_artifacts: list[ArtifactDigest] = []
        for item in artifacts:
            if not isinstance(item, dict) or set(item) != {"filename", "sha256"}:
                raise ReleaseIdentityError(
                    "release manifest artifact has an invalid schema"
                )
            filename = item["filename"]
            sha256 = item["sha256"]
            if not isinstance(filename, str) or not isinstance(sha256, str):
                raise ReleaseIdentityError(
                    "release manifest artifact values must be strings"
                )
            parsed_artifacts.append(ArtifactDigest(filename, sha256))
        return cls(identity, tuple(parsed_artifacts))

    def verify_artifacts(self, dist: Path) -> None:
        """Require the artifact directory to be the exact manifest artifact set."""
        actual = _artifact_paths(dist)
        expected_names = {artifact.filename for artifact in self.artifacts}
        if {path.name for path in actual} != expected_names:
            raise ReleaseIdentityError(
                "artifact names differ from the release manifest"
            )
        for artifact in self.artifacts:
            digest = _sha256(dist / artifact.filename)
            if digest != artifact.sha256:
                raise ReleaseIdentityError(
                    "artifact digest differs from the release manifest: "
                    f"{artifact.filename}"
                )


def require_new_candidate(
    identity: ReleaseIdentity,
    *,
    latest_published: str,
    local_tags: Iterable[str],
    remote_tags: Iterable[str],
    github_releases: Iterable[str],
    package_index_versions: Iterable[str],
) -> None:
    """Reject any candidate that has already been published or named locally."""
    github_tags = tuple(github_releases)
    index_versions = tuple(package_index_versions)
    if identity.tag in set(local_tags):
        raise ReleaseIdentityError("candidate tag already exists as a local tag")
    if identity.tag in set(remote_tags):
        raise ReleaseIdentityError("candidate tag already exists as a remote tag")
    if identity.tag in set(github_tags):
        raise ReleaseIdentityError("candidate tag already has a GitHub release")
    if identity.version in {
        _parse_publication_version(version) for version in index_versions
    }:
        raise ReleaseIdentityError(
            "candidate version already exists on the configured package index"
        )
    observed_versions = [_parse_publication_version(latest_published)]
    observed_versions.extend(
        _parse_publication_version(version) for version in index_versions
    )
    observed_versions.extend(_parse_release_tag_version(tag) for tag in github_tags)
    if identity.version <= max(observed_versions):
        raise ReleaseIdentityError(
            "candidate version is not greater than latest publication"
        )


def collect_release_observations(
    *,
    remote: str,
    github_repo: str,
    package_index_url: str,
    run: Callable[..., subprocess.CompletedProcess[bytes]] = subprocess.run,
    open_url: Callable[..., Any] = urlopen,
) -> ReleaseObservations:
    """Collect candidate-uniqueness observations for an explicit release step.

    This function is never called by fast CI. Its command and HTTP boundaries
    are injectable so fast tests exercise the parsing and failure behavior
    without contacting a remote service.
    """
    local_tags = _command_lines(run, ["git", "tag", "--list"])
    remote_output = _command_lines(run, ["git", "ls-remote", "--tags", remote])
    remote_tags = tuple(
        line.rsplit("/", maxsplit=1)[-1]
        for line in remote_output
        if "refs/tags/" in line
    )
    github_releases = _command_lines(
        run,
        [
            "gh",
            "api",
            f"repos/{github_repo}/releases",
            "--paginate",
            "--jq",
            ".[].tag_name",
        ],
    )
    request = Request(package_index_url, headers={"Accept": "application/json"})
    try:
        with open_url(request, timeout=10.0) as response:
            raw = response.read()
    except OSError as error:
        raise ReleaseIdentityError("cannot query configured package index") from error
    if not isinstance(raw, bytes):
        raise ReleaseIdentityError("configured package index returned non-byte data")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ReleaseIdentityError(
            "configured package index returned invalid JSON"
        ) from error
    if not isinstance(payload, dict) or not isinstance(payload.get("releases"), dict):
        raise ReleaseIdentityError(
            "configured package index returned an invalid schema"
        )
    versions = payload["releases"]
    if not all(isinstance(version, str) for version in versions):
        raise ReleaseIdentityError("configured package index returned invalid versions")
    return ReleaseObservations(
        local_tags=tuple(local_tags),
        remote_tags=remote_tags,
        github_releases=tuple(github_releases),
        package_index_versions=tuple(versions),
    )


def create_manifest(
    identity: ReleaseIdentity,
    dist: Path,
    *,
    artifacts: tuple[Path, Path] | None = None,
) -> ReleaseManifest:
    """Create a manifest from exactly one version-matching wheel and sdist."""
    paths = artifacts if artifacts is not None else _artifact_paths(dist)
    _require_artifact_names(identity, paths)
    for path in paths:
        if artifact_metadata_version(path) != identity.version:
            raise ReleaseIdentityError(
                "artifact metadata version does not match release version"
            )
    return ReleaseManifest(
        identity,
        tuple(ArtifactDigest(path.name, _sha256(path)) for path in paths),
    )


def require_tagged_evidence(
    *,
    current_note: bytes,
    tagged_note: bytes,
    current_changelog_section: bytes,
    tagged_changelog_section: bytes,
) -> None:
    """Require historical release note and changelog bytes to remain unchanged."""
    if current_note != tagged_note:
        raise ReleaseIdentityError("release note differs from its tagged evidence")
    if current_changelog_section != tagged_changelog_section:
        raise ReleaseIdentityError("changelog section differs from its tagged evidence")


def require_published_digests(
    manifest: ReleaseManifest, published_digests: dict[str, str]
) -> None:
    """Require published assets to have the exact names and hashes in a manifest."""
    expected = {item.filename: item.sha256 for item in manifest.artifacts}
    if published_digests != expected:
        raise ReleaseIdentityError(
            "published digest set differs from the release manifest"
        )


def read_project_version(pyproject: Path) -> str:
    """Read the authoritative project version from one pyproject file."""
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ReleaseIdentityError("cannot read project metadata") from error
    project = data.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("version"), str):
        raise ReleaseIdentityError("project metadata does not declare a version")
    version: object = project["version"]
    if not isinstance(version, str):
        raise ReleaseIdentityError("project metadata does not declare a version")
    release_tag(version)
    return version


def changelog_section(changelog: bytes, version: str) -> bytes:
    """Return exactly one raw changelog section for a published version."""
    prefix = f"## {version}".encode()
    lines = changelog.splitlines(keepends=True)
    matches = [
        index
        for index, line in enumerate(lines)
        if line.startswith(prefix)
        and (
            len(line) == len(prefix)
            or line[len(prefix) : len(prefix) + 1] in (b" ", b"\r", b"\n")
        )
    ]
    if len(matches) != 1:
        raise ReleaseIdentityError(
            f"changelog must contain exactly one section for version {version}"
        )
    start = matches[0]
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith(b"## ")
        ),
        len(lines),
    )
    return b"".join(lines[start:end])


def artifact_metadata_version(artifact: Path) -> Version:
    """Read and validate the exact version embedded in a wheel or source archive."""
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact) as archive:
            metadata_name = next(
                (
                    name
                    for name in archive.namelist()
                    if name.endswith(".dist-info/METADATA")
                ),
                None,
            )
            if metadata_name is None:
                raise ReleaseIdentityError("wheel does not contain package metadata")
            metadata = archive.read(metadata_name)
    elif artifact.name.endswith(".tar.gz"):
        with tarfile.open(artifact) as archive:
            metadata_member = next(
                (
                    member
                    for member in archive.getmembers()
                    if member.name.endswith("/PKG-INFO")
                ),
                None,
            )
            if metadata_member is None:
                raise ReleaseIdentityError("sdist does not contain package metadata")
            source = archive.extractfile(metadata_member)
            if source is None:
                raise ReleaseIdentityError("cannot read sdist package metadata")
            metadata = source.read()
    else:
        raise ReleaseIdentityError("unsupported release artifact type")
    version: object = BytesParser().parsebytes(metadata)["Version"]
    if not isinstance(version, str):
        raise ReleaseIdentityError("artifact metadata does not declare a version")
    release_tag(version)
    return Version(version)


def verify_repository_tagged_evidence(repo: Path, *, tag: str, version: str) -> None:
    """Verify one checked-out historical note and changelog section against its tag."""
    release_tag(version)
    if tag != f"v{version}":
        raise ReleaseIdentityError("tag does not match the release version")
    note_relative = Path("docs/release-notes") / f"{version}.md"
    note = repo / note_relative
    changelog = repo / "CHANGELOG.md"
    try:
        current_note = note.read_bytes()
        current_changelog = changelog.read_bytes()
    except OSError as error:
        raise ReleaseIdentityError(
            "checked-out release evidence is unavailable"
        ) from error
    tagged_note = _git_show_bytes(repo, tag, note_relative)
    tagged_changelog = _git_show_bytes(repo, tag, Path("CHANGELOG.md"))
    require_tagged_evidence(
        current_note=current_note,
        tagged_note=tagged_note,
        current_changelog_section=changelog_section(current_changelog, version),
        tagged_changelog_section=changelog_section(tagged_changelog, version),
    )


def verify_all_tagged_evidence(repo: Path) -> None:
    """Verify every canonical release tag that has checked-in release evidence."""
    tags = _command_lines(
        subprocess.run,
        ["git", "tag", "--list", "v*"],
        cwd=repo,
    )
    for tag in tags:
        version = tag.removeprefix("v")
        try:
            release_tag(version)
        except ReleaseIdentityError:
            continue
        note = repo / "docs" / "release-notes" / f"{version}.md"
        if not note.is_file():
            raise ReleaseIdentityError(
                f"tagged release evidence is unavailable: {note.relative_to(repo)}"
            )
        verify_repository_tagged_evidence(repo, tag=tag, version=version)


def verify_release_identity(
    identity: ReleaseIdentity,
    *,
    repo: Path,
    pyproject: Path,
) -> None:
    """Bind source metadata, tag, release note, and changelog to one version."""
    version = str(identity.version)
    if read_project_version(pyproject) != version:
        raise ReleaseIdentityError(
            "project metadata version does not match release identity"
        )
    note = repo / "docs" / "release-notes" / f"{version}.md"
    try:
        note_bytes = note.read_bytes()
        changelog = (repo / "CHANGELOG.md").read_bytes()
    except OSError as error:
        raise ReleaseIdentityError(
            "release identity evidence is unavailable"
        ) from error
    if note_bytes.splitlines()[0:1] != [f"# Polis {version}".encode()]:
        raise ReleaseIdentityError(
            "release note heading does not match release identity"
        )
    section = changelog_section(changelog, version)
    heading = section.splitlines()[0:1]
    expected_heading = f"## {version}".encode()
    if heading != [expected_heading] and not re.fullmatch(
        re.escape(expected_heading) + rb" \(\d{4}-\d{2}-\d{2}\)",
        heading[0] if heading else b"",
    ):
        raise ReleaseIdentityError("changelog heading does not match release identity")
    _require_source_commit(repo, identity.source_commit)


def verify_tag_binding(repo: Path, identity: ReleaseIdentity) -> None:
    """Require an existing exact release tag to resolve to the identity commit."""
    _require_source_commit(repo, identity.source_commit)
    completed = subprocess.run(
        ["git", "rev-parse", f"{identity.tag}^{{commit}}"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ReleaseIdentityError("release identity tag does not exist")
    if completed.stdout.decode("utf-8").strip() != identity.source_commit:
        raise ReleaseIdentityError("release tag is not bound to the source commit")


def _require_source_commit(repo: Path, source_commit: str) -> None:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{source_commit}^{{commit}}"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ReleaseIdentityError("release identity source commit does not exist")


def _parse_publication_version(value: str) -> Version:
    try:
        return Version(value)
    except InvalidVersion as error:
        raise ReleaseIdentityError("published version is invalid") from error


def _parse_release_tag_version(tag: str) -> Version:
    if not tag.startswith("v"):
        raise ReleaseIdentityError("GitHub release tag is not canonical")
    version = tag.removeprefix("v")
    release_tag(version)
    return Version(version)


def _artifact_paths(dist: Path) -> tuple[Path, Path]:
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ReleaseIdentityError("dist must contain exactly one wheel and one sdist")
    return wheels[0], sdists[0]


def _command_lines(
    run: Callable[..., subprocess.CompletedProcess[bytes]],
    command: list[str],
    *,
    cwd: Path | None = None,
) -> tuple[str, ...]:
    completed = run(command, cwd=cwd, check=False, capture_output=True)
    if completed.returncode != 0:
        raise ReleaseIdentityError(
            f"release-only observation command failed: {' '.join(command[:2])}"
        )
    try:
        output = completed.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReleaseIdentityError(
            "release-only observation command returned invalid UTF-8"
        ) from error
    return tuple(line.strip() for line in output.splitlines() if line.strip())


def _require_artifact_names(
    identity: ReleaseIdentity, paths: tuple[Path, Path]
) -> None:
    wheel, sdist = paths
    version = str(identity.version)
    if not wheel.name.startswith(f"polis_nlp-{version}-") or wheel.suffix != ".whl":
        raise ReleaseIdentityError("artifact name does not match release version")
    if sdist.name != f"polis_nlp-{version}.tar.gz":
        raise ReleaseIdentityError("artifact name does not match release version")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_show_bytes(repo: Path, tag: str, relative_path: Path) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{tag}:{relative_path.as_posix()}"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ReleaseIdentityError(
            f"tagged release evidence is unavailable: {relative_path.as_posix()}"
        )
    return completed.stdout


def main(argv: Sequence[str] | None = None) -> int:
    """Run explicit offline release-identity checks without uploading artifacts."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    candidate = commands.add_parser("candidate", help="verify a new candidate name")
    candidate.add_argument("--version", required=True)
    candidate.add_argument("--source-commit", required=True)
    candidate.add_argument("--latest-published", required=True)
    candidate.add_argument("--repo", type=Path, default=Path("."))
    candidate.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    candidate.add_argument("--release-only", action="store_true")
    candidate.add_argument("--remote", default="origin")
    candidate.add_argument("--github-repo")
    candidate.add_argument("--package-index-url")
    candidate.add_argument("--local-tag", action="append", default=[])
    candidate.add_argument("--remote-tag", action="append", default=[])
    candidate.add_argument("--github-release", action="append", default=[])
    candidate.add_argument("--package-index-version", action="append", default=[])

    manifest = commands.add_parser(
        "manifest", help="record one build-once artifact set"
    )
    manifest.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    manifest.add_argument("--repo", type=Path, default=Path("."))
    manifest.add_argument("--source-commit", required=True)
    manifest.add_argument("--dist", type=Path, default=Path("dist"))
    manifest.add_argument("--output", type=Path, required=True)

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
        verify_release_identity(identity, repo=args.repo, pyproject=args.pyproject)
        if args.release_only:
            if args.github_repo is None or args.package_index_url is None:
                raise ReleaseIdentityError(
                    "release-only candidate checks require GitHub and "
                    "package-index settings"
                )
            observations = collect_release_observations(
                remote=args.remote,
                github_repo=args.github_repo,
                package_index_url=args.package_index_url,
            )
            local_tags = observations.local_tags
            remote_tags = observations.remote_tags
            github_releases = observations.github_releases
            package_index_versions = observations.package_index_versions
        else:
            local_tags = args.local_tag
            remote_tags = args.remote_tag
            github_releases = args.github_release
            package_index_versions = args.package_index_version
        require_new_candidate(
            identity,
            latest_published=args.latest_published,
            local_tags=local_tags,
            remote_tags=remote_tags,
            github_releases=github_releases,
            package_index_versions=package_index_versions,
        )
        print(f"candidate identity is available: {identity.tag}")
        return 0
    if args.command == "manifest":
        identity = ReleaseIdentity.create(
            version=read_project_version(args.pyproject),
            source_commit=args.source_commit,
        )
        _require_source_commit(args.repo, identity.source_commit)
        release_manifest = create_manifest(identity, args.dist)
        args.output.write_text(release_manifest.to_json(), encoding="utf-8")
        print(f"recorded build-once manifest: {args.output}")
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
        release_manifest = ReleaseManifest.from_json(
            args.manifest.read_text(encoding="utf-8")
        )
        try:
            raw_digests = json.loads(args.published_digests.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ReleaseIdentityError(
                "published digest file is not valid JSON"
            ) from error
        if not isinstance(raw_digests, dict) or not all(
            isinstance(name, str) and isinstance(digest, str)
            for name, digest in raw_digests.items()
        ):
            raise ReleaseIdentityError(
                "published digest file must map artifact names to hashes"
            )
        require_published_digests(release_manifest, raw_digests)
        print(f"published digests match: {args.manifest}")
        return 0
    raise AssertionError(f"unsupported release identity command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseIdentityError as error:
        raise SystemExit(f"release identity check failed: {error}") from error
