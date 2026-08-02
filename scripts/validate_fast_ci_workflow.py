from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOW = ROOT / ".github/workflows/fast-ci.yml"
EXPECTED_MATRIX = {
    ("ubuntu-24.04", "x86_64", "x64", "3.12"),
    ("ubuntu-24.04", "x86_64", "x64", "3.13"),
    ("ubuntu-24.04", "x86_64", "x64", "3.14"),
    ("macos-15", "arm64", "arm64", "3.12"),
    ("macos-15", "arm64", "arm64", "3.14"),
    ("windows-2025", "x86_64", "x64", "3.12"),
    ("windows-2025", "x86_64", "x64", "3.14"),
}
VALID_SETUP_PYTHON_ARCHITECTURES = {"x86", "x64", "arm64"}
SETUP_PYTHON_ARCHITECTURE_BY_POLICY = {"x86_64": "x64", "arm64": "arm64"}
EXPECTED_ACTIONS = {
    "actions/checkout": "34e114876b0b11c390a56381ad16ebd13914f8d5",
    "actions/setup-python": "ece7cb06caefa5fff74198d8649806c4678c61a1",
    "astral-sh/setup-uv": "37802adc94f370d6bfd71619e3f0bf239e1f3b78",
}
GENERATIVE_GENERATOR_VERSION = "unicode-structural-v1"
GENERATIVE_SEED = 95001
GENERATIVE_CASES = 64
GENERATIVE_MAX_CASES = 256
GENERATIVE_ENVIRONMENT = (
    ("POLIS_GENERATIVE_GENERATOR_VERSION", GENERATIVE_GENERATOR_VERSION),
    ("POLIS_GENERATIVE_SEED", str(GENERATIVE_SEED)),
    ("POLIS_GENERATIVE_CASES", str(GENERATIVE_CASES)),
)
FAST_PYTEST_COMMAND = (
    'run: uv run --locked --extra dev pytest -m "not research and not slow and'
    ' not model"'
)
FAST_PYTEST_FILTER = 'pytest -m "not research and not slow and not model"'
REQUIRED_SNIPPETS = (
    "push:",
    "pull_request:",
    "permissions:\n  contents: read",
    "uv sync --locked --extra dev",
    "uv run --locked --extra dev ruff check .",
    "uv run --locked --extra dev ruff format --check .",
    "uv run --locked --extra dev mypy .",
    "uv run --locked --extra dev python -m build --no-isolation",
    "uv run --locked --extra dev python scripts/verify_distribution_artifacts.py",
    "version: 0.11.2",
    "enable-cache: true",
    "cache-dependency-glob: uv.lock",
    "fetch-depth: 0",
    "fetch-tags: true",
    (
        "Fast suite deliberately excludes research, slow, model, benchmark, and"
        " release work."
    ),
)


def parse_matrix(workflow: str) -> set[tuple[str, str, str, str]]:
    entries = re.findall(
        r"^          - os: ([^\n]+)\n"
        r"            architecture: ([^\n]+)\n"
        r"            setup-python-architecture: ([^\n]+)\n"
        r"            python-version: \"([^\"]+)\"$",
        workflow,
        re.MULTILINE,
    )
    return {
        (os_name, architecture, setup_python_architecture, python_version)
        for os_name, architecture, setup_python_architecture, python_version in entries
    }


