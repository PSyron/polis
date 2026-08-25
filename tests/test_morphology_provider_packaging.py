from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_morfeusz_is_optional_and_not_a_default_dependency() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert project["project"]["dependencies"] == []
    assert "morfeusz2==1.99.15" in project["project"]["optional-dependencies"]["dev"]
    assert project["project"]["optional-dependencies"]["morphology"] == [
        "morfeusz2==1.99.15"
    ]
    assert (ROOT / "src/polis/rules/_morfeusz.py").is_file()
    assert (ROOT / "src/polis/rules/subject_verb.py").is_file()


def test_synthetic_generator_is_checkout_only() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    excluded = set(project["tool"]["hatch"]["build"]["targets"]["wheel"]["exclude"])

    assert "/src/polis/evaluation/synthetic_corpus.py" in excluded
    assert "/src/polis/evaluation/_synthetic_*.py" in excluded
    assert "/src/polis/evaluation/synthetic_corpus.py" in set(
        project["tool"]["hatch"]["build"]["targets"]["sdist"]["exclude"]
    )
    assert "/src/polis/evaluation/_synthetic_*.py" in set(
        project["tool"]["hatch"]["build"]["targets"]["sdist"]["exclude"]
    )
