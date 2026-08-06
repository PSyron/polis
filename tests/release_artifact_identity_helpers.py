from __future__ import annotations

import hashlib
import io
import tarfile
import zipfile
from pathlib import Path

from scripts.release_identity import ArtifactDigest, ReleaseIdentity, ReleaseManifest

SOURCE_COMMIT = "a" * 40
VERSION = "0.2.0"


def _metadata(name: str = "polis-nlp", version: str = VERSION) -> bytes:
    return (f"Metadata-Version: 2.4\nName: {name}\nVersion: {version}\n").encode()


def write_adversarial_artifacts(dist: Path, case: str) -> tuple[Path, Path]:
    wheel_name = f"polis_nlp-{VERSION}-py3-none-any.whl"
    sdist_name = f"polis_nlp-{VERSION}.tar.gz"
    if case == "evil-outer":
        wheel_name = "evil.whl"
        sdist_name = "evil.tar.gz"
    elif case == "wrong-distribution-outer":
        wheel_name = f"other_nlp-{VERSION}-py3-none-any.whl"
        sdist_name = f"other_nlp-{VERSION}.tar.gz"
    elif case == "wrong-version-outer":
        wheel_name = "polis_nlp-9.9.9-py3-none-any.whl"
        sdist_name = "polis_nlp-9.9.9.tar.gz"
    elif case == "evil-wheel-suffix":
        wheel_name = f"polis_nlp-{VERSION}-evil.whl"
    elif case == "platform-wheel-tag":
        wheel_name = f"polis_nlp-{VERSION}-cp312-cp312-macosx_11_0_arm64.whl"
    elif case == "python-two-wheel-tag":
        wheel_name = f"polis_nlp-{VERSION}-py2-none-any.whl"
    elif case == "wheel-build-tag":
        wheel_name = f"polis_nlp-{VERSION}-1-py3-none-any.whl"
    elif case == "malformed-wheel-tag":
        wheel_name = f"polis_nlp-{VERSION}-.whl"

    wheel = dist / wheel_name
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"polis_nlp-{VERSION}.dist-info/METADATA", _metadata())
        if case == "duplicate-wheel-metadata":
            archive.writestr(f"copy-{VERSION}.dist-info/METADATA", _metadata())
        elif case == "conflicting-wheel-metadata":
            archive.writestr(
                f"evil-{VERSION}.dist-info/METADATA", _metadata("evil-package")
            )

    sdist = dist / sdist_name
    with tarfile.open(sdist, "w:gz") as archive:
        canonical = _metadata()
        info = tarfile.TarInfo(f"polis_nlp-{VERSION}/PKG-INFO")
        info.size = len(canonical)
        archive.addfile(info, io.BytesIO(canonical))
        if case in {"duplicate-sdist-metadata", "conflicting-sdist-root"}:
            extra = (
                canonical
                if case == "duplicate-sdist-metadata"
                else _metadata("evil-package")
            )
            extra_info = tarfile.TarInfo(f"evil-{VERSION}/PKG-INFO")
            extra_info.size = len(extra)
            archive.addfile(extra_info, io.BytesIO(extra))
    return wheel, sdist


def write_manifest(dist: Path, path: Path) -> None:
    artifacts = tuple(
        ArtifactDigest(
            artifact.name,
            artifact.stat().st_size,
            hashlib.sha256(artifact.read_bytes()).hexdigest(),
        )
        for artifact in sorted(dist.iterdir())
    )
    path.write_text(
        ReleaseManifest(
            ReleaseIdentity.create(version=VERSION, source_commit=SOURCE_COMMIT),
            artifacts,
        ).to_json(),
        encoding="utf-8",
    )
