from __future__ import annotations

import re
import subprocess
import tomllib
from collections.abc import Callable
from pathlib import Path

from scripts.release_identity_candidate import command_lines, require_source_commit
from scripts.release_identity_models import (
    ReleaseIdentity,
    ReleaseIdentityError,
    release_tag,
)


def require_tagged_evidence(
    *,
    current_note: bytes,
    tagged_note: bytes,
    current_changelog_section: bytes,
    tagged_changelog_section: bytes,
) -> None:
    if current_note != tagged_note:
        raise ReleaseIdentityError("release note differs from its tagged evidence")
    if current_changelog_section != tagged_changelog_section:
        raise ReleaseIdentityError("changelog section differs from its tagged evidence")


def read_project_version(pyproject: Path) -> str:
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ReleaseIdentityError("cannot read project metadata") from error
    project = data.get("project")
    if not isinstance(project, dict):
        raise ReleaseIdentityError("project metadata does not declare a version")
    version = project.get("version")
    if not isinstance(version, str):
        raise ReleaseIdentityError("project metadata does not declare a version")
    release_tag(version)
    return version


def changelog_section(changelog: bytes, version: str) -> bytes:
    prefix = f"## {version}".encode()
    lines = changelog.splitlines(keepends=True)
    matches = [
        index
        for index, line in enumerate(lines)
        if line.startswith(prefix)
        and (
            len(line) == len(prefix)
            or line[len(prefix) : len(prefix) + 1] in (b" ", b"\r", b"\n")
        )
    ]
    if len(matches) != 1:
        raise ReleaseIdentityError(
            f"changelog must contain exactly one section for version {version}"
        )
    start = matches[0]
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith(b"## ")
        ),
        len(lines),
    )
    return b"".join(lines[start:end])


def verify_repository_tagged_evidence(repo: Path, *, tag: str, version: str) -> None:
    release_tag(version)
    if tag != f"v{version}":
        raise ReleaseIdentityError("tag does not match the release version")
    note_relative = Path("docs/release-notes") / f"{version}.md"
    try:
        current_note = (repo / note_relative).read_bytes()
        current_changelog = (repo / "CHANGELOG.md").read_bytes()
    except OSError as error:
        raise ReleaseIdentityError(
            "checked-out release evidence is unavailable"
        ) from error
    tagged_note = git_show_bytes(repo, tag, note_relative)
    tagged_changelog = git_show_bytes(repo, tag, Path("CHANGELOG.md"))
    require_tagged_evidence(
        current_note=current_note,
        tagged_note=tagged_note,
        current_changelog_section=changelog_section(current_changelog, version),
        tagged_changelog_section=changelog_section(tagged_changelog, version),
    )


def verify_all_tagged_evidence(repo: Path) -> None:
    for tag in command_lines(subprocess.run, ["git", "tag", "--list", "v*"], cwd=repo):
        version = tag.removeprefix("v")
        try:
            release_tag(version)
        except ReleaseIdentityError:
            continue
        note = repo / "docs" / "release-notes" / f"{version}.md"
        if not note.is_file():
            raise ReleaseIdentityError(
                f"tagged release evidence is unavailable: {note.relative_to(repo)}"
            )
        verify_repository_tagged_evidence(repo, tag=tag, version=version)


def verify_release_identity(
    identity: ReleaseIdentity,
    *,
    repo: Path,
    pyproject: Path,
    source_verifier: Callable[[Path, str], None] = require_source_commit,
) -> None:
    version = str(identity.version)
    if read_project_version(pyproject) != version:
        raise ReleaseIdentityError(
            "project metadata version does not match release identity"
        )
    try:
        note_bytes = (repo / "docs" / "release-notes" / f"{version}.md").read_bytes()
        changelog = (repo / "CHANGELOG.md").read_bytes()
    except OSError as error:
        raise ReleaseIdentityError(
            "release identity evidence is unavailable"
        ) from error
    if note_bytes.splitlines()[0:1] != [f"# Polis {version}".encode()]:
        raise ReleaseIdentityError(
            "release note heading does not match release identity"
        )
    section = changelog_section(changelog, version)
    expected_heading = f"## {version}".encode()
    heading = section.splitlines()[0:1]
    if heading != [expected_heading] and not re.fullmatch(
        re.escape(expected_heading) + rb" \(\d{4}-\d{2}-\d{2}\)",
        heading[0] if heading else b"",
    ):
        raise ReleaseIdentityError("changelog heading does not match release identity")
    source_verifier(repo, identity.source_commit)


def verify_tag_binding(
    repo: Path,
    identity: ReleaseIdentity,
    *,
    source_verifier: Callable[[Path, str], None] = require_source_commit,
) -> None:
    source_verifier(repo, identity.source_commit)
    completed = subprocess.run(
        ["git", "rev-parse", f"{identity.tag}^{{commit}}"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ReleaseIdentityError("release identity tag does not exist")
    if completed.stdout.decode("utf-8").strip() != identity.source_commit:
        raise ReleaseIdentityError("release tag is not bound to the source commit")


def git_show_bytes(repo: Path, tag: str, relative_path: Path) -> bytes:
    completed = subprocess.run(
        ["git", "show", f"{tag}:{relative_path.as_posix()}"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ReleaseIdentityError(
            f"tagged release evidence is unavailable: {relative_path.as_posix()}"
        )
    return completed.stdout
