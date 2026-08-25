from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from scripts.validate_fast_ci_workflow import _strip_unquoted_shell_comment

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts/validate_fast_ci_workflow.py"
WORKFLOW = ROOT / ".github/workflows/fast-ci.yml"
PYPROJECT = ROOT / "pyproject.toml"
LICENSE_REVIEW = ROOT / "docs/development/dependency-licenses.md"
COMPATIBILITY_POLICY = ROOT / "docs/compatibility.md"
DISTRIBUTION_VERIFICATION = ROOT / "docs/distribution-verification.md"
BYTE_STABLE_TEXT_PATHS = (
    "experiments/languagetool_stdio_session/config.json",
    "tests/fixtures/evaluation/polish_correction_corpus_v3.json",
    "third_party/languagetool-pl/manifest.json",
)
BYTE_EXACT_UPSTREAM_PATHS = ("third_party/languagetool-pl/LICENSE-LGPL-2.1.txt",)
FAST_PYTEST_COMMAND = (
    'run: uv run --locked --extra dev pytest -m "not research and not slow"'
)
FAST_PYTEST_FILTER = 'pytest -m "not research and not slow"'
GENERATIVE_CONFIGURATION = (
    ("POLIS_GENERATIVE_GENERATOR_VERSION", "unicode-structural-v1"),
    ("POLIS_GENERATIVE_SEED", "95001"),
    ("POLIS_GENERATIVE_CASES", "64"),
)
GENERATIVE_ENVIRONMENT_BLOCK = (
    "        env:\n"
    "          POLIS_GENERATIVE_GENERATOR_VERSION: unicode-structural-v1\n"
    "          POLIS_GENERATIVE_SEED: 95001\n"
    "          POLIS_GENERATIVE_CASES: 64\n"
)


def run_validator(workflow: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(VALIDATOR)]
    if workflow is not None:
        command.extend(["--workflow", str(workflow)])
    return subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False
    )


def write_workflow(tmp_path: Path, workflow: str) -> Path:
    path = tmp_path / "fast-ci.yml"
    path.write_text(workflow, encoding="utf-8")
    return path


def test_fast_ci_contract_is_valid() -> None:
    result = run_validator()

    assert result.returncode == 0, result.stderr
    assert result.stdout == "fast CI workflow contract is valid\n"


def test_fast_ci_contract_rejects_nonexistent_workflow(tmp_path: Path) -> None:
    missing_workflow = tmp_path / "missing-fast-ci.yml"

    result = run_validator(missing_workflow)

    assert result.returncode != 0
    assert result.stderr == f"workflow does not exist: {missing_workflow}\n"


def test_fast_ci_contract_rejects_malformed_yaml(tmp_path: Path) -> None:
    malformed_workflow = tmp_path / "fast-ci.yml"
    malformed_workflow.write_text("jobs: [\n", encoding="utf-8")

    result = run_validator(malformed_workflow)

    assert result.returncode != 0
    assert result.stderr.startswith("YAML syntax validation failed:")
    assert "Traceback" not in result.stderr
    assert ".rb:" not in result.stderr
    assert "psych" not in result.stderr.lower()


def test_fast_ci_contract_rejects_triggers_present_only_in_comments(
    tmp_path: Path,
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        "on:\n  push:\n  pull_request:\n",
        "on:\n  workflow_dispatch:\n# push:\n# pull_request:\n",
        1,
    )

    result = run_validator(write_workflow(tmp_path, workflow))

    assert result.returncode != 0
    assert "unexpected workflow trigger" in result.stderr


def test_fast_ci_contract_rejects_duplicate_root_permissions(tmp_path: Path) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        "permissions:\n  contents: read\n",
        "permissions:\n  contents: read\npermissions:\n  contents: write\n",
        1,
    )

    result = run_validator(write_workflow(tmp_path, workflow))

    assert result.returncode != 0
    assert "duplicate YAML mapping key" in result.stderr


