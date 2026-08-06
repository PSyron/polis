from __future__ import annotations

from pathlib import Path

import pytest
from tests.release_workflow_helpers import (
    BUILD_COMMAND,
    EXACT_BUILD_COMMAND,
    QUALIFY_JOB_HEADER,
    UPLOAD_JOB_HEADER,
    WORKFLOW,
    WORKFLOW_VALIDATOR,
    _run,
)


@pytest.mark.parametrize(
    "addition",
    (
        "          user: ${{ secrets.PYPI_USER }}\n",
        "          repository-url: https://test.pypi.org/legacy/\n",
        "          skip-existing: true\n",
    ),
)
def test_release_workflow_rejects_forbidden_publication_features(
    tmp_path: Path, addition: str
) -> None:
    invalid = tmp_path / "release.yml"
    workflow = WORKFLOW.read_text(encoding="utf-8")
    invalid.write_text(
        workflow.replace(
            "          packages-dir: publish\n",
            "          packages-dir: publish\n" + addition,
            1,
        ),
        encoding="utf-8",
    )

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode != 0
    assert "upload steps" in result.stderr


@pytest.mark.parametrize(
    "destination",
    (
        "Publish only allowlisted distributions",
        "Verify authority, manifests, receipt, and stage allowlisted bytes",
    ),
)
def test_release_workflow_rejects_a_build_relocated_outside_qualify(
    tmp_path: Path, destination: str
) -> None:
    invalid = tmp_path / "release.yml"
    workflow = WORKFLOW.read_text(encoding="utf-8")
    relocated = workflow.replace(BUILD_COMMAND, "echo qualify-only", 1).replace(
        f"      - name: {destination}",
        "      - name: Illegally rebuild outside qualify\n"
        f"        run: {BUILD_COMMAND}\n"
        f"      - name: {destination}",
        1,
    )
    invalid.write_text(
        relocated,
        encoding="utf-8",
    )

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode != 0
    assert "qualify steps" in result.stderr


@pytest.mark.parametrize(
    "replacement",
    (
        f'        run: echo "{BUILD_COMMAND}"',
        f"        run: echo dead && false && {BUILD_COMMAND}",
        f"        run: |\n          exit 0;\n          {BUILD_COMMAND}",
        (
            "        run: |\n"
            "          cat <<'EOF'\n"
            f"          {BUILD_COMMAND}\n"
            "          EOF"
        ),
        f"        run: command='{BUILD_COMMAND}'",
    ),
)
def test_release_workflow_rejects_an_inert_build_command(
    tmp_path: Path, replacement: str
) -> None:
    invalid = tmp_path / "release.yml"
    workflow = WORKFLOW.read_text(encoding="utf-8")
    invalid.write_text(
        workflow.replace(f"        run: {EXACT_BUILD_COMMAND}", replacement, 1),
        encoding="utf-8",
    )

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode != 0
    assert "qualify steps" in result.stderr


@pytest.mark.parametrize(
    ("job_header", "replacement"),
    (
        (
            QUALIFY_JOB_HEADER,
            "    # needs: validate_inputs",
        ),
        (
            QUALIFY_JOB_HEADER,
            "    # needs: validate_inputs\n    needs: 17",
        ),
        (
            QUALIFY_JOB_HEADER,
            "    # needs: validate_inputs\n    needs: [validate_inputs]",
        ),
        (
            QUALIFY_JOB_HEADER,
            "    # needs: validate_inputs\n    needs: [validate_inputs, qualify]",
        ),
        (
            UPLOAD_JOB_HEADER,
            "    # needs: validate_inputs",
        ),
        (
            UPLOAD_JOB_HEADER,
            "    # needs: validate_inputs\n    needs: 17",
        ),
        (
            UPLOAD_JOB_HEADER,
            "    # needs: validate_inputs\n    needs: [validate_inputs]",
        ),
        (
            UPLOAD_JOB_HEADER,
            "    # needs: validate_inputs\n    needs: [validate_inputs, qualify]",
        ),
    ),
)
def test_release_workflow_rejects_noncanonical_job_dependencies(
    tmp_path: Path, job_header: str, replacement: str
) -> None:
    invalid = tmp_path / "release.yml"
    workflow = WORKFLOW.read_text(encoding="utf-8")
    needle = f"{job_header}\n    needs: validate_inputs"
    assert needle in workflow
    invalid.write_text(
        workflow.replace(needle, f"{job_header}\n{replacement}", 1),
        encoding="utf-8",
    )

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode != 0
    semantic_class = "qualify job" if job_header == QUALIFY_JOB_HEADER else "upload job"
    assert semantic_class in result.stderr


@pytest.mark.parametrize("permission", ("actions: read", "id-token: write"))
def test_release_workflow_rejects_upload_permissions_relocated_to_qualify(
    tmp_path: Path, permission: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    invalid = tmp_path / "release.yml"
    qualify_permissions = (
        f"    permissions:\n      contents: read\n      {permission}\n"
    )
    without_upload_permission = workflow.replace(f"      {permission}\n", "", 1)
    invalid.write_text(
        without_upload_permission.replace(
            "    runs-on: macos-15\n",
            "    runs-on: macos-15\n" + qualify_permissions,
            1,
        ),
        encoding="utf-8",
    )

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode != 0
    assert "qualify job" in result.stderr
    assert "upload job" in result.stderr


def test_release_workflow_rejects_a_commented_upload_environment(
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "release.yml"
    invalid.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "    environment: pypi\n", "    # environment: pypi\n", 1
        ),
        encoding="utf-8",
    )

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode != 0
    assert "upload job" in result.stderr


def test_release_workflow_rejects_disabled_remote_main_bindings(
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "release.yml"
    workflow = WORKFLOW.read_text(encoding="utf-8")
    disabled = workflow.replace(
        "          git fetch --no-tags origin main\n",
        "          # git fetch --no-tags origin main\n",
    ).replace(
        '          test "$(git rev-parse refs/remotes/origin/main)" = '
        '"${{ inputs.source_commit }}"\n',
        '          # test "$(git rev-parse refs/remotes/origin/main)" = '
        '"${{ inputs.source_commit }}"\n'
        "          true\n",
    )
    invalid.write_text(disabled, encoding="utf-8")

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode != 0
    assert "qualify steps" in result.stderr
    assert "upload steps" in result.stderr
