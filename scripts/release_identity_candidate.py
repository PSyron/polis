from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urljoin

from packaging.version import InvalidVersion, Version
from scripts.release_identity_authority import (
    parse_github_releases,
    project_is_absent,
    read_json,
)
from scripts.release_identity_models import (
    COMMIT_RE,
    ReleaseIdentity,
    ReleaseIdentityError,
    ReleaseObservations,
    TagBinding,
    release_tag,
)

_GITHUB_API_URL = "https://api.github.com"


def collect_release_observations(
    *,
    repo: Path,
    tag: str,
    remote: str,
    github_repo: str,
    package_index_url: str,
) -> ReleaseObservations:
    github_base = os.environ.get("POLIS_RELEASE_GITHUB_API_URL", _GITHUB_API_URL)
    github_url = urljoin(f"{github_base.rstrip('/')}/", f"repos/{github_repo}/releases")
    return ReleaseObservations(
        local_tag=local_tag_binding(repo, tag),
        remote_tag=remote_tag_binding(remote, tag),
        github_releases=parse_github_releases(read_json(github_url)),
        package_index_is_absent=project_is_absent(package_index_url),
    )


def require_new_candidate(
    identity: ReleaseIdentity, *, state: str, observations: ReleaseObservations
) -> None:
    if not observations.package_index_is_absent:
        raise ReleaseIdentityError("configured package project already exists")
    release_versions = tuple(
        parse_release_tag_version(tag) for tag in observations.github_releases
    )
    if identity.tag in observations.github_releases:
        raise ReleaseIdentityError("candidate tag already has a GitHub release")
    if release_versions and identity.version <= max(release_versions):
        raise ReleaseIdentityError("candidate version is not greater than publication")
    if state == "candidate-absent":
        if observations.local_tag.exists or observations.remote_tag.exists:
            raise ReleaseIdentityError("candidate tag already exists")
        return
    if state == "tag-bound":
        require_annotated_binding(observations.local_tag, identity, "local")
        require_annotated_binding(observations.remote_tag, identity, "remote")
        return
    raise ReleaseIdentityError("candidate state is invalid")


def require_recovery_candidate(
    identity: ReleaseIdentity, *, observations: ReleaseObservations
) -> None:
    if observations.package_index_is_absent:
        raise ReleaseIdentityError("recovery requires an existing package project")
    release_versions = tuple(
        parse_release_tag_version(tag) for tag in observations.github_releases
    )
    if identity.tag in observations.github_releases:
        raise ReleaseIdentityError("candidate tag already has a GitHub release")
    if release_versions and identity.version <= max(release_versions):
        raise ReleaseIdentityError("candidate version is not greater than publication")
    require_annotated_binding(observations.local_tag, identity, "local")
    require_annotated_binding(observations.remote_tag, identity, "remote")


def local_tag_binding(repo: Path, tag: str) -> TagBinding:
    lines = command_lines(
        subprocess.run,
        [
            "git",
            "for-each-ref",
            "--format=%(objecttype)\t%(objectname)\t%(*objectname)",
            f"refs/tags/{tag}",
        ],
        cwd=repo,
    )
    if not lines:
        return TagBinding(False, False, None)
    if len(lines) != 1:
        raise ReleaseIdentityError("local release tag is ambiguous")
    fields = lines[0].split("\t")
    if len(fields) != 3:
        raise ReleaseIdentityError("local release tag has an invalid schema")
    object_type, object_sha, peeled_sha = fields
    if (
        object_type != "tag"
        or not COMMIT_RE.fullmatch(object_sha)
        or not COMMIT_RE.fullmatch(peeled_sha)
    ):
        return TagBinding(True, False, None)
    return TagBinding(True, object_sha != peeled_sha, peeled_sha)


def remote_tag_binding(remote: str, tag: str) -> TagBinding:
    bare: str | None = None
    peeled: str | None = None
    for line in command_lines(subprocess.run, ["git", "ls-remote", "--tags", remote]):
        fields = line.split("\t")
        if len(fields) != 2 or not COMMIT_RE.fullmatch(fields[0]):
            raise ReleaseIdentityError("remote tag observation has an invalid schema")
        sha, reference = fields
        if reference == f"refs/tags/{tag}":
            if bare is not None:
                raise ReleaseIdentityError("remote release tag is ambiguous")
            bare = sha
        elif reference == f"refs/tags/{tag}^{{}}":
            if peeled is not None:
                raise ReleaseIdentityError("remote release tag is ambiguous")
            peeled = sha
    if bare is None and peeled is None:
        return TagBinding(False, False, None)
    if bare is None or peeled is None:
        return TagBinding(True, False, None)
    return TagBinding(True, bare != peeled, peeled)


def require_annotated_binding(
    binding: TagBinding, identity: ReleaseIdentity, location: str
) -> None:
    if not binding.annotated or binding.source_commit != identity.source_commit:
        raise ReleaseIdentityError(
            f"{location} release tag is not an annotated binding to the source commit"
        )


def require_source_commit(repo: Path, source_commit: str) -> None:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{source_commit}^{{commit}}"],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ReleaseIdentityError("release identity source commit does not exist")


def command_lines(
    run: Callable[..., subprocess.CompletedProcess[bytes]],
    command: list[str],
    *,
    cwd: Path | None = None,
) -> tuple[str, ...]:
    completed = run(command, cwd=cwd, check=False, capture_output=True)
    if completed.returncode != 0:
        raise ReleaseIdentityError(
            f"release-only observation command failed: {' '.join(command[:2])}"
        )
    try:
        output = completed.stdout.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ReleaseIdentityError(
            "release-only observation command returned invalid UTF-8"
        ) from error
    return tuple(line.strip() for line in output.splitlines() if line.strip())


def parse_release_tag_version(tag: str) -> Version:
    if not tag.startswith("v"):
        raise ReleaseIdentityError("GitHub release tag is not canonical")
    version = tag.removeprefix("v")
    release_tag(version)
    return Version(version)


def parse_publication_version(value: str) -> Version:
    try:
        return Version(value)
    except InvalidVersion as error:
        raise ReleaseIdentityError("published version is invalid") from error
