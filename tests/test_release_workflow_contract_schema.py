from __future__ import annotations

from pathlib import Path

import pytest
from tests.release_workflow_helpers import (
    WORKFLOW,
    WORKFLOW_VALIDATOR,
    _replace_occurrence,
    _run,
)


@pytest.mark.parametrize(
    ("needle", "replacement"),
    (
        ("        type: choice\n", "        type: string\n"),
        (
            "        type: string\n      artifact_run_id:",
            "        type: boolean\n      artifact_run_id:",
        ),
        (
            "      artifact_run_id:\n",
            "      artifact_run_id:\n        unexpected: true\n",
        ),
        (
            "      gate_receipt_json:\n",
            "      gate_receipt_json:\n        required: true\n",
        ),
        (
            "      recovery_filename:\n",
            "      recovery_filename:\n        options: [missing]\n",
        ),
    ),
)
def test_release_workflow_rejects_each_input_schema_mutation(
    tmp_path: Path, needle: str, replacement: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert needle in workflow
    invalid = tmp_path / "release.yml"
    invalid.write_text(workflow.replace(needle, replacement, 1), encoding="utf-8")

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode == 1
    assert "dispatch" in result.stderr


@pytest.mark.parametrize(
    "replacement",
    (
        "actions/checkout@main",
        "actions/checkout@v4",
        "docker://alpine:3.22",
        "./local-action",
    ),
)
def test_release_workflow_rejects_nonreviewed_action_forms(
    tmp_path: Path, replacement: str
) -> None:
    canonical = "actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5"
    workflow = WORKFLOW.read_text(encoding="utf-8")
    invalid = tmp_path / "release.yml"
    invalid.write_text(workflow.replace(canonical, replacement, 1), encoding="utf-8")

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode == 1
    assert "validate_inputs steps" in result.stderr


@pytest.mark.parametrize(
    "job",
    ("validate_inputs", "qualify", "verify_bundle", "upload"),
)
def test_release_workflow_rejects_a_missing_named_job(tmp_path: Path, job: str) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    invalid = tmp_path / "release.yml"
    invalid.write_text(
        workflow.replace(f"  {job}:\n", f"  renamed_{job}:\n", 1),
        encoding="utf-8",
    )

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode == 1
    assert "job inventory" in result.stderr


@pytest.mark.parametrize(
    ("needle", "replacement", "semantic_class"),
    (
        (
            '          - os: ubuntu-24.04\n            python-version: "3.12"\n',
            "",
            "verify_bundle matrix",
        ),
        ("os: ubuntu-24.04", "os: ubuntu-latest", "verify_bundle matrix"),
        ('python-version: "3.13"', 'python-version: "3.11"', "verify_bundle matrix"),
        ("runs-on: ${{ matrix.os }}", "runs-on: ubuntu-24.04", "verify_bundle job"),
    ),
)
def test_release_workflow_rejects_matrix_shape_mutations(
    tmp_path: Path, needle: str, replacement: str, semantic_class: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    invalid = tmp_path / "release.yml"
    invalid.write_text(workflow.replace(needle, replacement, 1), encoding="utf-8")

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode == 1
    assert semantic_class in result.stderr


@pytest.mark.parametrize(
    ("name", "occurrence", "semantic_class"),
    (
        ("Check out exact source", 0, "validate_inputs steps"),
        ("Validate disjoint inputs", 0, "validate_inputs steps"),
        ("Check out exact source", 1, "qualify steps"),
        ("Set up CPython", 0, "qualify steps"),
        ("Set up uv", 0, "qualify steps"),
        ("Synchronize locked tools", 0, "qualify steps"),
        ("Require remote main binding", 0, "qualify steps"),
        ("Prepare locked wheelhouse", 0, "qualify steps"),
        ("Build exactly once", 0, "qualify steps"),
        ("Verify the existing build and write its manifest", 0, "qualify steps"),
        ("Assemble exact transfer bundle", 0, "qualify steps"),
        ("Upload immutable transfer bundle", 0, "qualify steps"),
        ("Check out exact source", 2, "verify_bundle steps"),
        ("Set up CPython", 1, "verify_bundle steps"),
        ("Set up uv", 1, "verify_bundle steps"),
        ("Synchronize locked tools", 1, "verify_bundle steps"),
        ("Download build-once bundle", 0, "verify_bundle steps"),
        (
            "Verify both public manifests and offline installation",
            0,
            "verify_bundle steps",
        ),
        ("Check out exact source", 3, "upload steps"),
        ("Set up CPython", 2, "upload steps"),
        ("Set up uv", 2, "upload steps"),
        ("Synchronize locked tools", 2, "upload steps"),
        ("Require unchanged remote main", 0, "upload steps"),
        ("Read original qualify run metadata", 0, "upload steps"),
        ("Download original qualify bundle", 0, "upload steps"),
        (
            "Verify authority, manifests, receipt, and stage allowlisted bytes",
            0,
            "upload steps",
        ),
        ("Publish only allowlisted distributions", 0, "upload steps"),
    ),
)
def test_release_workflow_rejects_if_false_on_every_mandatory_step(
    tmp_path: Path, name: str, occurrence: int, semantic_class: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    needle = f"      - name: {name}\n"
    replacement = f"      - name: {name}\n        if: false\n"
    invalid = tmp_path / "release.yml"
    invalid.write_text(
        _replace_occurrence(workflow, needle, replacement, occurrence),
        encoding="utf-8",
    )

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode == 1
    assert semantic_class in result.stderr
