from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = ("wheel", "sdist")
SYNTHETIC_BENCHMARK = "/src/polis/evaluation/synthetic_benchmark.py"


def test_synthetic_benchmark_is_excluded_from_runtime_distributions() -> None:
    # Given
    with (ROOT / "pyproject.toml").open("rb") as pyproject_file:
        project = tomllib.load(pyproject_file)

    # When
    targets = project["tool"]["hatch"]["build"]["targets"]

    # Then
    for target in TARGETS:
        assert SYNTHETIC_BENCHMARK in targets[target]["exclude"]
    assert project["project"]["dependencies"] == []
