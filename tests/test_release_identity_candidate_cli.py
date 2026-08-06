from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from tests.release_identity_helpers import (
    ROOT,
    _candidate_command,
    _cli_environment,
    _empty_remote,
    _HttpReply,
    _wire_server,
)


def test_candidate_cli_accepts_only_derived_publication_inputs() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/release_identity.py"),
            "candidate",
            "--help",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--state" in result.stdout
    assert "--latest-published" not in result.stdout


def test_candidate_cli_rejects_an_existing_remote_tag(tmp_path: Path) -> None:
    remote = _empty_remote(tmp_path)
    checkout = tmp_path / "checkout"
    cloned = subprocess.run(
        ["git", "clone", "--quiet", "--no-local", str(ROOT), str(checkout)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert cloned.returncode == 0, cloned.stderr
    tag = subprocess.run(
        ["git", "tag", "-a", "v0.2.0", "-m", "candidate tag"],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    assert tag.returncode == 0, tag.stderr
    pushed = subprocess.run(
        ["git", "push", str(remote), "v0.2.0"],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    assert pushed.returncode == 0, pushed.stderr
    routes = {
        "/repos/PSyron/polis/releases": [_HttpReply(200, b"[]")],
        "/pypi/polis-nlp/json": [_HttpReply(404, b"")],
    }

    with _wire_server(routes) as server:
        result = subprocess.run(
            _candidate_command(server=server, remote=remote, state="candidate-absent"),
            cwd=checkout,
            text=True,
            capture_output=True,
            check=False,
            env=_cli_environment(server),
        )

    assert result.returncode != 0
    assert "candidate tag already exists" in result.stderr
    assert server.requests == [
        "/repos/PSyron/polis/releases",
        "/pypi/polis-nlp/json",
    ]


def test_candidate_observes_github_and_package_index_over_local_wire(
    tmp_path: Path,
) -> None:
    remote = _empty_remote(tmp_path)
    routes = {
        "/repos/PSyron/polis/releases": [_HttpReply(200, b"[]")],
        "/pypi/polis-nlp/json": [_HttpReply(404, b"")],
    }

    with _wire_server(routes) as server:
        result = subprocess.run(
            _candidate_command(server=server, remote=remote, state="candidate-absent"),
            text=True,
            capture_output=True,
            check=False,
            env=_cli_environment(server),
        )

    assert result.returncode == 0, result.stderr
    assert server.requests == [
        "/repos/PSyron/polis/releases",
        "/pypi/polis-nlp/json",
    ]


def test_candidate_cli_accepts_project_404_before_first_upload(tmp_path: Path) -> None:
    remote = _empty_remote(tmp_path)
    routes = {
        "/repos/PSyron/polis/releases": [_HttpReply(200, b"[]")],
        "/pypi/polis-nlp/json": [_HttpReply(404, b"")],
    }

    with _wire_server(routes) as server:
        result = subprocess.run(
            _candidate_command(server=server, remote=remote, state="candidate-absent"),
            text=True,
            capture_output=True,
            check=False,
            env=_cli_environment(server),
        )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "candidate identity is available: v0.2.0\n"
    assert server.requests == [
        "/repos/PSyron/polis/releases",
        "/pypi/polis-nlp/json",
    ]


@pytest.mark.parametrize("status", [200, 403, 429, 500])
def test_candidate_cli_fail_closes_on_project_index_status(
    tmp_path: Path, status: int
) -> None:
    remote = _empty_remote(tmp_path)
    routes = {
        "/repos/PSyron/polis/releases": [_HttpReply(200, b"[]")],
        "/pypi/polis-nlp/json": [_HttpReply(status, b'{"releases": {}}')],
    }

    with _wire_server(routes) as server:
        result = subprocess.run(
            _candidate_command(server=server, remote=remote, state="candidate-absent"),
            text=True,
            capture_output=True,
            check=False,
            env=_cli_environment(server),
        )

    assert result.returncode != 0
    assert "/pypi/polis-nlp/json" in server.requests


@pytest.mark.parametrize(
    "github_body",
    [b"{", b'[{"tag_name": 17}]'],
    ids=["invalid-json", "invalid-schema"],
)
def test_candidate_cli_fail_closes_on_invalid_github_response(
    tmp_path: Path, github_body: bytes
) -> None:
    remote = _empty_remote(tmp_path)
    routes = {
        "/repos/PSyron/polis/releases": [_HttpReply(200, github_body)],
        "/pypi/polis-nlp/json": [_HttpReply(404, b"")],
    }

    with _wire_server(routes) as server:
        result = subprocess.run(
            _candidate_command(server=server, remote=remote, state="candidate-absent"),
            text=True,
            capture_output=True,
            check=False,
            env=_cli_environment(server),
        )

    assert result.returncode != 0
    assert server.requests == ["/repos/PSyron/polis/releases"]
