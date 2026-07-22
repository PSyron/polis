from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import Any

import pytest
from scripts import release_identity, verify_prerelease_candidate

ROOT = Path(__file__).resolve().parents[1]


def _write_artifacts(dist: Path, version: str) -> tuple[Path, Path]:
    dist.mkdir()
    normalized = version.replace("-", "_")
    wheel = dist / f"polis_nlp-{normalized}-py3-none-any.whl"
    wheel_metadata = f"Name: polis-nlp\nVersion: {version}\n\n".encode()
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"polis_nlp-{normalized}.dist-info/METADATA", wheel_metadata)

    sdist = dist / f"polis_nlp-{version}.tar.gz"
    info = tarfile.TarInfo(f"polis_nlp-{version}/PKG-INFO")
    info.size = len(wheel_metadata)
    with tarfile.open(sdist, "w:gz") as archive:
        archive.addfile(info, io.BytesIO(wheel_metadata))
    return wheel, sdist


@pytest.mark.parametrize(
    "value",
    [
        "0.2",
        "v0.2.0",
        "0.2.0-rc1",
        "0.2.0rc0",
        "0.2.0rc01",
        "0.2.0.dev1",
        "01.2.0",
        "0.2.0+local",
    ],
)
def test_release_version_rejects_noncanonical_identifiers(value: str) -> None:
    with pytest.raises(ValueError, match="canonical release lifecycle"):
        release_identity.ReleaseVersion.parse(value)


def test_release_lifecycle_accepts_dev_rc_sequence_and_stable() -> None:
    release_identity.validate_transition("0.2.0.dev0", "0.2.0rc1")
    release_identity.validate_transition("0.2.0rc1", "0.2.0rc2")
    release_identity.validate_transition("0.2.0rc2", "0.2.0")


def test_changelog_rejects_duplicate_release_identity() -> None:
    duplicate = (
        b"# Changelog\n\n## 0.2.0rc1 (2026-07-22)\n\n- First.\n"
        b"\n## 0.2.0rc1 (2026-07-23)\n\n- Reused.\n"
    )
    with pytest.raises(ValueError, match="exactly one changelog section"):
        release_identity._changelog_section(duplicate, "0.2.0rc1")


