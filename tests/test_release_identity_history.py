from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from scripts.release_identity import (
    ReleaseIdentity,
    ReleaseIdentityError,
    changelog_section,
    read_project_version,
    require_tagged_evidence,
    verify_all_tagged_evidence,
    verify_repository_tagged_evidence,
    verify_tag_binding,
)
from tests.release_identity_helpers import ROOT


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
