from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

type JsonValue = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)
type Action = tuple[str, str, dict[str, JsonValue]]

EXPECTED_ACTIONS: Final[tuple[Action, ...]] = (
    (
        "actions/checkout",
        "34e114876b0b11c390a56381ad16ebd13914f8d5",
        {"fetch-depth": 0, "fetch-tags": True},
    ),
    (
        "actions/setup-python",
        "ece7cb06caefa5fff74198d8649806c4678c61a1",
        {
            "python-version": "${{ matrix.python-version }}",
            "architecture": "${{ matrix.setup-python-architecture }}",
        },
    ),
    (
        "astral-sh/setup-uv",
        "37802adc94f370d6bfd71619e3f0bf239e1f3b78",
        {
            "version": "0.11.2",
            "enable-cache": True,
            "cache-dependency-glob": "uv.lock",
        },
    ),
)
EXPECTED_RUN_COMMANDS: Final[tuple[str, ...]] = (
    "uv sync --locked --extra dev",
    "uv run --locked --extra dev python scripts/prepare_build_wheelhouse.py "
    '--lock uv.lock --output "${{ runner.temp }}/polis-build-wheelhouse" '
    '--manifest "${{ runner.temp }}/polis-build-wheelhouse.json"',
    'uv run --locked --extra dev pytest -m "not research and not slow"',
    "uv run --locked --extra dev ruff check .",
    "uv run --locked --extra dev ruff format --check .",
    "uv run --locked --extra dev mypy .",
    "uv run --locked --extra dev python scripts/validate_documentation_inventory.py",
    "uv run --locked --extra dev python scripts/rule_coverage_contract.py",
    "uv run --locked --extra dev python -m scripts.rule_coverage_rjp_2026",
    "uv run --locked --extra dev python scripts/validate_release_workflow.py "
    "--workflow .github/workflows/release.yml",
    "uv run --locked --extra dev python -m build --no-isolation",
    "uv run --locked --extra dev python scripts/verify_distribution_artifacts.py",
    'mkdir "${{ runner.temp }}/polis-install-smoke-cwd"',
    "uv run --locked --extra dev python scripts/verify_distribution_install.py "
    '--dist dist --wheelhouse "${{ runner.temp }}/polis-build-wheelhouse" '
    '--wheelhouse-manifest "${{ runner.temp }}/polis-build-wheelhouse.json" '
    '--smoke-cwd "${{ runner.temp }}/polis-install-smoke-cwd"',
)
EXPECTED_PYTEST_ENVIRONMENT: Final[dict[str, JsonValue]] = {
    "POLIS_GENERATIVE_GENERATOR_VERSION": "unicode-structural-v1",
    "POLIS_GENERATIVE_SEED": 95001,
    "POLIS_GENERATIVE_CASES": 64,
}
EXPECTED_STRATEGY: Final[dict[str, JsonValue]] = {
    "fail-fast": False,
    "matrix": {
        "include": [
            {
                "os": "macos-15",
                "architecture": "arm64",
                "setup-python-architecture": "arm64",
                "python-version": "3.12",
            },
            {
                "os": "macos-15",
                "architecture": "arm64",
                "setup-python-architecture": "arm64",
                "python-version": "3.14",
            },
        ]
    },
}


@dataclass(frozen=True, slots=True)
class QualityGraphResult:
    run_commands: tuple[str, ...]
    errors: tuple[str, ...]


def _strip_unquoted_shell_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, character in enumerate(line):
        if escaped:
            escaped = False
            continue
        if character == "\\" and quote != "'":
            escaped = True
            continue
        if quote is not None:
            if character == quote:
                quote = None
            continue
        if character in {"'", '"'}:
            quote = character
        elif character == "#":
            return line[:index].rstrip()
    return line.rstrip()


def executes_required_command(run: str, required: str) -> bool:
    if len(run.splitlines()) != 1:
        return False
    return _shell_tokens(run) == _shell_tokens(required)


def _shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.commenters = ""
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return []


def _normalize_run(command: str) -> str:
    return "\n".join(
        cleaned
        for line in command.splitlines()
        if (cleaned := _strip_unquoted_shell_comment(line))
    ).strip()


