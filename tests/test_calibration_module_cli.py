from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

import polis.evaluation.__main__ as evaluation_cli

_CANONICAL_CONFIG = Path("experiments/a-b-qualification-v2/config.json")


def _module_command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "polis.evaluation", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def _write_repository(root: Path) -> Path:
    config = root / _CANONICAL_CONFIG
    config.parent.mkdir(parents=True)
    config.write_bytes(b"{}\n")
    return config


def _tree_snapshot(root: Path) -> tuple[tuple[str, str], ...]:
    rows: list[tuple[str, str]] = []
    for entry in sorted(root.rglob("*")):
        relative = entry.relative_to(root).as_posix()
        if entry.is_symlink():
            rows.append((relative, f"symlink:{entry.readlink()}"))
        elif entry.is_file():
            rows.append((relative, f"file:{entry.read_bytes().hex()}"))
        else:
            rows.append((relative, "directory"))
    return tuple(rows)


def _recording_runner(dispatched: list[Path]) -> Callable[[Path], int]:
    def run(config: Path) -> int:
        dispatched.append(config)
        return 0

    return run


def test_module_help_exposes_holdout_and_calibration_commands() -> None:
    result = _module_command("--help")

    assert result.returncode == 0
    assert "run-holdout" in result.stdout
    assert "run-calibration" in result.stdout


@pytest.mark.parametrize(
    "flag",
    (
        "--dataset",
        "--source",
        "--threshold",
        "--repetitions",
        "--output",
        "--replace",
    ),
)
def test_calibration_rejects_override_before_dispatch(
    flag: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dispatched: list[Path] = []
    monkeypatch.chdir(tmp_path)

    def forbidden_runner(config: Path) -> int:
        dispatched.append(config)
        return 0

    monkeypatch.setattr(evaluation_cli, "run_calibration", forbidden_runner)

    with pytest.raises(SystemExit) as raised:
        evaluation_cli.run(
            ["run-calibration", "--config", "synthetic.json", flag, "forbidden"]
        )

    assert raised.value.code == 2
    assert dispatched == []
    assert list(tmp_path.iterdir()) == []


def test_calibration_dispatches_only_the_config_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_repository(tmp_path)
    monkeypatch.chdir(tmp_path)
    dispatched: list[Path] = []

    def synthetic_runner(config: Path) -> int:
        dispatched.append(config)
        return 17

    monkeypatch.setattr(evaluation_cli, "run_calibration", synthetic_runner)

    exit_code = evaluation_cli.run(
        ["run-calibration", "--config", str(_CANONICAL_CONFIG)],
        repository_root=tmp_path,
    )

    assert exit_code == 17
    assert dispatched == [_CANONICAL_CONFIG]


@pytest.mark.parametrize(
    "alias",
    (
        "copied.json",
        "experiments/a-b-qualification-v2/copied.json",
        "experiments/a-b-qualification-v2/../a-b-qualification-v2/config.json",
    ),
)
def test_calibration_rejects_alias_or_parent_path_before_dispatch(
    alias: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = _write_repository(tmp_path)
    alias_path = tmp_path / alias
    if ".." not in Path(alias).parts:
        alias_path.parent.mkdir(parents=True, exist_ok=True)
        alias_path.write_bytes(canonical.read_bytes())
    monkeypatch.chdir(tmp_path)
    dispatched: list[Path] = []
    before = _tree_snapshot(tmp_path)
    monkeypatch.setattr(
        evaluation_cli, "run_calibration", _recording_runner(dispatched)
    )

    exit_code = evaluation_cli.run(
        ["run-calibration", "--config", alias], repository_root=tmp_path
    )

    assert exit_code == 2
    assert dispatched == []
    assert _tree_snapshot(tmp_path) == before


def test_calibration_rejects_absolute_canonical_path_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    canonical = _write_repository(tmp_path)
    monkeypatch.chdir(tmp_path)
    dispatched: list[Path] = []
    before = _tree_snapshot(tmp_path)
    monkeypatch.setattr(
        evaluation_cli, "run_calibration", _recording_runner(dispatched)
    )

    exit_code = evaluation_cli.run(
        ["run-calibration", "--config", str(canonical)], repository_root=tmp_path
    )

    assert exit_code == 2
    assert dispatched == []
    assert _tree_snapshot(tmp_path) == before


def test_calibration_rejects_wrong_working_directory_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = tmp_path / "repository"
    _write_repository(repository)
    nested = repository / "nested"
    nested.mkdir()
    monkeypatch.chdir(nested)
    dispatched: list[Path] = []
    before = _tree_snapshot(repository)
    monkeypatch.setattr(
        evaluation_cli, "run_calibration", _recording_runner(dispatched)
    )

    exit_code = evaluation_cli.run(
        ["run-calibration", "--config", str(_CANONICAL_CONFIG)],
        repository_root=repository,
    )

    assert exit_code == 2
    assert dispatched == []
    assert _tree_snapshot(repository) == before


@pytest.mark.parametrize("component", ("experiments", "experiment_root", "config"))
def test_calibration_rejects_every_symlink_component_before_dispatch(
    component: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    actual = tmp_path / "actual"
    config = actual / "config.json"
    config.parent.mkdir()
    config.write_bytes(b"{}\n")
    if component == "experiments":
        target = actual / "a-b-qualification-v2"
        target.mkdir()
        (target / "config.json").write_bytes(b"{}\n")
        (tmp_path / "experiments").symlink_to(actual, target_is_directory=True)
    else:
        experiments = tmp_path / "experiments"
        experiments.mkdir()
        experiment = experiments / "a-b-qualification-v2"
        if component == "experiment_root":
            experiment.symlink_to(actual, target_is_directory=True)
        else:
            experiment.mkdir()
            (experiment / "config.json").symlink_to(config)
    monkeypatch.chdir(tmp_path)
    dispatched: list[Path] = []
    before = _tree_snapshot(tmp_path)
    monkeypatch.setattr(
        evaluation_cli, "run_calibration", _recording_runner(dispatched)
    )

    exit_code = evaluation_cli.run(
        ["run-calibration", "--config", str(_CANONICAL_CONFIG)],
        repository_root=tmp_path,
    )

    assert exit_code == 2
    assert dispatched == []
    assert _tree_snapshot(tmp_path) == before
