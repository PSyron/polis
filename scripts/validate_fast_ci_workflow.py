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
    "Fast suite deliberately excludes slow, model, benchmark, and release work.",
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

    fast_pytest_command = (
        'run: uv run --locked --extra dev pytest -m "not slow and not model"'
    )
    if fast_pytest_command not in workflow:
        errors.append("fast pytest marker filter is missing")
    test_commands = re.findall(
        r"^\s+run: .*\b(?:pytest|unittest)\b.*$", workflow, re.MULTILINE
    )
    if [command.strip() for command in test_commands] != [fast_pytest_command]:
        errors.append("workflow must have exactly one filtered test command")

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
