from __future__ import annotations

from pathlib import Path

import pytest
from tests.release_workflow_helpers import WORKFLOW, WORKFLOW_VALIDATOR, _run


def test_release_workflow_contract_is_valid() -> None:
    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(WORKFLOW))

    assert result.returncode == 0, result.stderr
    assert result.stdout == "release workflow contract is valid\n"


def test_release_workflow_rejects_malformed_yaml(tmp_path: Path) -> None:
    invalid = tmp_path / "release.yml"
    invalid.write_text("jobs: [\n", encoding="utf-8")

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode == 1
    assert "YAML is invalid" in result.stderr


@pytest.mark.parametrize(
    ("needle", "replacement", "semantic_class"),
    (
        (
            "          - recover\n",
            "          - recover\n          - emergency\n",
            "dispatch",
        ),
        (
            "          - qualify\n          - publish\n          - recover\n",
            "          - publish\n          - qualify\n          - recover\n",
            "dispatch",
        ),
        (
            "        type: choice\n        options:",
            "        type: string\n        # type: choice\n        options:",
            "dispatch",
        ),
        (
            "      source_commit:\n",
            "      extra_input:\n        required: false\n        type: string\n"
            "      source_commit:\n",
            "dispatch",
        ),
        (
            "        required: true\n        type: string\n      artifact_run_id:",
            "        required: false\n        type: string\n      artifact_run_id:",
            "dispatch",
        ),
        (
            "concurrency:\n  group: polis-release\n  cancel-in-progress: false\n",
            "concurrency:\n  group: polis-release\n  cancel-in-progress: false\n"
            "  unexpected: true\n",
            "concurrency",
        ),
        ("permissions:\n", "unexpected-root: true\n\npermissions:\n", "root"),
        (
            "  validate_inputs:\n    runs-on:",
            "  unexpected_job:\n    runs-on: ubuntu-24.04\n\n"
            "  validate_inputs:\n    runs-on:",
            "job inventory",
        ),
        (
            "  validate_inputs:\n    runs-on: ubuntu-24.04",
            "  validate_inputs:\n    if: false\n    runs-on: ubuntu-24.04",
            "validate_inputs job",
        ),
        (
            "  qualify:\n    if: ${{ inputs.mode == 'qualify' }}",
            "  qualify:\n    if: ${{ inputs.mode == 'qualify' }}\n    unexpected: true",
            "qualify job",
        ),
        (
            "    runs-on: macos-15\n    steps:",
            "    runs-on: ubuntu-24.04\n    steps:",
            "qualify job",
        ),
        (
            "      - name: Validate disjoint inputs\n        env:",
            "      - name: Validate disjoint inputs\n        if: false\n        env:",
            "validate_inputs steps",
        ),
        (
            "      - name: Prepare locked wheelhouse\n        run:",
            "      - name: Prepare locked wheelhouse\n        if: false\n        run:",
            "qualify steps",
        ),
        (
            "      - name: Verify the existing build and write its manifest\n"
            "        run:",
            "      - name: Verify the existing build and write its manifest\n"
            "        if: false\n        run:",
            "qualify steps",
        ),
        (
            "      - name: Verify both public manifests and offline installation\n"
            "        shell:",
            "      - name: Verify both public manifests and offline installation\n"
            "        if: false\n        shell:",
            "verify_bundle steps",
        ),
        (
            "      - name: Verify authority, manifests, receipt, and stage "
            "allowlisted bytes\n        env:",
            "      - name: Verify authority, manifests, receipt, and stage "
            "allowlisted bytes\n        if: false\n        env:",
            "upload steps",
        ),
        (
            "      - name: Publish only allowlisted distributions\n        uses:",
            "      - name: Publish only allowlisted distributions\n"
            "        if: false\n        uses:",
            "upload steps",
        ),
        (
            "          repository: ${{ github.repository }}\n",
            "          repository: other/repository\n"
            "          # repository: ${{ github.repository }}\n",
            "upload steps",
        ),
        (
            "          run-id: ${{ inputs.artifact_run_id }}\n",
            "          run-id: 17\n          # run-id: ${{ inputs.artifact_run_id }}\n",
            "upload steps",
        ),
        (
            "          github-token: ${{ github.token }}\n",
            "          github-token: wrong\n"
            "          # github-token: ${{ github.token }}\n",
            "upload steps",
        ),
        (
            "permissions:\n  contents: read\n",
            "permissions:\n  contents: read\n  id-token: write\n",
            "permissions",
        ),
        (
            '          - os: windows-2025\n            python-version: "3.14"\n',
            '          - os: windows-2025\n            python-version: "3.14"\n'
            '          - os: windows-2025\n            python-version: "3.14"\n',
            "verify_bundle matrix",
        ),
        (
            "      - name: Validate disjoint inputs\n",
            "      - name: Harmless extra step\n        run: true\n"
            "      - name: Validate disjoint inputs\n",
            "validate_inputs steps",
        ),
        (
            "      - name: Validate disjoint inputs\n        env:",
            "      - name: Validate disjoint inputs\n        unexpected: true\n"
            "        env:",
            "validate_inputs steps",
        ),
    ),
)
def test_release_workflow_rejects_closed_semantic_mutations(
    tmp_path: Path, needle: str, replacement: str, semantic_class: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert needle in workflow
    invalid = tmp_path / "release.yml"
    invalid.write_text(workflow.replace(needle, replacement, 1), encoding="utf-8")

    result = _run(WORKFLOW_VALIDATOR, "--workflow", str(invalid))

    assert result.returncode != 0
    assert semantic_class in result.stderr
