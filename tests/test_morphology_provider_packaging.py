from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_morfeusz_is_development_only() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert project["project"]["dependencies"] == []
    assert "morfeusz2==1.99.15" in project["project"]["optional-dependencies"]["dev"]
    assert not any((ROOT / "src/polis").rglob("*morfeusz*"))