@pytest.mark.parametrize(
    ("current", "requested", "message"),
    [
        ("0.2.0.dev0", "0.2.0rc2", "first candidate must be rc1"),
        ("0.2.0rc1", "0.2.0rc1", "strictly advance"),
        ("0.2.0rc2", "0.2.0rc1", "strictly advance"),
        ("0.2.0rc1", "0.2.1rc2", "same base version"),
        ("0.2.0", "0.2.1rc1", "stable source must move to the next dev0"),
        ("0.2.0.dev0", "0.2.0", "must pass through an rc"),
    ],
)
def test_release_lifecycle_rejects_skips_reuse_and_regression(
    current: str, requested: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        release_identity.validate_transition(current, requested)


def test_candidate_must_exceed_latest_stable_and_not_be_published() -> None:
    release_identity.validate_candidate(
        "0.2.0rc1", latest_stable="0.1.0", published_versions={"0.1.0"}
    )

    with pytest.raises(ValueError, match="higher than latest stable"):
        release_identity.validate_candidate(
            "0.1.0rc1", latest_stable="0.1.0", published_versions=set()
        )


def test_published_history_must_match_claimed_stable_and_previous_candidate() -> None:
    with pytest.raises(ValueError, match="latest published stable is 0.3.0"):
        release_identity.validate_candidate(
            "0.2.0rc1",
            latest_stable="0.1.0",
            published_versions={"0.1.0", "0.3.0"},
        )
    with pytest.raises(ValueError, match="previous rc must already be published"):
        release_identity.validate_published_history(
            previous="0.2.0rc1",
            requested="0.2.0rc2",
            published_versions={"0.1.0"},
        )
    release_identity.validate_published_history(
        previous="0.2.0rc1",
        requested="0.2.0rc2",
        published_versions={"0.1.0", "0.2.0rc1"},
    )
    with pytest.raises(ValueError, match="higher than latest stable"):
        release_identity.validate_candidate(
            "0.0.9", latest_stable="0.1.0", published_versions=set()
        )
    with pytest.raises(ValueError, match="already published"):
        release_identity.validate_candidate(
            "0.2.0rc1",
            latest_stable="0.1.0",
            published_versions={"0.1.0", "0.2.0rc1"},
        )


def test_freeze_manifest_requires_exact_identity_and_hashes_artifacts(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        '[project]\nname = "polis-nlp"\nversion = "0.2.0rc1"\n', encoding="utf-8"
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 0.2.0rc1 (2026-07-22)\n\n- Candidate.\n",
        encoding="utf-8",
    )
    notes = root / "docs/release-notes/0.2.0rc1.md"
    notes.parent.mkdir(parents=True)
    notes.write_text("# Release notes: 0.2.0rc1\n", encoding="utf-8")
    wheel, sdist = _write_artifacts(root / "dist", "0.2.0rc1")
    manifest_path = root / "dist/release-manifest.json"

    manifest = release_identity.freeze_manifest(
        root=root,
        dist=root / "dist",
        manifest_path=manifest_path,
        requested_version="0.2.0rc1",
        requested_tag="v0.2.0rc1",
        previous_version="0.2.0.dev0",
        latest_stable="0.1.0",
        published_versions={"0.1.0"},
        existing_tags={"v0.1.0"},
        source_commit="a" * 40,
    )

    assert manifest["version"] == "0.2.0rc1"
    assert manifest["tag"] == "v0.2.0rc1"
    assert manifest["release_notes"] == "docs/release-notes/0.2.0rc1.md"
    assert {item["filename"] for item in manifest["artifacts"]} == {
        wheel.name,
        sdist.name,
    }
    assert all(len(item["sha256"]) == 64 for item in manifest["artifacts"])
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest

    with pytest.raises(ValueError, match="manifest already exists"):
        release_identity.freeze_manifest(
            root=root,
            dist=root / "dist",
            manifest_path=manifest_path,
            requested_version="0.2.0rc1",
            requested_tag="v0.2.0rc1",
            previous_version="0.2.0.dev0",
            latest_stable="0.1.0",
            published_versions={"0.1.0"},
            existing_tags={"v0.1.0"},
            source_commit="a" * 40,
        )

    release_identity.verify_manifest(
        root=root, dist=root / "dist", manifest_path=manifest_path
    )
    altered_manifest = dict(manifest)
    altered_manifest["project"] = "another-project"
    manifest_path.write_text(json.dumps(altered_manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest project"):
        release_identity.verify_manifest(
            root=root, dist=root / "dist", manifest_path=manifest_path
        )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    wheel.write_bytes(wheel.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="changed after manifest freeze"):
        release_identity.verify_manifest(
            root=root, dist=root / "dist", manifest_path=manifest_path
        )


@pytest.mark.parametrize(
    ("source_version", "artifact_version", "tag", "notes_version", "error"),
    [
        ("0.2.0rc2", "0.2.0rc1", "v0.2.0rc1", "0.2.0rc1", "pyproject"),
        ("0.2.0rc1", "0.2.0rc2", "v0.2.0rc1", "0.2.0rc1", "artifact"),
        ("0.2.0rc1", "0.2.0rc1", "0.2.0rc1", "0.2.0rc1", "tag"),
        ("0.2.0rc1", "0.2.0rc1", "v0.2.0rc1", "0.2.0rc2", "notes"),
    ],
)
def test_freeze_manifest_rejects_mismatched_identity(
    tmp_path: Path,
    source_version: str,
    artifact_version: str,
    tag: str,
    notes_version: str,
    error: str,
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "polis-nlp"\nversion = "{source_version}"\n',
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 0.2.0rc1 (2026-07-22)\n", encoding="utf-8"
    )
    notes = root / "docs/release-notes/0.2.0rc1.md"
    notes.parent.mkdir(parents=True)
    notes.write_text(f"# Release notes: {notes_version}\n", encoding="utf-8")
    _write_artifacts(root / "dist", artifact_version)

    with pytest.raises(ValueError, match=error):
        release_identity.freeze_manifest(
            root=root,
            dist=root / "dist",
            manifest_path=root / "dist/release-manifest.json",
            requested_version="0.2.0rc1",
            requested_tag=tag,
            previous_version="0.2.0.dev0",
            latest_stable="0.1.0",
            published_versions=set(),
            existing_tags={"v0.1.0"},
            source_commit="a" * 40,
        )


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = json.dumps(payload).encode()

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def test_pypi_checks_are_injected_and_compare_exact_published_digests() -> None:
    calls: list[str] = []
    payload: dict[str, Any] = {
        "releases": {"0.1.0": [], "0.2.0rc1": []},
        "urls": [
            {"filename": "polis_nlp-0.2.0rc1.tar.gz", "digests": {"sha256": "b" * 64}},
            {
                "filename": "polis_nlp-0.2.0rc1-py3-none-any.whl",
                "digests": {"sha256": "a" * 64},
            },
        ],
    }

    def opener(url: str, *, timeout: float) -> _FakeResponse:
        calls.append(f"{url} timeout={timeout}")
        return _FakeResponse(payload)

    assert release_identity.fetch_published_versions(opener=opener) == {
        "0.1.0",
        "0.2.0rc1",
    }
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "project": "polis-nlp",
        "previous_version": "0.2.0.dev0",
        "version": "0.2.0rc1",
        "tag": "v0.2.0rc1",
        "release_notes": "docs/release-notes/0.2.0rc1.md",
        "release_notes_sha256": "c" * 64,
        "changelog_section_sha256": "d" * 64,
        "source_commit": "a" * 40,
        "artifacts": [
            {"filename": "polis_nlp-0.2.0rc1-py3-none-any.whl", "sha256": "a" * 64},
            {"filename": "polis_nlp-0.2.0rc1.tar.gz", "sha256": "b" * 64},
        ],
    }
    release_identity.verify_published_digests(
        manifest, version="0.2.0rc1", opener=opener
    )
    assert calls == [
        "https://pypi.org/pypi/polis-nlp/json timeout=10.0",
        "https://pypi.org/pypi/polis-nlp/0.2.0rc1/json timeout=10.0",
    ]

    payload["urls"] = [payload["urls"][0]]
    with pytest.raises(ValueError, match="published artifact names and digests"):
        release_identity.verify_published_digests(
            manifest, version="0.2.0rc1", opener=opener
        )

    with pytest.raises(ValueError, match="manifest artifact entry"):
        malformed_manifest = dict(manifest)
        malformed_manifest["artifacts"] = [
            {"filename": None, "sha256": "a" * 64},
            {"filename": "polis_nlp-0.2.0rc1.tar.gz", "sha256": "b" * 64},
        ]
        release_identity.verify_published_digests(
            malformed_manifest,
            version="0.2.0rc1",
            opener=opener,
        )

    payload["urls"] = [
        {
            "filename": "polis_nlp-0.2.0rc1-py3-none-any.whl",
            "digests": {"sha256": "0" * 64},
        },
        {
            "filename": "polis_nlp-0.2.0rc1-py3-none-any.whl",
            "digests": {"sha256": "a" * 64},
        },
        {"filename": "polis_nlp-0.2.0rc1.tar.gz", "digests": {"sha256": "b" * 64}},
    ]
    with pytest.raises(ValueError, match="duplicate published artifact"):
        release_identity.verify_published_digests(
            manifest, version="0.2.0rc1", opener=opener
        )

    tampered_manifest = dict(manifest)
    tampered_manifest["project"] = "another-project"
    with pytest.raises(ValueError, match="manifest project"):
        release_identity.verify_published_digests(
            tampered_manifest, version="0.2.0rc1", opener=opener
        )


def test_historical_0_1_0_notes_and_changelog_section_match_local_tag() -> None:
    notes = (ROOT / "docs/release-notes/0.1.0.md").read_bytes()
    changelog = (ROOT / "CHANGELOG.md").read_bytes()
    section = release_identity._changelog_section(changelog, "0.1.0")
    assert hashlib.sha256(notes).hexdigest() == (
        "53b285495a8711735cbcdc5aaa0d88aa2713d1090a00d673fcb93fbb14c4f3c5"
    )
    assert hashlib.sha256(section).hexdigest() == (
        "269dff3d21280ce9b56dcccaa4e3ad94611122fd9970c970fdec278fa99a2864"
    )

    tag = subprocess.run(
        ["git", "rev-parse", "--verify", "refs/tags/v0.1.0"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if tag.returncode == 0:
        release_identity.verify_tagged_evidence(ROOT, "v0.1.0")


def test_tagged_evidence_rejects_tag_with_mismatched_project_version(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    notes = root / "docs/release-notes/0.1.0.md"
    notes.parent.mkdir(parents=True)
    notes.write_text("# Release notes: 0.1.0\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 0.1.0 (2026-07-20)\n\n- Release.\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "polis-nlp"\nversion = "9.9.9"\n', encoding="utf-8"
    )
    for command in (
        ("init", "--quiet"),
        ("config", "user.name", "Paweł Cyroń"),
        ("config", "user.email", "release@example.invalid"),
        ("add", "."),
        ("commit", "--quiet", "-m", "fixture"),
        ("tag", "v0.1.0"),
    ):
        subprocess.run(["git", *command], cwd=root, check=True)

    with pytest.raises(ValueError, match="tagged pyproject version"):
        release_identity.verify_tagged_evidence(root, "v0.1.0")


def test_manifest_rejects_existing_tag_and_tag_must_bind_to_source_commit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "repo"
    notes = root / "docs/release-notes/0.2.0rc1.md"
    notes.parent.mkdir(parents=True)
    notes.write_text("# Release notes: 0.2.0rc1\n", encoding="utf-8")
    (root / "CHANGELOG.md").write_text(
        "# Changelog\n\n## 0.2.0rc1 (2026-07-22)\n\n- Candidate.\n",
        encoding="utf-8",
    )
    (root / "pyproject.toml").write_text(
        '[project]\nname = "polis-nlp"\nversion = "0.2.0rc1"\n', encoding="utf-8"
    )
    _write_artifacts(root / "dist", "0.2.0rc1")

    with pytest.raises(ValueError, match="tag already exists"):
        release_identity.freeze_manifest(
            root=root,
            dist=root / "dist",
            manifest_path=root / "dist/release-manifest.json",
            requested_version="0.2.0rc1",
            requested_tag="v0.2.0rc1",
            previous_version="0.2.0.dev0",
            latest_stable="0.1.0",
            published_versions={"0.1.0"},
            existing_tags={"v0.1.0", "v0.2.0rc1"},
            source_commit="a" * 40,
        )

    for command in (
        ("init", "--quiet"),
        ("config", "user.name", "Paweł Cyroń"),
        ("config", "user.email", "release@example.invalid"),
        ("add", "."),
        ("commit", "--quiet", "-m", "candidate"),
        ("tag", "v0.2.0rc1"),
    ):
        subprocess.run(["git", *command], cwd=root, check=True)
    source_commit = release_identity.current_commit(root)
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "project": "polis-nlp",
        "previous_version": "0.2.0.dev0",
        "version": "0.2.0rc1",
        "tag": "v0.2.0rc1",
        "release_notes": "docs/release-notes/0.2.0rc1.md",
        "release_notes_sha256": hashlib.sha256(notes.read_bytes()).hexdigest(),
        "changelog_section_sha256": hashlib.sha256(
            release_identity._changelog_section(
                (root / "CHANGELOG.md").read_bytes(), "0.2.0rc1"
            )
        ).hexdigest(),
        "source_commit": source_commit,
        "artifacts": [
            {"filename": "polis_nlp-0.2.0rc1-py3-none-any.whl", "sha256": "c" * 64},
            {"filename": "polis_nlp-0.2.0rc1.tar.gz", "sha256": "d" * 64},
        ],
    }
    release_identity.verify_tagged_evidence(root, "v0.2.0rc1", manifest=manifest)
    manifest["release_notes_sha256"] = "e" * 64
    with pytest.raises(ValueError, match="tagged release notes digest"):
        release_identity.verify_tagged_evidence(root, "v0.2.0rc1", manifest=manifest)
    manifest["release_notes_sha256"] = hashlib.sha256(notes.read_bytes()).hexdigest()
    manifest["source_commit"] = "f" * 40
    with pytest.raises(ValueError, match="tag commit differs"):
        release_identity.verify_tagged_evidence(root, "v0.2.0rc1", manifest=manifest)


def test_prerelease_orchestration_builds_once_and_reuses_dist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands: list[list[str]] = []
    frozen: dict[str, Any] = {}

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        verify_prerelease_candidate, "_run", lambda command: commands.append(command)
    )
    monkeypatch.setattr(release_identity, "fetch_published_versions", lambda: {"0.1.0"})
    monkeypatch.setattr(release_identity, "list_local_tags", lambda _root: {"v0.1.0"})
    monkeypatch.setattr(release_identity, "current_commit", lambda _root: "a" * 40)
    monkeypatch.setattr(release_identity, "require_clean_worktree", lambda _root: None)
    monkeypatch.setattr(
        release_identity, "verify_tagged_evidence", lambda _root, _tag: None
    )

    def freeze(**kwargs: Any) -> dict[str, Any]:
        frozen.update(kwargs)
        return {"artifacts": []}

    monkeypatch.setattr(release_identity, "freeze_manifest", freeze)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_prerelease_candidate.py",
            "--dist",
            "candidate-dist",
            "--version",
            "0.2.0rc1",
            "--tag",
            "v0.2.0rc1",
            "--previous-version",
            "0.2.0.dev0",
            "--latest-stable",
            "0.1.0",
            "--manifest",
            "candidate-dist/release-manifest.json",
            "--check-pypi",
        ],
    )

    verify_prerelease_candidate.main()

    builds = [command for command in commands if "build" in command]
    assert len(builds) == 1
    assert builds[0][-2:] == ["--outdir", "candidate-dist"]
    assert frozen["dist"] == (tmp_path / "candidate-dist").resolve()
    assert frozen["source_commit"] == "a" * 40
    assert frozen["existing_tags"] == {"v0.1.0"}


def test_prerelease_orchestration_rejects_stale_dist_before_build(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    stale = dist / "polis_nlp-0.1.0.tar.gz"
    stale.write_bytes(b"stale")

    with pytest.raises(SystemExit, match="output must be empty"):
        verify_prerelease_candidate._require_clean_output(
            dist, dist / "release-manifest.json"
        )


def test_prerelease_orchestration_rejects_missing_stable_tag_before_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    commands: list[list[str]] = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        verify_prerelease_candidate, "_run", lambda command: commands.append(command)
    )
    monkeypatch.setattr(release_identity, "require_clean_worktree", lambda _root: None)
    monkeypatch.setattr(release_identity, "fetch_published_versions", lambda: {"0.1.0"})
    monkeypatch.setattr(release_identity, "list_local_tags", lambda _root: set())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "verify_prerelease_candidate.py",
            "--version",
            "0.2.0rc1",
            "--tag",
            "v0.2.0rc1",
            "--previous-version",
            "0.2.0.dev0",
            "--latest-stable",
            "0.1.0",
            "--manifest",
            "dist/release-manifest.json",
            "--check-pypi",
        ],
    )

    with pytest.raises(SystemExit, match="latest stable tag is missing locally"):
        verify_prerelease_candidate.main()
    assert commands == []


