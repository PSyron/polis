from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from packaging.version import InvalidVersion, Version

COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
RELEASE_LINE_RE = re.compile(r"\d+\.\d+\.\d+(?:\.dev\d+|rc\d+)?\Z")


class ReleaseIdentityError(ValueError):
    pass


def release_tag(version: str) -> str:
    try:
        parsed = Version(version)
    except InvalidVersion as error:
        raise ReleaseIdentityError("version is not canonical public PEP 440") from error
    if (
        str(parsed) != version
        or parsed.local is not None
        or not RELEASE_LINE_RE.fullmatch(version)
    ):
        raise ReleaseIdentityError("version is not canonical public PEP 440")
    return f"v{parsed}"


@dataclass(frozen=True)
class ReleaseIdentity:
    version: Version
    tag: str
    source_commit: str

    @classmethod
    def create(cls, *, version: str, source_commit: str) -> ReleaseIdentity:
        tag = release_tag(version)
        if not COMMIT_RE.fullmatch(source_commit):
            raise ReleaseIdentityError(
                "source commit must be a 40-character lowercase SHA"
            )
        return cls(Version(version), tag, source_commit)


@dataclass(frozen=True)
class ArtifactDigest:
    filename: str
    size: int
    sha256: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.size, int)
            or isinstance(self.size, bool)
            or self.size < 1
        ):
            raise ReleaseIdentityError("artifact size must be a positive integer")
        if not SHA256_RE.fullmatch(self.sha256):
            raise ReleaseIdentityError("artifact digest must be a lowercase SHA-256")


@dataclass(frozen=True)
class TagBinding:
    exists: bool
    annotated: bool
    source_commit: str | None


@dataclass(frozen=True)
class ReleaseObservations:
    local_tag: TagBinding
    remote_tag: TagBinding
    github_releases: tuple[str, ...]
    package_index_is_absent: bool


@dataclass(frozen=True)
class ReleasePolicy:
    approved_plan_sha256: str


@dataclass(frozen=True)
class ReleaseManifest:
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
        return (
            json.dumps(
                {
                    "schema_version": 1,
                    "artifacts": [
                        {
                            "filename": item.filename,
                            "sha256": item.sha256,
                            "size": item.size,
                        }
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

    def verify_artifacts(self, dist: Path) -> None:
        from scripts.release_identity_artifacts import verify_manifest_artifacts

        verify_manifest_artifacts(self, dist)

    @classmethod
    def from_json(cls, raw: str) -> ReleaseManifest:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ReleaseIdentityError("release manifest is not valid JSON") from error
        if not isinstance(payload, dict) or set(payload) != {
            "artifacts",
            "schema_version",
            "source_commit",
            "tag",
            "version",
        }:
            raise ReleaseIdentityError("release manifest has an invalid schema")
        version = payload["version"]
        source_commit = payload["source_commit"]
        tag = payload["tag"]
        artifacts = payload["artifacts"]
        if payload["schema_version"] != 1 or isinstance(
            payload["schema_version"], bool
        ):
            raise ReleaseIdentityError("release manifest schema version is invalid")
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
        parsed: list[ArtifactDigest] = []
        for item in artifacts:
            if not isinstance(item, dict) or set(item) != {
                "filename",
                "sha256",
                "size",
            }:
                raise ReleaseIdentityError(
                    "release manifest artifact has an invalid schema"
                )
            filename = item["filename"]
            size = item["size"]
            sha256 = item["sha256"]
            if (
                not isinstance(filename, str)
                or not isinstance(size, int)
                or isinstance(size, bool)
                or not isinstance(sha256, str)
            ):
                raise ReleaseIdentityError(
                    "release manifest artifact values must be strings"
                )
            parsed.append(ArtifactDigest(filename, size, sha256))
        return cls(identity, tuple(parsed))
