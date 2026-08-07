from __future__ import annotations

from tests.release_workflow_helpers import WORKFLOW, WORKFLOW_VALIDATOR, _run


def test_release_workflow_declares_exact_universal_compatibility_matrix() -> None:
    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(WORKFLOW), "--print-matrix")

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[-7:] == [
        "macos-15|3.12",
        "macos-15|3.14",
        "ubuntu-24.04|3.12",
        "ubuntu-24.04|3.13",
        "ubuntu-24.04|3.14",
        "windows-2025|3.12",
        "windows-2025|3.14",
    ]


def test_release_matrix_uses_a_smoke_directory_outside_the_checkout() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "SMOKE_CWD: ${{ runner.temp }}/polis-install-smoke" in workflow
    assert '--smoke-cwd "$SMOKE_CWD"' in workflow
    assert "Path('smoke-cwd').mkdir()" not in workflow


def test_release_workflow_routes_recovery_through_the_protected_upload_job() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "recover_blocked:" not in workflow
    assert "inputs.mode == 'publish' || inputs.mode == 'recover'" in workflow
    assert "release_identity.py recovery-authority" in workflow
    assert "RECOVERY_FILENAME: ${{ inputs.recovery_filename }}" in workflow
    assert '--recovery-filename "$RECOVERY_FILENAME"' in workflow
    assert (
        workflow.count(
            "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33"
        )
        == 1
    )
