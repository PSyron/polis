from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from scripts.release_identity import ReleaseIdentityError, read_release_policy
from tests.release_identity_helpers import (
    ROOT,
    _candidate_absent_checkout,
    _candidate_command,
    _cli_environment,
    _empty_remote,
    _HttpReply,
    _wire_server,
)


def test_tracked_release_policy_pins_the_approved_plan_digest() -> None:
    policy = ROOT / "docs/project/release-policy.json"

    assert policy.is_file()
    assert json.loads(policy.read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "approved_plan_sha256": (
            "98d87cec471291987d7df83fb8ee14382978349ef4f517dfec89567fdcc0d9b9"
        ),
    }


def test_candidate_cli_accepts_one_annotated_tag_bound_to_the_source(
    tmp_path: Path,
) -> None:
    remote = _empty_remote(tmp_path)
    checkout = _candidate_absent_checkout(tmp_path)
    tagged = subprocess.run(
        ["git", "tag", "-a", "v0.2.0", "-m", "candidate tag"],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    assert tagged.returncode == 0, tagged.stderr
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
            _candidate_command(
                server=server,
                remote=remote,
                state="tag-bound",
                repo=checkout,
            ),
            cwd=checkout,
            text=True,
            capture_output=True,
            check=False,
            env=_cli_environment(server),
        )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "candidate identity is available: v0.2.0\n"


def test_candidate_cli_rejects_annotated_tag_bound_to_another_commit(
    tmp_path: Path,
) -> None:
    remote = _empty_remote(tmp_path)
    checkout = _candidate_absent_checkout(tmp_path)
    tagged = subprocess.run(
        ["git", "tag", "-a", "v0.2.0", "-m", "candidate tag"],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    assert tagged.returncode == 0, tagged.stderr
    pushed = subprocess.run(
        ["git", "push", str(remote), "v0.2.0"],
        cwd=checkout,
        text=True,
        capture_output=True,
        check=False,
    )
    assert pushed.returncode == 0, pushed.stderr
    wrong_source = subprocess.check_output(
        ["git", "rev-parse", "HEAD^"], cwd=checkout, text=True
    ).strip()
    routes = {
        "/repos/PSyron/polis/releases": [_HttpReply(200, b"[]")],
        "/pypi/polis-nlp/json": [_HttpReply(404, b"")],
    }

    with _wire_server(routes) as server:
        command = _candidate_command(
            server=server,
            remote=remote,
            state="tag-bound",
            repo=checkout,
        )
        source_index = command.index("--source-commit") + 1
        command[source_index] = wrong_source
        result = subprocess.run(
            command,
            cwd=checkout,
            text=True,
            capture_output=True,
            check=False,
            env=_cli_environment(server),
        )

    assert result.returncode != 0
    assert "annotated binding" in result.stderr


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"schema_version": 1, "approved_plan_sha256": "A" * 64},
        {
            "schema_version": 2,
            "approved_plan_sha256": (
                "98d87cec471291987d7df83fb8ee14382978349ef4f517dfec89567fdcc0d9b9"
            ),
        },
        {
            "schema_version": 1,
            "approved_plan_sha256": (
                "98d87cec471291987d7df83fb8ee14382978349ef4f517dfec89567fdcc0d9b9"
            ),
            "caller_override": "different",
        },
    ],
    ids=["missing", "uppercase", "bad-schema", "override"],
)
def test_release_policy_rejects_invalid_or_overrideable_bytes(
    tmp_path: Path, payload: dict[str, str | int]
) -> None:
    policy = tmp_path / "release-policy.json"
    policy.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ReleaseIdentityError):
        read_release_policy(policy)