def _load_jobs(path: Path) -> tuple[JsonValue | None, bool, bool, str | None]:
    ruby = shutil.which("ruby")
    if ruby is None:
        return None, False, False, "Ruby is required for local YAML syntax validation."
    result = subprocess.run(
        [
            ruby,
            "-e",
            "require 'json'; require 'yaml'; workflow = YAML.load_file(ARGV.fetch(0)); "
            "STDOUT.write(JSON.generate(workflow.is_a?(Hash) ? {"
            "'jobs'=>workflow['jobs'],'root_env_present'=>workflow.key?('env'), "
            "'root_defaults_present'=>workflow.key?('defaults')} : nil))",
            str(path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None, False, False, "YAML syntax validation failed: invalid YAML."
    try:
        decoded = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, False, False, "YAML command extraction returned invalid JSON."
    if not isinstance(decoded, dict):
        return None, False, False, "YAML command extraction returned invalid JSON."
    root_env_present = decoded.get("root_env_present") is True
    root_defaults_present = decoded.get("root_defaults_present") is True
    return decoded.get("jobs"), root_env_present, root_defaults_present, None


def _mapping(value: JsonValue) -> dict[str, JsonValue] | None:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        return None
    return value


def _step_mapping(value: JsonValue) -> dict[str, JsonValue] | None:
    return _mapping(value)


def _matches_expected(actual: JsonValue | None, expected: JsonValue) -> bool:
    match actual, expected:
        case dict() as actual_mapping, dict() as expected_mapping:
            return set(actual_mapping) == set(expected_mapping) and all(
                _matches_expected(actual_mapping[key], value)
                for key, value in expected_mapping.items()
            )
        case list() as actual_list, list() as expected_list:
            return len(actual_list) == len(expected_list) and all(
                _matches_expected(value, expected_list[index])
                for index, value in enumerate(actual_list)
            )
        case _:
            return type(actual) is type(expected) and actual == expected


def _validate_action_step(
    step: dict[str, JsonValue], expected: tuple[str, str, dict[str, JsonValue]]
) -> list[str]:
    action, commit, inputs = expected
    errors: list[str] = []
    if set(step) != {"name", "uses", "with"}:
        errors.append("unexpected quality step")
    uses = step.get("uses")
    if uses != f"{action}@{commit}":
        errors.append(f"action is not pinned to its reviewed commit: {action}")
    if not isinstance(uses, str) or "@" not in uses:
        errors.append(f"action is not pinned to a full commit SHA: {action}")
    elif len(uses.rpartition("@")[2]) != 40:
        errors.append(f"action is not pinned to a full commit SHA: {action}")
    if not _matches_expected(step.get("with"), inputs):
        errors.append("unexpected quality step")
    return errors


def _validate_run_step(
    step: dict[str, JsonValue], expected: str, index: int
) -> tuple[str, list[str]]:
    allowed_keys = {"name", "run"}
    if index == 2:
        allowed_keys.add("env")
    errors: list[str] = []
    if set(step) != allowed_keys:
        errors.append("unexpected quality step")
    run = step.get("run")
    normalized = _normalize_run(run) if isinstance(run, str) else ""
    if normalized != expected:
        errors.append("unexpected quality step")
    if index == 2 and not _matches_expected(
        step.get("env"), EXPECTED_PYTEST_ENVIRONMENT
    ):
        errors.append("unexpected environment entry")
    return normalized, errors


def validate_quality_graph(path: Path) -> QualityGraphResult:
    jobs_value, root_env_present, root_defaults_present, parse_error = _load_jobs(path)
    if parse_error is not None:
        return QualityGraphResult((), (parse_error,))
    if root_env_present or root_defaults_present:
        return QualityGraphResult((), ("unexpected workflow root key",))
    jobs = _mapping(jobs_value)
    if jobs is None or set(jobs) != {"quality"}:
        return QualityGraphResult((), ("unexpected quality job key",))
    quality = _mapping(jobs["quality"])
    if quality is None:
        return QualityGraphResult((), ("unexpected quality job key",))
    errors: list[str] = []
    if set(quality) != {"name", "runs-on", "timeout-minutes", "strategy", "steps"}:
        errors.append("unexpected quality job key")
    if (
        quality.get("runs-on") != "${{ matrix.os }}"
        or quality.get("timeout-minutes") != 10
        or not _matches_expected(quality.get("strategy"), EXPECTED_STRATEGY)
    ):
        errors.append("unexpected quality job key")
    steps_value = quality.get("steps")
    if not isinstance(steps_value, list) or len(steps_value) != 17:
        return QualityGraphResult((), tuple(errors + ["unexpected quality step"]))
    commands: list[str] = []
    for index, action_spec in enumerate(EXPECTED_ACTIONS):
        step = _step_mapping(steps_value[index])
        if step is None:
            errors.append("unexpected quality step")
        else:
            errors.extend(_validate_action_step(step, action_spec))
    for index, command_spec in enumerate(EXPECTED_RUN_COMMANDS, start=3):
        step = _step_mapping(steps_value[index])
        if step is None:
            errors.append("unexpected quality step")
        else:
            command, step_errors = _validate_run_step(step, command_spec, index - 3)
            commands.append(command)
            errors.extend(step_errors)
    return QualityGraphResult(tuple(commands), tuple(errors))
