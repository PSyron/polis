from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from tests.release_workflow_helpers import (
    ENVIRONMENT_VALIDATOR,
    FIXTURES,
    INPUT_VALIDATOR,
    SOURCE_COMMIT,
    _run,
)


def test_release_environment_rejects_a_ruleset_list_instead_of_read_back(
    tmp_path: Path,
) -> None:
    ruleset_list = tmp_path / "rulesets.json"
    ruleset_list.write_text(
        json.dumps(
            {
                "total_count": 1,
                "rulesets": [
                    json.loads(
                        (FIXTURES / "ruleset-valid.json").read_text(encoding="utf-8")
                    )
                ],
            }
        ),
        encoding="utf-8",
    )

    result = _environment_command(
        FIXTURES / "environment-valid.json",
        FIXTURES / "branch-policies-valid.json",
        ruleset_list,
    )

    assert result.returncode != 0
    assert "active" in result.stderr


@pytest.mark.parametrize(
    ("mode", "artifact", "receipt", "recovery", "valid"),
    (
        ("qualify", "", "", "", True),
        ("publish", "17", '{"receipt":1}', "", True),
        ("recover", "17", '{"receipt":1}', "polis_nlp-0.2.0.tar.gz", True),
        ("other", "", "", "", False),
        ("qualify", "17", "", "", False),
        ("qualify", "", '{"receipt":1}', "", False),
        ("publish", "", '{"receipt":1}', "", False),
        ("publish", "17", '{ "receipt": 1 }', "", False),
        ("publish", "17", '{"receipt":1}', "file.whl", False),
        ("recover", "17", '{"receipt":1}', "", False),
    ),
)
def test_release_inputs_are_disjoint_and_compact(
    mode: str, artifact: str, receipt: str, recovery: str, valid: bool
) -> None:
    result = _run(
        INPUT_VALIDATOR,
        "--mode",
        mode,
        "--source-commit",
        SOURCE_COMMIT,
        "--artifact-run-id",
        artifact,
        "--gate-receipt-json",
        receipt,
        "--recovery-filename",
        recovery,
    )

    assert (result.returncode == 0) is valid


def _environment_command(
    environment: Path, branches: Path, ruleset: Path
) -> subprocess.CompletedProcess[str]:
    return _run(
        ENVIRONMENT_VALIDATOR,
        "--environment",
        str(environment),
        "--branch-policies",
        str(branches),
        "--ruleset",
        str(ruleset),
        "--reviewer",
        "PSyron",
        "--branch",
        "main",
        "--tag-pattern",
        "refs/tags/v*",
    )


def test_release_environment_contract_is_valid() -> None:
    result = _environment_command(
        FIXTURES / "environment-valid.json",
        FIXTURES / "branch-policies-valid.json",
        FIXTURES / "ruleset-valid.json",
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "release environment contract is valid\n"


@pytest.mark.parametrize(
    ("fixture", "path", "value", "error"),
    (
        ("environment", ("name",), "other", "environment name"),
        (
            "environment",
            ("protection_rules", 0, "prevent_self_review"),
            True,
            "self review",
        ),
        (
            "environment",
            ("protection_rules", 0, "reviewers", 0, "reviewer", "login"),
            "Other",
            "reviewer",
        ),
        ("branches", ("branch_policies", 0, "name"), "release", "branch policy"),
        ("ruleset", ("enforcement",), "disabled", "active"),
        (
            "ruleset",
            ("conditions", "ref_name", "include"),
            ["refs/tags/test*"],
            "tag pattern",
        ),
        (
            "ruleset",
            ("bypass_actors", 0, "actor_type"),
            "Integration",
            "workflow actor bypass",
        ),
    ),
)
def test_release_environment_rejects_inactive_or_wrong_protection(
    tmp_path: Path,
    fixture: str,
    path: tuple[str | int, ...],
    value: str | bool | list[str],
    error: str,
) -> None:
    files = {
        "environment": FIXTURES / "environment-valid.json",
        "branches": FIXTURES / "branch-policies-valid.json",
        "ruleset": FIXTURES / "ruleset-valid.json",
    }
    payload = json.loads(files[fixture].read_text(encoding="utf-8"))
    target = payload
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    invalid = tmp_path / f"{fixture}.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")
    files[fixture] = invalid

    result = _environment_command(
        files["environment"], files["branches"], files["ruleset"]
    )

    assert result.returncode != 0
    assert error in result.stderr
