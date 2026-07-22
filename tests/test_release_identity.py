from __future__ import annotations

import hashlib
import io
import json
import subprocess
import tarfile
import zipfile
from pathlib import Path

import pytest
import scripts.release_identity as release_identity_module
from scripts.release_identity import (
    ArtifactDigest,
    ReleaseIdentity,
    ReleaseIdentityError,
    ReleaseManifest,
    artifact_metadata_version,
    changelog_section,
    collect_release_observations,
    create_manifest,
    main,
    read_project_version,
    release_tag,
    require_new_candidate,
    require_published_digests,
    require_tagged_evidence,
    verify_all_tagged_evidence,
    verify_release_identity,
    verify_repository_tagged_evidence,
    verify_tag_binding,
)

ROOT = Path(__file__).resolve().parents[1]


def _identity(version: str = "0.2.0rc1") -> ReleaseIdentity:
    return ReleaseIdentity.create(version=version, source_commit="a" * 40)


def _write_artifacts(dist: Path, version: str) -> tuple[Path, Path]:
    wheel = dist / f"polis_nlp-{version}-py3-none-any.whl"
    sdist = dist / f"polis_nlp-{version}.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    return wheel, sdist


def _write_metadata_artifacts(dist: Path, version: str) -> tuple[Path, Path]:
    wheel, sdist = _write_artifacts(dist, version)
    metadata = f"Metadata-Version: 2.4\nName: polis-nlp\nVersion: {version}\n".encode()
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"polis_nlp-{version}.dist-info/METADATA", metadata)
    with tarfile.open(sdist, "w:gz") as archive:
        info = tarfile.TarInfo(f"polis_nlp-{version}/PKG-INFO")
        info.size = len(metadata)
        archive.addfile(info, io.BytesIO(metadata))
    return wheel, sdist


def test_release_tag_accepts_next_dev_rc_and_stable_versions() -> None:
    assert release_tag("0.2.0.dev0") == "v0.2.0.dev0"
    assert release_tag("0.2.0rc1") == "v0.2.0rc1"
    assert release_tag("0.2.0") == "v0.2.0"


@pytest.mark.parametrize("version", ["0.2", "release-0.2.0", "0.2.0+local"])
def test_release_tag_rejects_non_canonical_or_local_versions(version: str) -> None:
    with pytest.raises(ReleaseIdentityError, match="canonical public PEP 440"):
        release_tag(version)


def test_candidate_rejects_reused_lower_existing_or_published_versions() -> None:
    identity = _identity("0.2.0")

    with pytest.raises(ReleaseIdentityError, match="not greater"):
        require_new_candidate(
            identity,
            latest_published="0.2.0",
            local_tags=(),
            remote_tags=(),
            github_releases=(),
            package_index_versions=(),
        )

    with pytest.raises(ReleaseIdentityError, match="local tag"):
        require_new_candidate(
            identity,
            latest_published="0.1.0",
            local_tags=(identity.tag,),
            remote_tags=(),
            github_releases=(),
            package_index_versions=(),
        )

    with pytest.raises(ReleaseIdentityError, match="package index"):
        require_new_candidate(
            identity,
            latest_published="0.1.0",
            local_tags=(),
            remote_tags=(),
            github_releases=(),
            package_index_versions=("0.2.0",),
        )

    with pytest.raises(ReleaseIdentityError, match="not greater"):
        require_new_candidate(
            identity,
            latest_published="0.1.0",
            local_tags=(),
            remote_tags=(),
            github_releases=("v0.3.0",),
            package_index_versions=("0.3.0",),
        )

    with pytest.raises(ReleaseIdentityError, match="GitHub release"):
        require_new_candidate(
            identity,
            latest_published="0.1.0",
            local_tags=(),
            remote_tags=(),
            github_releases=(identity.tag,),
            package_index_versions=(),
        )


def test_release_identity_requires_exact_source_and_evidence_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        release_identity_module,
        "_require_source_commit",
        lambda *_args, **_kwargs: None,
    )
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nversion = '0.2.0rc1'\n", encoding="utf-8")
    note = tmp_path / "docs" / "release-notes" / "0.2.0rc1.md"
    note.parent.mkdir(parents=True)
    note.write_bytes(b"# Polis 0.2.0rc1-extra\n")
    (tmp_path / "CHANGELOG.md").write_bytes(b"## 0.2.0rc1\n")

    with pytest.raises(ReleaseIdentityError, match="release note heading"):
        verify_release_identity(
            _identity(),
            repo=tmp_path,
            pyproject=project,
        )


def test_manifest_binds_one_exact_artifact_set_and_round_trips(tmp_path: Path) -> None:
    identity = _identity()
    wheel, sdist = _write_metadata_artifacts(tmp_path, str(identity.version))

    manifest = create_manifest(identity, tmp_path)

    assert manifest.identity == identity
    assert manifest.artifacts == (
        ArtifactDigest(wheel.name, hashlib.sha256(wheel.read_bytes()).hexdigest()),
        ArtifactDigest(sdist.name, hashlib.sha256(sdist.read_bytes()).hexdigest()),
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
            ArtifactDigest(wheel.name, "0" * 64),
            ArtifactDigest(sdist.name, hashlib.sha256(b"sdist").hexdigest()),
        ),
    )
    with pytest.raises(ReleaseIdentityError, match="digest"):
        manifest.verify_artifacts(tmp_path)


def test_artifact_metadata_must_match_the_release_identity(tmp_path: Path) -> None:
    identity = _identity()
    wheel, sdist = _write_metadata_artifacts(tmp_path, str(identity.version))

    assert artifact_metadata_version(wheel) == identity.version
    assert artifact_metadata_version(sdist) == identity.version


