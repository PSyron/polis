from __future__ import annotations

import argparse
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

EXCLUDED_ARTIFACT_PREFIXES = (
    "experiments/",
    "data/finetuning/",
    "tests/",
    "third_party/",
    "docs/superpowers/",
    ".superpowers/",
)
PROHIBITED_VENDOR_MARKERS = (
    ".jar",
    ".onnx",
    ".pt",
    ".pth",
    ".bin",
    ".safetensors",
    ".m2/",
    "target/",
    "repository/",
)


def assert_metadata(metadata: bytes, artifact: Path) -> None:
    message = BytesParser().parsebytes(metadata)
    if message["License-Expression"] != "MIT":
        raise SystemExit(f"{artifact}: missing License-Expression: MIT")
    if message.get_all("License-File") != ["LICENSE"]:
        raise SystemExit(f"{artifact}: missing License-File: LICENSE")


def _without_sdist_root(name: str) -> str:
    parts = name.split("/", 1)
    return parts[1] if len(parts) == 2 else name


def _assert_no_excluded_members(
    names: list[str], *, artifact: Path, sdist: bool
) -> None:
    for raw_name in names:
        name = _without_sdist_root(raw_name) if sdist else raw_name
        if name.startswith(EXCLUDED_ARTIFACT_PREFIXES):
            raise SystemExit(f"{artifact}: excluded repository path: {name}")


def _assert_no_prohibited_vendor_members(
    names: list[str], *, artifact: Path, sdist: bool
) -> None:
    for raw_name in names:
        name = _without_sdist_root(raw_name) if sdist else raw_name
        if any(marker in name for marker in PROHIBITED_VENDOR_MARKERS):
            raise SystemExit(f"{artifact}: prohibited vendor path: {name}")


def verify_wheel(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        _assert_no_excluded_members(names, artifact=path, sdist=False)
        _assert_no_prohibited_vendor_members(names, artifact=path, sdist=False)
        metadata_name = next(
            (name for name in names if name.endswith(".dist-info/METADATA")), None
        )
        if metadata_name is None or not any(
            name.endswith("/licenses/LICENSE") for name in names
        ):
            raise SystemExit(f"{path}: wheel must contain METADATA and LICENSE")
        assert_metadata(archive.read(metadata_name), path)


def verify_sdist(path: Path) -> None:
    with tarfile.open(path) as archive:
        names = archive.getnames()
        _assert_no_excluded_members(names, artifact=path, sdist=True)
        _assert_no_prohibited_vendor_members(names, artifact=path, sdist=True)
        metadata_name = next(
            (name for name in names if name.endswith("/PKG-INFO")), None
        )
        if metadata_name is None or not any(
            name.endswith("/LICENSE") for name in names
        ):
            raise SystemExit(f"{path}: sdist must contain PKG-INFO and LICENSE")
        member = archive.extractfile(metadata_name)
        if member is None:
            raise SystemExit(f"{path}: cannot read PKG-INFO")
        assert_metadata(member.read(), path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify license metadata and LICENSE files in distributions."
    )
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    args = parser.parse_args()
    dist = args.dist
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit(
            "dist must contain exactly one wheel and one source distribution"
        )
    verify_wheel(wheels[0])
    verify_sdist(sdists[0])
    print("distribution artifacts declare MIT metadata and contain LICENSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
