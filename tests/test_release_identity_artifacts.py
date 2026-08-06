from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from scripts.release_identity import (
    ArtifactDigest,
    ReleaseIdentity,
    ReleaseIdentityError,
    ReleaseManifest,
    artifact_metadata_version,
    create_manifest,
    require_published_digests,
)
from tests.release_identity_helpers import _identity, _write_metadata_artifacts


def test_manifest_binds_one_exact_artifact_set_and_round_trips(tmp_path: Path) -> None:
    identity = _identity()
    wheel, sdist = _write_metadata_artifacts(tmp_path, str(identity.version))

    manifest = create_manifest(identity, tmp_path)

    assert manifest.identity == identity
    assert manifest.artifacts == (
        ArtifactDigest(
            wheel.name,
            wheel.stat().st_size,
            hashlib.sha256(wheel.read_bytes()).hexdigest(),
        ),
        ArtifactDigest(
            sdist.name,
            sdist.stat().st_size,
            hashlib.sha256(sdist.read_bytes()).hexdigest(),
        ),
    )
    assert ReleaseManifest.from_json(manifest.to_json()) == manifest
    assert json.loads(manifest.to_json())["tag"] == "v0.2.0rc1"


def test_manifest_rejects_an_artifact_name_or_digest_mismatch(tmp_path: Path) -> None:
    identity = _identity()
    wheel, sdist = _write_metadata_artifacts(tmp_path, str(identity.version))

    with pytest.raises(ReleaseIdentityError, match="artifact name"):
        create_manifest(
            identity,
            tmp_path,
            artifacts=(wheel, tmp_path / "polis_nlp-0.2.0-py3-none-any.whl"),
        )

    manifest = ReleaseManifest(
        identity=identity,
        artifacts=(
            ArtifactDigest(wheel.name, wheel.stat().st_size, "0" * 64),
            ArtifactDigest(
                sdist.name, sdist.stat().st_size, hashlib.sha256(b"sdist").hexdigest()
            ),
        ),
    )
    with pytest.raises(ReleaseIdentityError, match="digest"):
        manifest.verify_artifacts(tmp_path)


def test_artifact_metadata_must_match_the_release_identity(tmp_path: Path) -> None:
    identity = _identity()
    wheel, sdist = _write_metadata_artifacts(tmp_path, str(identity.version))

    assert artifact_metadata_version(wheel) == identity.version
    assert artifact_metadata_version(sdist) == identity.version


def test_published_digest_check_rejects_missing_or_changed_files(
    tmp_path: Path,
) -> None:
    identity = _identity()
    wheel, sdist = _write_metadata_artifacts(tmp_path, str(identity.version))
    manifest = create_manifest(identity, tmp_path)

    with pytest.raises(ReleaseIdentityError, match="published digest"):
        require_published_digests(
            manifest,
            {wheel.name: manifest.artifacts[0].sha256, sdist.name: "0" * 64},
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-top-level",
        "extra-top-level",
        "bad-schema",
        "missing-size",
        "extra-field",
        "third-artifact",
    ],
    ids=[
        "missing-top-level",
        "extra-top-level",
        "bad-schema",
        "missing-size",
        "extra-field",
        "third-artifact",
    ],
)
def test_release_manifest_rejects_untrusted_schema_mutations(
    tmp_path: Path, mutation: str
) -> None:
    identity = ReleaseIdentity.create(version="0.2.0", source_commit="a" * 40)
    _write_metadata_artifacts(tmp_path, "0.2.0")
    payload = json.loads(create_manifest(identity, tmp_path).to_json())

    match mutation:
        case "missing-top-level":
            payload.pop("schema_version")
        case "extra-top-level":
            payload["unexpected"] = True
        case "bad-schema":
            payload["schema_version"] = 2
        case "missing-size":
            payload["artifacts"][0].pop("size")
        case "extra-field":
            payload["artifacts"][0]["unexpected"] = True
        case "third-artifact":
            payload["artifacts"].append(payload["artifacts"][0])
        case _:
            raise AssertionError(f"unknown test mutation: {mutation}")

    with pytest.raises(ReleaseIdentityError):
        ReleaseManifest.from_json(json.dumps(payload))