def test_tagged_evidence_compares_raw_bytes_without_newline_normalization() -> None:
    with pytest.raises(ReleaseIdentityError, match="release note"):
        require_tagged_evidence(
            current_note=b"heading\n",
            tagged_note=b"heading\r\n",
            current_changelog_section=b"## 0.2.0\n",
            tagged_changelog_section=b"## 0.2.0\n",
        )


def test_tagged_evidence_rejects_changed_changelog_section() -> None:
    with pytest.raises(ReleaseIdentityError, match="changelog section"):
        require_tagged_evidence(
            current_note=b"note\n",
            tagged_note=b"note\n",
            current_changelog_section=b"## 0.2.0\nnew\n",
            tagged_changelog_section=b"## 0.2.0\n",
        )


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


def test_read_project_version_uses_pyproject_as_the_authoritative_source(
    tmp_path: Path,
) -> None:
    project = tmp_path / "pyproject.toml"
    project.write_text("[project]\nversion = '0.2.0.dev0'\n", encoding="utf-8")

    assert read_project_version(project) == "0.2.0.dev0"


def test_changelog_section_uses_exact_bytes_between_version_headings() -> None:
    changelog = (
        b"# Changelog\n\n## Unreleased\n\n- pending\n\n"
        b"## 0.2.0 (2026-07-22)\n\n- published\n\n"
        b"## 0.1.0 (2026-07-20)\n\n- older\n"
    )

    assert (
        changelog_section(changelog, "0.2.0")
        == b"## 0.2.0 (2026-07-22)\n\n- published\n\n"
    )


def test_changelog_section_rejects_missing_or_duplicate_version_headings() -> None:
    with pytest.raises(ReleaseIdentityError, match="exactly one"):
        changelog_section(b"# Changelog\n", "0.2.0")
    with pytest.raises(ReleaseIdentityError, match="exactly one"):
        changelog_section(b"## 0.2.0\n\n## 0.2.0\n", "0.2.0")


def test_current_0_1_0_evidence_is_byte_identical_to_its_tag() -> None:
    verify_repository_tagged_evidence(ROOT, tag="v0.1.0", version="0.1.0")


def test_all_tagged_release_evidence_is_byte_identical() -> None:
    verify_all_tagged_evidence(ROOT)


def test_tagged_identity_binds_the_tag_to_its_source_commit() -> None:
    source_commit = subprocess.check_output(
        ["git", "rev-list", "-n", "1", "v0.1.0"], cwd=ROOT, text=True
    ).strip()

    verify_tag_binding(
        ROOT,
        ReleaseIdentity.create(version="0.1.0", source_commit=source_commit),
    )


def test_0_1_0_erratum_records_the_published_asset_digests() -> None:
    erratum = (ROOT / "docs/release-notes/0.1.0-erratum.md").read_text(encoding="utf-8")

    assert "append-only" in erratum
    assert "1bea324386cbabbe985e4af1fabf7c6e787228bd46e5f1a7971f4cd7a3a5c640" in erratum
    assert "ab90e5b708631c0accb03537e3f7a858a840cf622cf7416bae1fa47f3fc73aa5" in erratum
    assert "v0.1.0" in erratum


def test_manifest_cli_records_one_build_once_artifact_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        release_identity_module,
        "_require_source_commit",
        lambda *_args, **_kwargs: None,
    )
    version = "0.2.0.dev0"
    _write_metadata_artifacts(tmp_path, version)
    project = tmp_path / "pyproject.toml"
    project.write_text(f"[project]\nversion = '{version}'\n", encoding="utf-8")
    output = tmp_path / "release-manifest.json"

    assert (
        main(
            [
                "manifest",
                "--pyproject",
                str(project),
                "--source-commit",
                "b" * 40,
                "--dist",
                str(tmp_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    manifest = ReleaseManifest.from_json(output.read_text(encoding="utf-8"))
    assert str(manifest.identity.version) == version
    manifest.verify_artifacts(tmp_path)


def test_candidate_cli_rejects_an_existing_remote_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        release_identity_module,
        "verify_release_identity",
        lambda *_args, **_kwargs: None,
    )
    with pytest.raises(ReleaseIdentityError, match="remote tag"):
        main(
            [
                "candidate",
                "--version",
                "0.2.0rc1",
                "--source-commit",
                "c" * 40,
                "--latest-published",
                "0.1.0",
                "--remote-tag",
                "v0.2.0rc1",
            ]
        )


def test_release_only_observations_use_explicit_injected_network_adapters() -> None:
    commands: list[tuple[str, ...]] = []

    def run(
        command: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        commands.append(tuple(command))
        if command[:3] == ["git", "tag", "--list"]:
            return subprocess.CompletedProcess(command, 0, b"v0.1.0\n", b"")
        if command[:2] == ["git", "ls-remote"]:
            return subprocess.CompletedProcess(
                command,
                0,
                b"abc\trefs/tags/v0.1.0\n",
                b"",
            )
        return subprocess.CompletedProcess(
            command,
            0,
            b"v0.1.0\n",
            b"",
        )

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"releases": {"0.1.0": [{}]}}'

    observations = collect_release_observations(
        remote="origin",
        github_repo="PSyron/polis",
        package_index_url="https://example.test/pypi/polis-nlp/json",
        run=run,
        open_url=lambda _request, timeout: Response(),
    )

    assert observations.local_tags == ("v0.1.0",)
    assert observations.remote_tags == ("v0.1.0",)
    assert observations.github_releases == ("v0.1.0",)
    assert observations.package_index_versions == ("0.1.0",)
    assert ("git", "tag", "--list") in commands