@pytest.mark.parametrize(
    ("workflow", "expected_error"),
    (
        (
            WORKFLOW.read_text(encoding="utf-8").replace("name: Fast CI\n", "", 1),
            "unexpected workflow root key",
        ),
        (
            WORKFLOW.read_text(encoding="utf-8").replace(
                "name: Fast CI\n", "name: Fast CI\nconcurrency: fast-ci\n", 1
            ),
            "unexpected workflow root key",
        ),
        (
            WORKFLOW.read_text(encoding="utf-8").replace(
                "contents: read", "contents: write", 1
            ),
            "unexpected workflow permissions",
        ),
        (
            WORKFLOW.read_text(encoding="utf-8").replace(
                "on:\n  push:\n  pull_request:\n",
                "on:\n  workflow_dispatch:\non:\n  push:\n  pull_request:\n",
                1,
            ),
            "duplicate YAML mapping key",
        ),
    ),
)
def test_fast_ci_contract_rejects_root_policy_drift(
    tmp_path: Path, workflow: str, expected_error: str
) -> None:
    result = run_validator(write_workflow(tmp_path, workflow))

    assert result.returncode != 0
    assert expected_error in result.stderr


def test_fast_ci_contract_rejects_fake_uv_added_through_github_path(
    tmp_path: Path,
) -> None:
    attack = (
        "      - name: Shadow uv\n"
        "        run: |\n"
        '          mkdir -p "${{ runner.temp }}/fake-bin"\n'
        "          printf '#!/bin/sh\\nexit 0\\n' > "
        '"${{ runner.temp }}/fake-bin/uv"\n'
        '          chmod +x "${{ runner.temp }}/fake-bin/uv"\n'
        '          echo "${{ runner.temp }}/fake-bin" >> "$GITHUB_PATH"\n'
    )
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        "      - name: Synchronize locked development environment\n",
        attack + "      - name: Synchronize locked development environment\n",
        1,
    )

    result = run_validator(write_workflow(tmp_path, workflow))

    assert result.returncode != 0
    assert "unexpected quality step" in result.stderr


@pytest.mark.parametrize(
    "modifier",
    (
        "    if: false\n",
        "    continue-on-error: true\n",
        "    defaults:\n      run:\n        shell: bash\n",
        "    defaults:\n      run:\n        working-directory: /tmp\n",
    ),
)
def test_fast_ci_contract_rejects_unsafe_quality_job_modifier(
    tmp_path: Path, modifier: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        "    strategy:\n", modifier + "    strategy:\n", 1
    )

    result = run_validator(write_workflow(tmp_path, workflow))

    assert result.returncode != 0
    assert "unexpected quality job key" in result.stderr


@pytest.mark.parametrize(
    ("modifier", "value"),
    (
        ("if", "false"),
        ("continue-on-error", "true"),
        ("shell", "bash"),
        ("working-directory", "/tmp"),
    ),
)
def test_fast_ci_contract_rejects_unsafe_quality_step_modifier(
    tmp_path: Path, modifier: str, value: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        "      - name: Run Ruff lint\n        run:",
        f"      - name: Run Ruff lint\n        {modifier}: {value}\n        run:",
        1,
    )

    result = run_validator(write_workflow(tmp_path, workflow))

    assert result.returncode != 0
    assert "unexpected quality step" in result.stderr


@pytest.mark.parametrize("scope", ("job", "step"))
def test_fast_ci_contract_rejects_path_environment_shadowing(
    tmp_path: Path, scope: str
) -> None:
    match scope:
        case "job":
            workflow = WORKFLOW.read_text(encoding="utf-8").replace(
                "    strategy:\n",
                "    env:\n      PATH: /tmp/fake-bin\n    strategy:\n",
                1,
            )
        case "step":
            workflow = WORKFLOW.read_text(encoding="utf-8").replace(
                "        env:\n",
                "        env:\n          PATH: /tmp/fake-bin\n",
                1,
            )
        case unreachable:
            pytest.fail(f"unexpected mutation scope: {unreachable}")

    result = run_validator(write_workflow(tmp_path, workflow))

    assert result.returncode != 0
    assert (
        "unexpected quality job key"
        if scope == "job"
        else "unexpected environment entry"
    ) in result.stderr