def test_release_source_commit_requires_clean_worktree(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    tracked = root / "pyproject.toml"
    tracked.write_text('[project]\nversion = "0.2.0rc1"\n', encoding="utf-8")
    for command in (
        ("init", "--quiet"),
        ("config", "user.name", "Paweł Cyroń"),
        ("config", "user.email", "release@example.invalid"),
        ("add", "."),
        ("commit", "--quiet", "-m", "candidate"),
    ):
        subprocess.run(["git", *command], cwd=root, check=True)
    tracked.write_text('[project]\nversion = "0.2.0rc2"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="worktree must be clean"):
        release_identity.require_clean_worktree(root)


def test_release_documentation_defines_immutable_identity_workflow() -> None:
    lifecycle = (ROOT / "docs/release-lifecycle.md").read_text(encoding="utf-8")
    prerelease = (ROOT / "docs/prerelease-candidate.md").read_text(encoding="utf-8")
    distribution = (ROOT / "docs/distribution-verification.md").read_text(
        encoding="utf-8"
    )
    compatibility = (ROOT / "docs/compatibility.md").read_text(encoding="utf-8")
    combined = "\n".join((lifecycle, prerelease, distribution, compatibility))

    assert "0.2.0.dev0" in lifecycle
    assert "0.2.0rcN" in lifecycle
    assert "v<version>" in lifecycle
    assert "--check-pypi" in prerelease
    assert "release-manifest.json" in prerelease
    assert "verify-published" in distribution
    assert "Do not move or replace a published tag" in lifecycle
    assert "byte-for-byte" in combined
    assert "build exactly once" in combined
    assert "upload only the two paths" in distribution


def test_documented_prerelease_command_is_directly_executable() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify_prerelease_candidate.py", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--previous-version" in result.stdout
    assert "--check-pypi" in result.stdout