def validate_yaml_syntax(path: Path) -> str | None:
    ruby = shutil.which("ruby")
    if ruby is None:
        return "Ruby is required for local YAML syntax validation."
    result = subprocess.run(
        [ruby, "-e", "require 'yaml'; YAML.load_file(ARGV.fetch(0))", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return f"YAML syntax validation failed: {result.stderr.strip()}"
    return None


def validate_generated_invariant_configuration(workflow: str) -> list[str]:
    """Return policy errors for safe, bounded generated-test metadata."""
    step = re.search(
        r"^      - name: Run pytest suite\n(?P<content>.*?)(?=^      - |\Z)",
        workflow,
        re.MULTILINE | re.DOTALL,
    )
    if step is None:
        return ["generated-invariant configuration must be on the pytest step"]

    step_content = step.group("content")
    environment = re.search(
        r"^        env:\n(?P<entries>(?:^          [^\n]+\n?)*)",
        step_content,
        re.MULTILINE,
    )
    if environment is None:
        return [
            "generated-invariant configuration must use the pytest step env mapping"
        ]

    environment_entries = environment.group("entries")
    configuration: dict[str, str] = {}
    errors: list[str] = []
    for name, _ in GENERATIVE_ENVIRONMENT:
        matches = re.findall(rf"^\s+{name}: ([^\s]+)\s*$", workflow, re.MULTILINE)
        step_matches = re.findall(
            rf"^          {name}: ([^\s]+)\s*$", environment_entries, re.MULTILINE
        )
        if not matches:
            errors.append(f"generated-invariant configuration is missing: {name}")
        elif len(matches) != 1 or len(step_matches) != 1:
            if len(matches) > 1 or len(step_matches) > 1:
                errors.append("generated-invariant configuration is duplicated")
            else:
                errors.append(
                    "generated-invariant configuration must be on the pytest step"
                )
        else:
            configuration[name] = step_matches[0]
    if errors:
        return errors

    if (
        configuration["POLIS_GENERATIVE_GENERATOR_VERSION"]
        != GENERATIVE_GENERATOR_VERSION
    ):
        errors.append("generated-invariant generator version is invalid")

    seed = configuration["POLIS_GENERATIVE_SEED"]
    if not seed.isascii() or not seed.isdecimal() or int(seed) != GENERATIVE_SEED:
        errors.append("generated-invariant seed is invalid")

    cases = configuration["POLIS_GENERATIVE_CASES"]
    if not cases.isascii() or not cases.isdecimal():
        errors.append("generated-invariant case budget is invalid")
    elif int(cases) > GENERATIVE_MAX_CASES:
        errors.append("generated-invariant case budget exceeds maximum")
    elif int(cases) != GENERATIVE_CASES:
        errors.append("generated-invariant case budget is invalid")

    return errors


def validate_contract(path: Path) -> list[str]:
    if not path.is_file():
        return [f"workflow does not exist: {path}"]

    syntax_error = validate_yaml_syntax(path)
    if syntax_error is not None:
        return [syntax_error]

    workflow = path.read_text(encoding="utf-8")
    errors = [
        f"missing required workflow content: {value}"
        for value in REQUIRED_SNIPPETS
        if value not in workflow
    ]

    matrix = parse_matrix(workflow)
    for entry in sorted(EXPECTED_MATRIX - matrix):
        errors.append(f"missing required matrix entry: {entry}")
    for entry in sorted(matrix - EXPECTED_MATRIX):
        errors.append(f"unexpected matrix entry: {entry}")

    for _, policy_architecture, setup_python_architecture, _ in matrix:
        if setup_python_architecture not in VALID_SETUP_PYTHON_ARCHITECTURES:
            errors.append(
                f"invalid setup-python architecture value: {setup_python_architecture}"
            )
        expected = SETUP_PYTHON_ARCHITECTURE_BY_POLICY.get(policy_architecture)
        if setup_python_architecture != expected:
            errors.append(
                "setup-python architecture does not match policy architecture: "
                f"{policy_architecture} -> {setup_python_architecture}"
            )

    setup_python_input = "architecture: ${{ matrix.setup-python-architecture }}"
    if setup_python_input not in workflow:
        errors.append(
            "setup-python architecture input must use the mapped matrix field"
        )

    if FAST_PYTEST_FILTER not in workflow:
        errors.append("fast pytest marker filter is missing")
    test_commands = re.findall(
        r"^\s+run: .*\b(?:pytest|unittest)\b.*$", workflow, re.MULTILINE
    )
    if [command.strip() for command in test_commands] != [FAST_PYTEST_COMMAND]:
        errors.append("workflow must have exactly one filtered test command")
    errors.extend(validate_generated_invariant_configuration(workflow))

    action_references = re.findall(
        r"^\s+uses: ([^@\s]+)@([^\s]+)$", workflow, re.MULTILINE
    )
    actual_actions = dict(action_references)
    if len(action_references) != len(EXPECTED_ACTIONS):
        errors.append("workflow must use exactly the reviewed external actions")
    for action, commit in EXPECTED_ACTIONS.items():
        if actual_actions.get(action) != commit:
            errors.append(f"action is not pinned to its reviewed commit: {action}")
    for action, reference in action_references:
        if re.fullmatch(r"[0-9a-f]{40}", reference) is None:
            errors.append(f"action is not pinned to a full commit SHA: {action}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the fast CI workflow contract."
    )
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    args = parser.parse_args()

    errors = validate_contract(args.workflow)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("fast CI workflow contract is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
