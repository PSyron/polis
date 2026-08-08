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
