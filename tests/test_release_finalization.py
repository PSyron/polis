from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from scripts.verify_distribution_artifacts import ALLOWED_SDIST_MEMBERS

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.0"
RELEASE_NOTE = f"docs/release-notes/{VERSION}.md"


def _project_data() -> dict[str, Any]:
    with (ROOT / "pyproject.toml").open("rb") as metadata_file:
        return tomllib.load(metadata_file)


def test_stable_release_metadata_is_consistent() -> None:
    project_data = _project_data()
    project = project_data["project"]
    local_lock = next(
        package
        for package in tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))[
            "package"
        ]
        if package["name"] == "polis-nlp"
    )

    assert project["version"] == VERSION
    assert local_lock["version"] == VERSION
    assert "Development Status :: 4 - Beta" in project["classifiers"]
    assert (
        sum(
            classifier.startswith("Development Status ::")
            for classifier in project["classifiers"]
        )
        == 1
    )


def test_stable_release_note_is_shipped_and_inventory_protected() -> None:
    project_data = _project_data()
    sdist_members = project_data["tool"]["hatch"]["build"]["targets"]["sdist"]
    inventory = json.loads(
        (ROOT / "docs/project/documentation-migration-inventory.json").read_text(
            encoding="utf-8"
        )
    )
    immutable_paths = next(
        rule["paths"]
        for rule in inventory["rules"]
        if rule["id"] == "immutable-release-evidence"
    )
    license_review = (ROOT / "docs/development/dependency-licenses.md").read_text(
        encoding="utf-8"
    )

    assert f"/{RELEASE_NOTE}" in sdist_members["include"]
    assert RELEASE_NOTE in ALLOWED_SDIST_MEMBERS
    assert RELEASE_NOTE in immutable_paths
    assert "| `polis-nlp` | 0.2.0 | MIT | projekt lokalny |" in license_review
