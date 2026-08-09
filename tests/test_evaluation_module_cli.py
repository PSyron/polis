from __future__ import annotations

import importlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Protocol, runtime_checkable

import pytest
from tests.holdout_config_fixture import synthetic_config


@runtime_checkable
class _CliApi(Protocol):
    def run(
        self,
        arguments: list[str],
        *,
        runner: Callable[[Path], int],
        repository_root: Path | None = None,
    ) -> int: ...


def _cli() -> _CliApi:
    try:
        module = importlib.import_module("polis.evaluation.__main__")
    except ModuleNotFoundError as error:
        raise AssertionError("planned evaluation module CLI is absent") from error
    if not isinstance(module, _CliApi):
        raise AssertionError("planned evaluation module CLI API is incomplete")
    return module


def _module_command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "polis.evaluation", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def test_module_help_exposes_only_run_holdout() -> None:
    result = _module_command("--help")

    assert result.returncode == 0
    assert "run-holdout" in result.stdout
    assert "baseline" not in result.stdout
    assert "validate-proposal" not in result.stdout


@pytest.mark.parametrize(
    "flag",
    [
        "--dataset",
        "--analyzer",
        "--source",
        "--threshold",
        "--output",
        "--repetitions",
        "--replace",
    ],
)
def test_run_holdout_rejects_every_non_preregistered_override(
    flag: str, tmp_path: Path
) -> None:
    result = _module_command(
        "run-holdout", "--config", str(tmp_path / "config.json"), flag, "forbidden"
    )

    assert result.returncode == 2
    assert not (tmp_path / "holdout.started").exists()


def test_cli_dispatches_only_the_canonical_repository_config_to_injected_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "experiments/a-b-one-shot/config.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(synthetic_config()), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    dispatched: list[Path] = []

    def synthetic_runner(path: Path) -> int:
        dispatched.append(path)
        return 0

    exit_code = _cli().run(
        ["run-holdout", "--config", "experiments/a-b-one-shot/config.json"],
        runner=synthetic_runner,
        repository_root=tmp_path,
    )

    assert exit_code == 0
    assert dispatched == [Path("experiments/a-b-one-shot/config.json")]
    assert not (tmp_path / "holdout.started").exists()


@pytest.mark.parametrize("alias", ["copied.json", "renamed/config.json"])
def test_cli_rejects_noncanonical_config_alias_before_dispatch(
    alias: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copied = tmp_path / alias
    copied.parent.mkdir(parents=True, exist_ok=True)
    copied.write_text(json.dumps(synthetic_config()), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    dispatched: list[Path] = []

    def forbidden_runner(path: Path) -> int:
        dispatched.append(path)
        return 0

    exit_code = _cli().run(
        ["run-holdout", "--config", alias],
        runner=forbidden_runner,
        repository_root=tmp_path,
    )

    assert exit_code == 2
    assert dispatched == []
    assert not (tmp_path / "experiments/a-b-one-shot/holdout.started").exists()


def test_cli_rejects_absolute_config_even_when_it_is_the_canonical_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "experiments/a-b-one-shot/config.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(synthetic_config()), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    dispatched: list[Path] = []

    def forbidden_runner(path: Path) -> int:
        dispatched.append(path)
        return 0

    exit_code = _cli().run(
        ["run-holdout", "--config", str(config)],
        runner=forbidden_runner,
        repository_root=tmp_path,
    )

    assert exit_code == 2
    assert dispatched == []


def test_cli_rejects_symlinked_canonical_config_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    actual = tmp_path / "actual.json"
    actual.write_text(json.dumps(synthetic_config()), encoding="utf-8")
    config = tmp_path / "experiments/a-b-one-shot/config.json"
    config.parent.mkdir(parents=True)
    config.symlink_to(actual)
    monkeypatch.chdir(tmp_path)
    dispatched: list[Path] = []

    def forbidden_runner(path: Path) -> int:
        dispatched.append(path)
        return 0

    exit_code = _cli().run(
        ["run-holdout", "--config", "experiments/a-b-one-shot/config.json"],
        runner=forbidden_runner,
        repository_root=tmp_path,
    )

    assert exit_code == 2
    assert dispatched == []


def test_cli_rejects_canonical_looking_path_from_nested_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = tmp_path / "repo"
    nested = repository_root / "nested"
    config = nested / "experiments/a-b-one-shot/config.json"
    config.parent.mkdir(parents=True)
    config.write_text(json.dumps(synthetic_config()), encoding="utf-8")
    monkeypatch.chdir(nested)
    dispatched: list[Path] = []

    def forbidden_runner(path: Path) -> int:
        dispatched.append(path)
        return 0

    exit_code = _cli().run(
        ["run-holdout", "--config", "experiments/a-b-one-shot/config.json"],
        runner=forbidden_runner,
        repository_root=repository_root,
    )

    assert exit_code == 2
    assert dispatched == []
