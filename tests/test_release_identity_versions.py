from __future__ import annotations

from pathlib import Path

import pytest
import scripts.release_identity as release_identity_module
from scripts.release_identity import (
    ReleaseIdentityError,
    ReleaseObservations,
    TagBinding,
    release_tag,
    require_new_candidate,
    verify_release_identity,
)
from tests.release_identity_helpers import _identity


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

    with pytest.raises(ReleaseIdentityError, match="package project already exists"):
        require_new_candidate(
            identity,
            state="candidate-absent",
            observations=ReleaseObservations(
                TagBinding(False, False, None),
                TagBinding(False, False, None),
                (),
                False,
            ),
        )

    with pytest.raises(ReleaseIdentityError, match="candidate tag already exists"):
        require_new_candidate(
            identity,
            state="candidate-absent",
            observations=ReleaseObservations(
                TagBinding(True, False, None),
                TagBinding(False, False, None),
                (),
                True,
            ),
        )

    with pytest.raises(ReleaseIdentityError, match="not greater"):
        require_new_candidate(
            identity,
            state="candidate-absent",
            observations=ReleaseObservations(
                TagBinding(False, False, None),
                TagBinding(False, False, None),
                ("v0.3.0",),
                True,
            ),
        )

    with pytest.raises(ReleaseIdentityError, match="GitHub release"):
        require_new_candidate(
            identity,
            state="candidate-absent",
            observations=ReleaseObservations(
                TagBinding(False, False, None),
                TagBinding(False, False, None),
                (identity.tag,),
                True,
            ),
        )


def test_recovery_candidate_requires_existing_project_and_exact_tag_bindings() -> None:
    identity = _identity("0.2.0")
    matching = TagBinding(True, True, identity.source_commit)

    release_identity_module.require_recovery_candidate(
        identity,
        observations=ReleaseObservations(matching, matching, (), False),
    )

    with pytest.raises(ReleaseIdentityError, match="existing package project"):
        release_identity_module.require_recovery_candidate(
            identity,
            observations=ReleaseObservations(matching, matching, (), True),
        )
    with pytest.raises(ReleaseIdentityError, match="GitHub release"):
        release_identity_module.require_recovery_candidate(
            identity,
            observations=ReleaseObservations(
                matching, matching, (identity.tag,), False
            ),
        )
    with pytest.raises(ReleaseIdentityError, match="remote release tag"):
        release_identity_module.require_recovery_candidate(
            identity,
            observations=ReleaseObservations(
                matching, TagBinding(False, False, None), (), False
            ),
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