@pytest.mark.parametrize("name", ("PATH", "GITHUB_PATH"))
def test_fast_ci_contract_rejects_workflow_root_path_environment_shadowing(
    tmp_path: Path, name: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        "permissions:\n  contents: read\n",
        f"permissions:\n  contents: read\nenv:\n  {name}: /tmp/fake-bin\n",
        1,
    )

    result = run_validator(write_workflow(tmp_path, workflow))

    assert result.returncode != 0
    assert "unexpected workflow root key" in result.stderr


@pytest.mark.parametrize(
    ("name", "value"),
    (("shell", "bash"), ("working-directory", "/tmp")),
)
def test_fast_ci_contract_rejects_workflow_root_defaults_modifier(
    tmp_path: Path, name: str, value: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        "permissions:\n  contents: read\n",
        f"permissions:\n  contents: read\ndefaults:\n  run:\n    {name}: {value}\n",
        1,
    )

    result = run_validator(write_workflow(tmp_path, workflow))

    assert result.returncode != 0
    assert "unexpected workflow root key" in result.stderr


@pytest.mark.parametrize("name", ("PATH", "GITHUB_PATH"))
def test_fast_ci_contract_rejects_unexpected_pytest_environment_entry(
    tmp_path: Path, name: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        "          POLIS_GENERATIVE_CASES: 64\n",
        f"          POLIS_GENERATIVE_CASES: 64\n          {name}: /tmp/fake-bin\n",
        1,
    )

    result = run_validator(write_workflow(tmp_path, workflow))

    assert result.returncode != 0
    assert "unexpected environment entry" in result.stderr


@pytest.mark.parametrize(
    "step",
    (
        "      - name: Unexpected run\n        run: true\n",
        "      - name: Unexpected action\n"
        "        uses: actions/cache@34e114876b0b11c390a56381ad16ebd13914f8d5\n",
    ),
)
def test_fast_ci_contract_rejects_unexpected_quality_step(
    tmp_path: Path, step: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        "      - name: Synchronize locked development environment\n",
        step + "      - name: Synchronize locked development environment\n",
        1,
    )

    result = run_validator(write_workflow(tmp_path, workflow))

    assert result.returncode != 0
    assert "unexpected quality step" in result.stderr


def test_fast_ci_runs_public_offline_install_and_documentation_validator() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "scripts/prepare_build_wheelhouse.py" in workflow
    assert "scripts/verify_distribution_install.py" in workflow
    assert "--smoke-cwd" in workflow
    assert "scripts/validate_documentation_inventory.py" in workflow
    assert (
        "scripts/validate_release_workflow.py --workflow .github/workflows/release.yml"
        in workflow
    )


def test_fast_ci_contract_requires_full_tag_history_for_release_evidence() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "fetch-depth: 0" in workflow
    assert "fetch-tags: true" in workflow


def test_v1_static_tool_inputs_exclude_archived_experiments_and_model_marker() -> None:
    configuration = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    marker_names = {
        marker.partition(":")[0]
        for marker in configuration["tool"]["pytest"]["ini_options"]["markers"]
    }

    assert (
        "experiments/sentence_safety_gate_v2/**/*.py"
        not in configuration["tool"]["ruff"]["include"]
    )
    assert configuration["tool"]["mypy"]["files"] == ["src", "tests"]
    assert marker_names == {"research", "slow"}


