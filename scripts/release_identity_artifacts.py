from __future__ import annotations

import hashlib
import json
import tarfile
import zipfile
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path

from packaging.utils import canonicalize_name
from packaging.version import Version
from scripts.release_identity_models import (
    ArtifactDigest,
    ReleaseIdentity,
    ReleaseIdentityError,
    ReleaseManifest,
    release_tag,
)

_PACKAGE_NAME = "polis-nlp"


@dataclass(frozen=True)
class ArtifactMetadata:
    name: str
    version: Version


def create_manifest(
    identity: ReleaseIdentity,
    dist: Path,
    *,
    artifacts: tuple[Path, Path] | None = None,
) -> ReleaseManifest:
    paths = artifacts if artifacts is not None else artifact_paths(dist)
    require_artifact_names(identity, paths)
    for path in paths:
        if artifact_metadata(path).version != identity.version:
            raise ReleaseIdentityError(
                "artifact metadata version does not match release version"
            )
    return ReleaseManifest(
        identity,
        tuple(
            ArtifactDigest(path.name, path.stat().st_size, sha256(path))
            for path in paths
        ),
    )


def verify_manifest_artifacts(manifest: ReleaseManifest, dist: Path) -> None:
    actual = artifact_paths(dist)
    require_artifact_names(manifest.identity, actual)
    expected_names = {artifact.filename for artifact in manifest.artifacts}
    if {path.name for path in actual} != expected_names:
        raise ReleaseIdentityError("artifact names differ from the release manifest")
    for artifact in manifest.artifacts:
        path = dist / artifact.filename
        if artifact_metadata(path).version != manifest.identity.version:
            raise ReleaseIdentityError(
                "artifact metadata version differs from the release manifest: "
                f"{artifact.filename}"
            )
        if path.stat().st_size != artifact.size:
            raise ReleaseIdentityError(
                f"artifact size differs from the release manifest: {artifact.filename}"
            )
        if sha256(path) != artifact.sha256:
            raise ReleaseIdentityError(
                "artifact digest differs from the release manifest: "
                f"{artifact.filename}"
            )


def require_published_digests(
    manifest: ReleaseManifest, published_digests: dict[str, str]
) -> None:
    expected = {item.filename: item.sha256 for item in manifest.artifacts}
    if published_digests != expected:
        raise ReleaseIdentityError(
            "published digest set differs from the release manifest"
        )


def verify_published(manifest_path: Path, digests_path: Path) -> None:
    manifest = ReleaseManifest.from_json(manifest_path.read_text(encoding="utf-8"))
    try:
        raw_digests = json.loads(digests_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ReleaseIdentityError("published digest file is not valid JSON") from error
    if not isinstance(raw_digests, dict) or not all(
        isinstance(name, str) and isinstance(digest, str)
        for name, digest in raw_digests.items()
    ):
        raise ReleaseIdentityError(
            "published digest file must map artifact names to hashes"
        )
    require_published_digests(manifest, raw_digests)
    print(f"published digests match: {manifest_path}")


def artifact_metadata_version(artifact: Path) -> Version:
    return artifact_metadata(artifact).version


def artifact_metadata(artifact: Path) -> ArtifactMetadata:
    fields = BytesParser().parsebytes(read_metadata_bytes(artifact))
    name = fields["Name"]
    version = fields["Version"]
    if not isinstance(name, str) or canonicalize_name(name) != _PACKAGE_NAME:
        raise ReleaseIdentityError("artifact metadata name does not identify polis-nlp")
    if not isinstance(version, str):
        raise ReleaseIdentityError("artifact metadata does not declare a version")
    release_tag(version)
    return ArtifactMetadata(name, Version(version))


def read_metadata_bytes(artifact: Path) -> bytes:
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact) as archive:
            metadata_names = [
                name
                for name in archive.namelist()
                if name.endswith(".dist-info/METADATA")
            ]
            wheel_parts = artifact.name.removesuffix(".whl").split("-")
            expected = (
                f"{wheel_parts[0]}-{wheel_parts[1]}.dist-info/METADATA"
                if len(wheel_parts) >= 2
                else ""
            )
            if metadata_names != [expected]:
                raise ReleaseIdentityError(
                    "wheel must contain exactly one canonical package metadata record"
                )
            return archive.read(expected)
    if artifact.name.endswith(".tar.gz"):
        with tarfile.open(artifact) as archive:
            metadata_members = [
                member
                for member in archive.getmembers()
                if member.name.endswith("/PKG-INFO")
            ]
            expected = f"{artifact.name.removesuffix('.tar.gz')}/PKG-INFO"
            if [member.name for member in metadata_members] != [expected]:
                raise ReleaseIdentityError(
                    "sdist must contain exactly one canonical package metadata record"
                )
            metadata_member = metadata_members[0]
            source = archive.extractfile(metadata_member)
            if source is None:
                raise ReleaseIdentityError("cannot read sdist package metadata")
            return source.read()
    raise ReleaseIdentityError("unsupported release artifact type")


def artifact_paths(dist: Path) -> tuple[Path, Path]:
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ReleaseIdentityError("dist must contain exactly one wheel and one sdist")
    return wheels[0], sdists[0]


def require_artifact_names(identity: ReleaseIdentity, paths: tuple[Path, Path]) -> None:
    wheel, sdist = paths
    version = str(identity.version)
    if wheel.name != f"polis_nlp-{version}-py3-none-any.whl":
        raise ReleaseIdentityError("artifact name does not match release version")
    if sdist.name != f"polis_nlp-{version}.tar.gz":
        raise ReleaseIdentityError("artifact name does not match release version")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()
