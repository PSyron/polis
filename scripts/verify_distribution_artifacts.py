from __future__ import annotations

import argparse
import stat
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

from packaging.utils import (
    canonicalize_name,
    parse_sdist_filename,
    parse_wheel_filename,
)
from packaging.version import InvalidVersion, Version

REQUIRED_SDIST_MEMBERS = (
    "LICENSE",
    "README.md",
    "pyproject.toml",
    "src/polis/__init__.py",
    "src/polis/py.typed",
    "docs/compatibility.md",
    "docs/distribution-verification.md",
    "docs/offline-operation.md",
    "docs/privacy.md",
    "docs/public-api.md",
    "docs/quick-start.md",
    "docs/architecture/decisions/0023-evaluation-namespace-1-0.md",
)
REQUIRED_WHEEL_MEMBERS = (
    "docs/architecture/decisions/0023-evaluation-namespace-1-0.md",
)
EXPECTED_SOURCE_MEMBERS = tuple(
    (
        "src/polis/__init__.py src/polis/analysis/__init__.py "
        "src/polis/analysis/pipeline.py src/polis/analyzer.py "
        "src/polis/cli/__init__.py src/polis/cli/__main__.py "
        "src/polis/core/__init__.py src/polis/core/models.py "
        "src/polis/core/protocols.py src/polis/core/serialization.py "
        "src/polis/correction/__init__.py src/polis/correction/policy.py "
        "src/polis/evaluation/__init__.py "
        "src/polis/evaluation/_quality_parsing.py "
        "src/polis/evaluation/_quality_rules.py "
        "src/polis/evaluation/_quality_types.py "
        "src/polis/evaluation/correction_corpus.py src/polis/evaluation/dataset.py "
        "src/polis/evaluation/datasets/__init__.py "
        "src/polis/evaluation/datasets/quality/__init__.py "
        "src/polis/evaluation/datasets/quality/v1/__init__.py "
        "src/polis/evaluation/datasets/quality/v1/cases.json "
        "src/polis/evaluation/datasets/quality/v1/manifest.json "
        "src/polis/evaluation/datasets/v1/__init__.py "
        "src/polis/evaluation/datasets/v1/cases.json src/polis/evaluation/metrics.py "
        "src/polis/evaluation/quality_dataset.py "
        "src/polis/evaluation/quality_protocol.py "
        "src/polis/evaluation/quality_report.py "
        "src/polis/evaluation/quality_report_baseline.py "
        "src/polis/evaluation/quality_report_models.py "
        "src/polis/evaluation/quality_report_proposal.py "
        "src/polis/evaluation/quality_report_validation.py "
        "src/polis/evaluation/quality_runner.py "
        "src/polis/evaluation/safety_corpus.py src/polis/py.typed "
        "src/polis/rules/__init__.py src/polis/rules/agreement.py "
        "src/polis/rules/inflection.py src/polis/rules/spelling.py "
        "src/polis/rules/syntax.py "
        "src/polis/segmentation/__init__.py"
    ).split()
)
ALLOWED_SDIST_MEMBERS = (
    *REQUIRED_SDIST_MEMBERS,
    ".gitignore",
    "PKG-INFO",
    "docs/customization.md",
    "docs/development/dependency-licenses.md",
    "docs/limitations.md",
    "docs/prerelease-candidate.md",
    "docs/privacy-audit.md",
    "docs/release-notes/0.1.0-erratum.md",
    "docs/release-notes/0.1.0.md",
    "docs/release-notes/0.2.0.md",
    "docs/rules.md",
    "docs/segmentation.md",
    "docs/architecture/decisions/0001-python-platform-licensing-policy.md",
    "docs/architecture/decisions/0003-public-api-and-exception-contract.md",
    "docs/architecture/decisions/0008-hybrid-correction-policy.md",
    "docs/architecture/decisions/0018-runtime-composition-protocols.md",
    "docs/architecture/decisions/0019-evaluation-namespace-compatibility.md",
    "docs/architecture/decisions/0023-evaluation-namespace-1-0.md",
    "examples/polis.toml",
)
EXPECTED_WHEEL_METADATA_SUFFIXES = (
    "METADATA",
    "RECORD",
    "WHEEL",
    "entry_points.txt",
    "licenses/LICENSE",
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
PROJECT_METADATA = Path(__file__).resolve().parents[1] / "pyproject.toml"
DistributionIdentity = tuple[str, Version]


def expected_distribution_identity() -> DistributionIdentity:
    with PROJECT_METADATA.open("rb") as metadata_file:
        project = tomllib.load(metadata_file)["project"]
    name = project.get("name")
    version = project.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise SystemExit("pyproject.toml: project name and version are required")
    try:
        return canonicalize_name(name), Version(version)
    except InvalidVersion as error:
        raise SystemExit("pyproject.toml: project version is invalid") from error


def assert_metadata(
    metadata: bytes, artifact: Path, expected: DistributionIdentity
) -> None:
    message = BytesParser().parsebytes(metadata)
    names = message.get_all("Name") or []
    versions = message.get_all("Version") or []
    if len(names) != 1:
        raise SystemExit(f"{artifact}: distribution identity mismatch: metadata Name")
    if len(versions) != 1:
        raise SystemExit(
            f"{artifact}: distribution identity mismatch: metadata Version"
        )
    try:
        metadata_name = canonicalize_name(names[0])
        metadata_version = Version(versions[0])
    except InvalidVersion as error:
        raise SystemExit(
            f"{artifact}: distribution identity mismatch: metadata Version"
        ) from error
    if metadata_name != expected[0]:
        raise SystemExit(f"{artifact}: distribution identity mismatch: METADATA Name")
    if metadata_version != expected[1]:
        raise SystemExit(
            f"{artifact}: distribution identity mismatch: METADATA Version"
        )
    if message["License-Expression"] != "MIT":
        raise SystemExit(f"{artifact}: missing License-Expression: MIT")
    if message.get_all("License-File") != ["LICENSE"]:
        raise SystemExit(f"{artifact}: missing License-File: LICENSE")


def _without_sdist_root(name: str) -> str:
    parts = name.split("/", 1)
    return parts[1] if len(parts) == 2 else name


def _assert_explicit_sdist_surface(names: list[str], *, artifact: Path) -> None:
    normalized = {_without_sdist_root(name) for name in names}
    for required in REQUIRED_SDIST_MEMBERS:
        if required not in normalized:
            raise SystemExit(f"{artifact}: missing required sdist member: {required}")

    package_members = {name for name in normalized if name.startswith("src/polis/")}
    expected_package_members = set(EXPECTED_SOURCE_MEMBERS)
    missing = expected_package_members - package_members
    if missing:
        raise SystemExit(f"{artifact}: missing package member: {sorted(missing)[0]}")
    extra = package_members - expected_package_members
    if extra:
        raise SystemExit(
            f"{artifact}: sdist member outside release surface: {sorted(extra)[0]}"
        )

    unknown = normalized - set(ALLOWED_SDIST_MEMBERS) - expected_package_members
    if unknown:
        raise SystemExit(
            f"{artifact}: sdist member outside release surface: {sorted(unknown)[0]}"
        )


def _assert_explicit_wheel_surface(
    names: list[str], *, artifact: Path, expected: DistributionIdentity
) -> None:
    package_members = {f"src/{name}" for name in names if name.startswith("polis/")}
    expected_package_members = set(EXPECTED_SOURCE_MEMBERS)
    missing = expected_package_members - package_members
    if missing:
        raise SystemExit(f"{artifact}: missing package member: {sorted(missing)[0]}")
    extra = package_members - expected_package_members
    if extra:
        raise SystemExit(
            f"{artifact}: wheel member outside release surface: {sorted(extra)[0]}"
        )

    metadata_members = [name for name in names if ".dist-info/" in name]
    prefixes = {name.split("/", 1)[0] for name in metadata_members}
    if len(prefixes) != 1:
        raise SystemExit(f"{artifact}: wheel must contain one dist-info directory")
    prefix = next(iter(prefixes))
    expected_prefix = f"{expected[0].replace('-', '_')}-{expected[1]}.dist-info"
    if prefix != expected_prefix:
        raise SystemExit(f"{artifact}: dist-info directory does not match wheel")
    expected_metadata = {
        f"{prefix}/{suffix}" for suffix in EXPECTED_WHEEL_METADATA_SUFFIXES
    }
    if set(metadata_members) != expected_metadata:
        unexpected = set(metadata_members) - expected_metadata
        missing_metadata = expected_metadata - set(metadata_members)
        detail = sorted(unexpected or missing_metadata)[0]
        raise SystemExit(
            f"{artifact}: wheel metadata outside release surface: {detail}"
        )

    for required in REQUIRED_WHEEL_MEMBERS:
        if required not in names:
            raise SystemExit(f"{artifact}: missing required wheel member: {required}")

    unknown = (
        set(names)
        - {name.removeprefix("src/") for name in EXPECTED_SOURCE_MEMBERS}
        - expected_metadata
        - set(REQUIRED_WHEEL_MEMBERS)
    )
    if unknown:
        raise SystemExit(
            f"{artifact}: wheel member outside release surface: {sorted(unknown)[0]}"
        )


def _assert_no_prohibited_vendor_members(
    names: list[str], *, artifact: Path, sdist: bool
) -> None:
    for raw_name in names:
        name = _without_sdist_root(raw_name) if sdist else raw_name
        if any(marker in name for marker in PROHIBITED_VENDOR_MARKERS):
            raise SystemExit(f"{artifact}: prohibited vendor path: {name}")


def verify_wheel(path: Path, expected: DistributionIdentity | None = None) -> None:
    expected = expected or expected_distribution_identity()
    try:
        wheel_name, wheel_version, _, _ = parse_wheel_filename(path.name)
    except ValueError as error:
        raise SystemExit(
            f"{path}: distribution identity mismatch: wheel filename"
        ) from error
    if canonicalize_name(wheel_name) != expected[0] or wheel_version != expected[1]:
        raise SystemExit(f"{path}: distribution identity mismatch: wheel filename")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = [member.filename for member in members]
        if len(names) != len(set(names)):
            raise SystemExit(f"{path}: duplicate archive member")
        if any(
            member.is_dir()
            or stat.S_IFMT(member.external_attr >> 16) not in (0, stat.S_IFREG)
            for member in members
        ):
            raise SystemExit(f"{path}: non-regular archive member")
        _assert_no_prohibited_vendor_members(names, artifact=path, sdist=False)
        _assert_explicit_wheel_surface(names, artifact=path, expected=expected)
        metadata_name = next(
            (name for name in names if name.endswith(".dist-info/METADATA")), None
        )
        if metadata_name is None or not any(
            name.endswith("/licenses/LICENSE") for name in names
        ):
            raise SystemExit(f"{path}: wheel must contain METADATA and LICENSE")
        assert_metadata(archive.read(metadata_name), path, expected)


def verify_sdist(path: Path, expected: DistributionIdentity | None = None) -> None:
    expected = expected or expected_distribution_identity()
    try:
        sdist_name, sdist_version = parse_sdist_filename(path.name)
    except ValueError as error:
        raise SystemExit(
            f"{path}: distribution identity mismatch: sdist filename/root"
        ) from error
    if canonicalize_name(sdist_name) != expected[0] or sdist_version != expected[1]:
        raise SystemExit(f"{path}: distribution identity mismatch: sdist filename/root")
    with tarfile.open(path) as archive:
        members = archive.getmembers()
        names = [member.name for member in members]
        if len(names) != len(set(names)):
            raise SystemExit(f"{path}: duplicate archive member")
        if any(not member.isfile() for member in members):
            raise SystemExit(f"{path}: non-regular archive member")
        if len({name.split("/", 1)[0] for name in names}) != 1:
            raise SystemExit(f"{path}: multiple sdist roots")
        root = names[0].split("/", 1)[0]
        try:
            root_name, root_version = parse_sdist_filename(f"{root}.tar.gz")
        except ValueError as error:
            raise SystemExit(
                f"{path}: distribution identity mismatch: sdist filename/root"
            ) from error
        if canonicalize_name(root_name) != expected[0] or root_version != expected[1]:
            raise SystemExit(
                f"{path}: distribution identity mismatch: sdist filename/root"
            )
        _assert_no_prohibited_vendor_members(names, artifact=path, sdist=True)
        _assert_explicit_sdist_surface(names, artifact=path)
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
        assert_metadata(member.read(), path, expected)


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
    expected = expected_distribution_identity()
    verify_wheel(wheels[0], expected)
    verify_sdist(sdists[0], expected)
    print("distribution artifacts declare MIT metadata and contain LICENSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