def test_fast_ci_contract_rejects_a_missing_required_matrix_entry(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace("macos-15", "macos-latest"),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "missing required matrix entry" in result.stderr


def test_fast_ci_contract_rejects_non_macos_intermediate_runner(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "- os: macos-15", "- os: ubuntu-24.04", 1
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "intermediate Fast CI must use macOS runners only: ubuntu-24.04" in (
        result.stderr
    )


def test_fast_ci_contract_rejects_x86_64_for_setup_python(tmp_path: Path) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "architecture: ${{ matrix.setup-python-architecture }}",
            "architecture: x86_64",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "setup-python architecture" in result.stderr


def test_fast_ci_contract_rejects_invalid_action_architecture(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "setup-python-architecture: arm64",
            "setup-python-architecture: x86_64",
            1,
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "invalid setup-python architecture value: x86_64" in result.stderr


def test_fast_ci_contract_rejects_wrong_policy_to_action_mapping(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "setup-python-architecture: arm64",
            "setup-python-architecture: x86",
            1,
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "arm64 -> x86" in result.stderr


def test_fast_ci_contract_rejects_an_unfiltered_pytest_command(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            FAST_PYTEST_FILTER,
            'pytest -m "not slow and not model"',
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "fast pytest marker filter" in result.stderr


def test_fast_ci_contract_rejects_a_second_unfiltered_test_command(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            FAST_PYTEST_COMMAND,
            FAST_PYTEST_COMMAND + "\n"
            "      - name: Run unfiltered unittest suite\n"
            "        run: uv run --locked --extra dev python -m unittest discover",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "exactly one filtered test command" in result.stderr


def test_fast_ci_contract_rejects_required_command_in_run_comment(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            FAST_PYTEST_COMMAND,
            (
                "run: # uv run --locked --extra dev "
                'pytest -m "not research and not slow"'
            ),
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "workflow must have exactly one filtered test command" in result.stderr


def test_fast_ci_contract_rejects_required_command_in_shell_comment(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "run: uv run --locked --extra dev python "
            "scripts/verify_distribution_artifacts.py",
            "run: |\n"
            "          true # uv run --locked --extra dev python "
            "scripts/verify_distribution_artifacts.py",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "missing required executable command" in result.stderr


@pytest.mark.parametrize(
    ("line", "expected"),
    (
        ("true # comment", "true"),
        ("printf '# keep'", "printf '# keep'"),
        ('printf "# keep"', 'printf "# keep"'),
        (r"printf \# keep", r"printf \# keep"),
    ),
)
def test_shell_comment_stripping_preserves_quoted_and_escaped_hashes(
    line: str, expected: str
) -> None:
    assert _strip_unquoted_shell_comment(line) == expected


def test_fast_ci_contract_rejects_required_command_in_step_name(
    tmp_path: Path,
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    workflow = workflow.replace(
        "      - name: Run pytest suite",
        (
            "      - name: Run uv run --locked --extra dev "
            'pytest -m "not research and not slow"'
        ),
    )
    workflow = workflow.replace(
        FAST_PYTEST_COMMAND,
        "run: # command moved to step name",
    )
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(workflow, encoding="utf-8")

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "workflow must have exactly one filtered test command" in result.stderr


def test_fast_ci_contract_rejects_required_command_in_step_env_run(
    tmp_path: Path,
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        FAST_PYTEST_COMMAND,
        "run: # command moved to env.run",
    )
    workflow = workflow.replace(
        "        env:\n          POLIS_GENERATIVE_GENERATOR_VERSION",
        "        env:\n"
        "          run: uv run --locked --extra dev pytest "
        '-m "not research and not slow"\n'
        "          POLIS_GENERATIVE_GENERATOR_VERSION",
    )
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(workflow, encoding="utf-8")

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "workflow must have exactly one filtered test command" in result.stderr


def test_fast_ci_contract_rejects_required_command_in_another_job(
    tmp_path: Path,
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        FAST_PYTEST_COMMAND,
        "run: # command moved to another job",
    )
    workflow += (
        "\n  unrelated:\n"
        "    runs-on: macos-15\n"
        "    steps:\n"
        "      - name: Retained unrelated command\n"
        "        run: uv run --locked --extra dev pytest "
        '-m "not research and not slow"\n'
    )
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(workflow, encoding="utf-8")

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "workflow must have exactly one filtered test command" in result.stderr


def test_fast_ci_contract_rejects_required_command_in_nested_step_field(
    tmp_path: Path,
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        FAST_PYTEST_COMMAND,
        "run: # command moved to an unrelated nested field",
    )
    workflow = workflow.replace(
        "        run: # command moved to an unrelated nested field",
        "        run: # command moved to an unrelated nested field\n"
        "        with:\n"
        "          diagnostic:\n"
        "            - description: retained metadata\n"
        "              run: uv run --locked --extra dev pytest "
        '-m "not research and not slow"',
    )
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(workflow, encoding="utf-8")

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "workflow must have exactly one filtered test command" in result.stderr


def test_fast_ci_contract_rejects_required_command_in_run_true_comment(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "run: uv run --locked --extra dev python "
            "scripts/verify_distribution_artifacts.py",
            "run: true # uv run --locked --extra dev python "
            "scripts/verify_distribution_artifacts.py",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "missing required executable command" in result.stderr


def test_fast_ci_contract_rejects_required_command_hidden_in_echo(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "run: uv run --locked --extra dev python "
            "scripts/verify_distribution_artifacts.py",
            'run: echo "uv run --locked --extra dev python '
            'scripts/verify_distribution_artifacts.py"',
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "missing required executable command" in result.stderr


@pytest.mark.parametrize("masking_suffix", (" || true", "; true", " &"))
def test_fast_ci_contract_rejects_failure_masking_after_required_command(
    tmp_path: Path, masking_suffix: str
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    required_command = (
        "run: uv run --locked --extra dev python "
        "scripts/verify_distribution_artifacts.py"
    )
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            required_command,
            required_command + masking_suffix,
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "missing required executable command" in result.stderr


@pytest.mark.parametrize("masking_command", ("true", "exit 0"))
def test_fast_ci_contract_rejects_multiline_failure_masking(
    tmp_path: Path, masking_command: str
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    required_command = (
        "uv run --locked --extra dev python scripts/verify_distribution_artifacts.py"
    )
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            f"run: {required_command}",
            f"run: |\n          {required_command}\n          {masking_command}",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "missing required executable command" in result.stderr


def test_fast_ci_contract_rejects_required_command_with_help_argument(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    required_command = (
        "run: uv run --locked --extra dev python "
        "scripts/verify_distribution_install.py --dist dist "
        '--wheelhouse "${{ runner.temp }}/polis-build-wheelhouse" '
        '--wheelhouse-manifest "${{ runner.temp }}/polis-build-wheelhouse.json" '
        '--smoke-cwd "${{ runner.temp }}/polis-install-smoke-cwd"'
    )
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert required_command in workflow
    invalid_workflow.write_text(
        workflow.replace(required_command, required_command + " --help"),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "missing required executable command" in result.stderr


def test_fast_ci_contract_rejects_required_command_in_unreachable_if_false_body(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "run: uv run --locked --extra dev python "
            "scripts/verify_distribution_artifacts.py",
            "run: |\n"
            "          if false; then\n"
            "            uv run --locked --extra dev python "
            "scripts/verify_distribution_artifacts.py\n"
            "          fi",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "missing required executable command" in result.stderr


def test_fast_ci_contract_rejects_required_command_in_heredoc_payload(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "run: uv run --locked --extra dev python "
            "scripts/verify_distribution_artifacts.py",
            "run: |\n"
            "          cat <<'EOF'\n"
            "          uv run --locked --extra dev python "
            "scripts/verify_distribution_artifacts.py\n"
            "          EOF",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "missing required executable command" in result.stderr


@pytest.mark.parametrize("style", ("|", ">"))
def test_fast_ci_contract_accepts_multiline_filtered_pytest_run(
    tmp_path: Path, style: str
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8").replace(
        FAST_PYTEST_COMMAND,
        f"run: {style}\n"
        '          uv run --locked --extra dev pytest -m "not research and not slow"',
    )
    multiline_workflow = tmp_path / "fast-ci.yml"
    multiline_workflow.write_text(workflow, encoding="utf-8")

    result = run_validator(multiline_workflow)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("name,value", GENERATIVE_CONFIGURATION)
def test_fast_ci_contract_rejects_missing_generated_invariant_configuration(
    tmp_path: Path, name: str, value: str
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            f"          {name}: {value}\n", ""
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert f"generated-invariant configuration is missing: {name}" in result.stderr


@pytest.mark.parametrize(
    ("replacement", "expected_error"),
    (
        (
            "POLIS_GENERATIVE_GENERATOR_VERSION=unicode-structural-v2",
            "generated-invariant generator version is invalid",
        ),
        (
            "POLIS_GENERATIVE_SEED=not-a-seed",
            "generated-invariant seed is invalid",
        ),
        (
            "POLIS_GENERATIVE_CASES=many",
            "generated-invariant case budget is invalid",
        ),
        (
            "POLIS_GENERATIVE_CASES=257",
            "generated-invariant case budget exceeds maximum",
        ),
    ),
)
def test_fast_ci_contract_rejects_invalid_generated_invariant_configuration(
    tmp_path: Path, replacement: str, expected_error: str
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    name = replacement.partition("=")[0]
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            next(
                f"{configured_name}: {configured_value}"
                for configured_name, configured_value in GENERATIVE_CONFIGURATION
                if configured_name == name
            ),
            replacement.replace("=", ": "),
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert expected_error in result.stderr


def test_fast_ci_contract_rejects_duplicate_generated_invariant_configuration(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "          POLIS_GENERATIVE_SEED: 95001\n",
            "          POLIS_GENERATIVE_SEED: 95001\n"
            "          POLIS_GENERATIVE_SEED: 95001\n",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "generated-invariant configuration is duplicated" in result.stderr


def test_fast_ci_contract_requires_generated_invariant_configuration_on_pytest_step(
    tmp_path: Path,
) -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        workflow.replace(
            "      - name: Run pytest suite\n" + GENERATIVE_ENVIRONMENT_BLOCK,
            "      - name: Run pytest suite\n"
            "        env:\n"
            "          UNRELATED_SETTING: retained\n",
        ).replace(
            "      - name: Synchronize locked development environment\n"
            "        run: uv sync --locked --extra dev\n",
            "      - name: Synchronize locked development environment\n"
            + GENERATIVE_ENVIRONMENT_BLOCK
            + "        run: uv sync --locked --extra dev\n",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert (
        "generated-invariant configuration must be on the pytest step" in result.stderr
    )


def test_fast_ci_contract_requires_an_env_mapping_on_the_pytest_step(
    tmp_path: Path,
) -> None:
    invalid_workflow = tmp_path / "fast-ci.yml"
    invalid_workflow.write_text(
        WORKFLOW.read_text(encoding="utf-8").replace(
            "      - name: Run pytest suite\n        env:\n",
            "      - name: Run pytest suite\n        with:\n",
        ),
        encoding="utf-8",
    )

    result = run_validator(invalid_workflow)

    assert result.returncode != 0
    assert "generated-invariant configuration must use the pytest step env mapping" in (
        result.stderr
    )


def test_workflow_has_only_the_filtered_pytest_test_command() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    test_commands = [
        line.strip()
        for line in workflow.splitlines()
        if line.lstrip().startswith("run:") and ("pytest" in line or "unittest" in line)
    ]

    assert FAST_PYTEST_FILTER in workflow
    assert test_commands == [FAST_PYTEST_COMMAND]


def test_workflow_actions_have_an_exact_license_review() -> None:
    review = LICENSE_REVIEW.read_text(encoding="utf-8")

    for action, commit in (
        ("actions/checkout", "34e114876b0b11c390a56381ad16ebd13914f8d5"),
        ("actions/setup-python", "ece7cb06caefa5fff74198d8649806c4678c61a1"),
        ("astral-sh/setup-uv", "37802adc94f370d6bfd71619e3f0bf239e1f3b78"),
    ):
        assert f"`{action}`" in review
        assert commit in review
        assert "MIT" in review


def test_fast_pytest_filter_deselects_slow_and_research_tests(tmp_path: Path) -> None:
    sample = tmp_path / "test_marker_selection.py"
    sample.write_text(
        """import unittest

import pytest


def test_fast_case():
    assert True


@pytest.mark.slow
class SlowCase(unittest.TestCase):
    def test_slow_case(self):
        self.assertTrue(True)


@pytest.mark.research
class ResearchCase(unittest.TestCase):
    def test_research_case(self):
        self.assertTrue(True)
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--strict-markers",
            "-c",
            str(ROOT / "pyproject.toml"),
            "-m",
            "not research and not slow",
            str(sample),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed, 2 deselected" in result.stdout


def test_fast_ci_evaluation_contracts_run_without_documentation_prose() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--strict-markers",
            "-c",
            str(ROOT / "pyproject.toml"),
            "-m",
            "not research and not slow",
            "tests/test_evaluation_dataset.py",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "19 passed" in result.stdout
    assert "1 deselected" in result.stdout


def test_byte_stable_text_uses_effective_text_and_lf_attributes() -> None:
    result = subprocess.run(
        ["git", "check-attr", "text", "eol", "--", *BYTE_STABLE_TEXT_PATHS],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f"{path}: {attribute}: {value}"
        for path in BYTE_STABLE_TEXT_PATHS
        for attribute, value in (("text", "auto"), ("eol", "lf"))
    ]


def _run_git(*args: str, cwd: Path) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_crlf_configured_checkout_preserves_declared_bytes_and_hashes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    checkout = tmp_path / "checkout"
    source.mkdir()
    paths = (*BYTE_STABLE_TEXT_PATHS, *BYTE_EXACT_UPSTREAM_PATHS)
    for relative_path in (".gitattributes", *paths):
        target = source / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative_path, target)

    _run_git("init", "--quiet", cwd=source)
    _run_git("config", "user.email", "ci@example.invalid", cwd=source)
    _run_git("config", "user.name", "Fast CI regression", cwd=source)
    _run_git("config", "core.autocrlf", "false", cwd=source)
    _run_git("add", ".", cwd=source)
    _run_git("commit", "--quiet", "-m", "fixture", cwd=source)

    _run_git(
        "-c",
        "core.autocrlf=true",
        "-c",
        "core.eol=crlf",
        "clone",
        "--quiet",
        "--no-local",
        str(source),
        str(checkout),
        cwd=tmp_path,
    )

    for relative_path in paths:
        expected = (source / relative_path).read_bytes()
        actual = (checkout / relative_path).read_bytes()
        assert actual == expected, relative_path
        assert hashlib.sha256(actual).digest() == hashlib.sha256(expected).digest()


def test_platform_specific_release_checks_have_versioned_owners() -> None:
    compatibility = COMPATIBILITY_POLICY.read_text(encoding="utf-8")
    distribution = DISTRIBUTION_VERIFICATION.read_text(encoding="utf-8")
    normalized_distribution = " ".join(distribution.split())

    assert "Profil weryfikacji platform 1.0" in compatibility
    assert "`tests/test_cli.py`" in compatibility
    assert "`tests/test_release_distribution_installation.py`" in compatibility
    assert "`tests/test_offline_verification.py`" in compatibility
    assert "Efektywna polityka `text`/`eol`" in compatibility
    assert "Dowód pracy z zablokowaną siecią" in compatibility
    assert "osobną weryfikację bramki wydania" in compatibility
    assert "`PYTHONIOENCODING=cp1252`" in distribution
    assert "`tests/test_release_distribution_installation.py`" in distribution
    assert "natywne dla platformy zakończenia" in normalized_distribution
    assert (
        "starsze środowisko Windows z odziedziczonym kodekiem"
        in normalized_distribution
    )
    assert "test_languagetool_vendor_artifacts.py" not in compatibility
    assert "scripts/verify_distribution_install.py" in distribution
    assert "--dist dist --wheelhouse build-wheelhouse" in normalized_distribution
    assert "--wheelhouse-manifest build-wheelhouse-manifest.json" in (
        normalized_distribution
    )
    assert "--smoke-cwd build-smoke-cwd" in normalized_distribution


def test_vendored_upstream_text_is_exempt_from_checkout_normalization() -> None:
    result = subprocess.run(
        [
            "git",
            "check-attr",
            "text",
            "eol",
            "--",
            *BYTE_EXACT_UPSTREAM_PATHS,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        f"{path}: {attribute}: unset"
        for path in BYTE_EXACT_UPSTREAM_PATHS
        for attribute in ("text", "eol")
    ]
