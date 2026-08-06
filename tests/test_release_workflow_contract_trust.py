from __future__ import annotations

from pathlib import Path

import pytest
from tests.release_workflow_helpers import WORKFLOW, WORKFLOW_VALIDATOR, _run


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
