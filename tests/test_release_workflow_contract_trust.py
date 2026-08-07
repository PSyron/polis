from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from tests.release_workflow_helpers import (
    INPUT_VALIDATOR,
    ROOT,
    WORKFLOW,
    WORKFLOW_VALIDATOR,
    _run,
)


def _ruby_failure_environment(tmp_path: Path, detail: str) -> dict[str, str]:
    ruby = shutil.which("ruby")
    assert ruby is not None
    fake_ruby = tmp_path / "ruby"
    fake_ruby.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        "  *-rdigest/sha2*)\n"
        f"    printf {shlex.quote(detail + chr(10))} >&2\n"
        "    exit 7\n"
        "    ;;\n"
        "esac\n"
        f'exec {shlex.quote(ruby)} "$@"\n',
        encoding="utf-8",
    )
    fake_ruby.chmod(0o755)
    return os.environ | {"PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}


@pytest.mark.parametrize(
    ("needle", "replacement", "semantic_class"),
    (
        (
            "python scripts/validate_release_inputs.py",
            "echo disabled && python scripts/validate_release_inputs.py",
            "validate_inputs steps",
        ),
        (
            "python scripts/prepare_build_wheelhouse.py",
            "echo disabled && python scripts/prepare_build_wheelhouse.py",
            "qualify steps",
        ),
        (
            "python scripts/verify_prerelease_candidate.py",
            "echo disabled && python scripts/verify_prerelease_candidate.py",
            "qualify steps",
        ),
        (
            "release_identity.py verify-manifest",
            "echo disabled && release_identity.py verify-manifest",
            "verify_bundle steps",
        ),
        (
            "validate_wheelhouse(Path('bundle/wheelhouse-manifest.json')",
            "False and validate_wheelhouse(Path('bundle/wheelhouse-manifest.json')",
            "verify_bundle steps",
        ),
        (
            "release_identity.py candidate",
            "echo disabled && release_identity.py candidate",
            "upload steps",
        ),
        (
            "release_identity.py recovery-authority",
            "echo disabled && release_identity.py recovery-authority",
            "upload steps",
        ),
        (
            "scripts/validate_release_gate_receipt.py validate",
            "echo disabled && scripts/validate_release_gate_receipt.py validate",
            "upload steps",
        ),
        (
            "scripts/stage_release_upload.py",
            "echo disabled && scripts/stage_release_upload.py",
            "upload steps",
        ),
        (
            "packages-dir: publish",
            "packages-dir: bundle/release-manifest.json",
            "upload steps",
        ),
    ),
)
def test_release_workflow_rejects_disabled_trust_critical_commands(
    tmp_path: Path, needle: str, replacement: str, semantic_class: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert needle in workflow
    invalid = tmp_path / "release.yml"
    invalid.write_text(workflow.replace(needle, replacement, 1), encoding="utf-8")

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode == 1
    assert semantic_class in result.stderr


@pytest.mark.parametrize(
    ("needle", "replacement", "error"),
    (
        ("group: polis-release", "group: other-release", "concurrency"),
        ("cancel-in-progress: false", "cancel-in-progress: true", "concurrency"),
        ("workflow_dispatch:", "push:", "dispatch"),
        (
            "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5",
            "actions/checkout@v4",
            "validate_inputs steps",
        ),
        (
            "uv run --locked --extra dev python -m build --no-isolation",
            "uv run --locked --extra dev python -m build",
            "qualify steps",
        ),
        ("runs-on: ${{ matrix.os }}", "runs-on: ubuntu-latest", "verify_bundle job"),
        ("environment: pypi", "environment: staging", "upload job"),
        ("id-token: write", "id-token: read", "upload job"),
        ("actions: read", "actions: write", "upload job"),
        ("--wheelhouse-manifest", "--not-wheelhouse-manifest", "qualify steps"),
        ("--state tag-bound", "--state candidate-absent", "upload steps"),
        (
            "scripts/validate_release_gate_receipt.py",
            "scripts/not-a-receipt-validator.py",
            "upload steps",
        ),
        (
            "scripts/stage_release_upload.py",
            "scripts/not-a-stager.py",
            "upload steps",
        ),
        ("needs: validate_inputs", "needs: qualify", "qualify job"),
        ("refs/remotes/origin/main", "refs/remotes/origin/other", "qualify steps"),
        (
            "https://pypi.org/pypi/polis-nlp/json",
            "https://pypi.org/pypi/other/json",
            "upload steps",
        ),
        ("packages-dir: publish", "packages-dir: bundle", "upload steps"),
    ),
)
def test_release_workflow_rejects_security_contract_mutations(
    tmp_path: Path, needle: str, replacement: str, error: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert needle in workflow
    invalid = tmp_path / "release.yml"
    invalid.write_text(workflow.replace(needle, replacement, 1), encoding="utf-8")

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode != 0
    assert error in result.stderr


def test_release_workflow_rejects_direct_dispatch_input_in_shell_run(
    tmp_path: Path,
) -> None:
    # Given: a shell step interpolates a dispatch input whose value may be shell syntax.
    workflow = WORKFLOW.read_text(encoding="utf-8")
    unsafe_step = (
        "      - name: Unsafe dispatch input\n"
        '        run: echo "${{ inputs.gate_receipt_json }}"\n'
    )
    invalid = tmp_path / "release.yml"
    invalid.write_text(
        workflow.replace("  qualify:\n", f"{unsafe_step}  qualify:\n", 1),
        encoding="utf-8",
    )

    # When: the release workflow contract is validated.
    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    # Then: validation rejects the shell boundary without executing the payload.
    assert result.returncode == 1
    assert (
        "release shell run uses direct dispatch input at "
        "jobs.validate_inputs.steps[2].run: inputs.gate_receipt_json"
    ) in result.stderr


def test_release_workflow_keeps_ruby_failure_detail(tmp_path: Path) -> None:
    environment = _ruby_failure_environment(tmp_path, "Ruby parser rejected input")

    result = subprocess.run(
        [sys.executable, str(WORKFLOW_VALIDATOR), "--workflow", str(WORKFLOW)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 1
    assert (
        result.stderr
        == "release workflow YAML is invalid: Ruby parser rejected input\n"
    )


def test_release_workflow_rejects_ruby_failure_without_stderr(tmp_path: Path) -> None:
    environment = _ruby_failure_environment(tmp_path, "")

    result = subprocess.run(
        [sys.executable, str(WORKFLOW_VALIDATOR), "--workflow", str(WORKFLOW)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 1
    assert (
        result.stderr
        == "release workflow YAML is invalid: Ruby parser failed without a diagnostic\n"
    )
    assert "Traceback" not in result.stderr
    assert "IndexError" not in result.stderr


def test_release_input_validator_rejects_shell_payload_as_data(
    tmp_path: Path,
) -> None:
    sentinel = tmp_path / "sentinel"
    payload = f"$(touch {sentinel})"
    environment = os.environ.copy()
    environment["SOURCE_COMMIT"] = payload
    command = (
        f"{shlex.quote(sys.executable)} {shlex.quote(str(INPUT_VALIDATOR))} "
        '--mode qualify --source-commit "$SOURCE_COMMIT"'
    )

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 1
    assert result.stderr == "source commit must be a lowercase 40-character SHA\n"
    assert not sentinel.exists()


def test_release_workflow_allows_dispatch_input_in_non_shell_with_run(
    tmp_path: Path,
) -> None:
    # Given: an action input happens to be named run but is not a shell step.
    workflow = WORKFLOW.read_text(encoding="utf-8")
    invalid_contract = tmp_path / "release.yml"
    invalid_contract.write_text(
        workflow.replace(
            "          ref: ${{ inputs.source_commit }}",
            "          run: ${{ inputs.source_commit }}",
            1,
        ),
        encoding="utf-8",
    )

    # When: the mutated workflow contract is validated.
    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid_contract))

    # Then: only the pinned contract rejects it, not the shell-input boundary.
    assert result.returncode == 1
    assert "release validate_inputs steps semantic contract is invalid" in result.stderr
    assert "release shell run uses direct dispatch input" not in result.stderr
