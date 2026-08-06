from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOCK_FILE = ROOT / "uv.lock"
LICENSE_REVIEW = ROOT / "docs/development/dependency-licenses.md"
PYPROJECT = ROOT / "pyproject.toml"
README = ROOT / "README.md"


def test_every_locked_package_has_a_license_review_entry() -> None:
    lock_data: dict[str, Any] = tomllib.loads(LOCK_FILE.read_text(encoding="utf-8"))
    locked_packages = {
        (package["name"], package["version"]) for package in lock_data["package"]
    }
    review = LICENSE_REVIEW.read_text(encoding="utf-8")
    locked_review = review.split("## Zewnętrzne narzędzie inicjujące", maxsplit=1)[0]
    reviewed_packages = set(
        re.findall(r"^\| `([^`]+)` \| ([^ |]+) \|", locked_review, re.MULTILINE)
    )

    assert reviewed_packages == locked_packages


def test_external_uv_bootstrap_tool_is_pinned_and_reviewed() -> None:
    project_data: dict[str, Any] = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    readme = README.read_text(encoding="utf-8")
    review = LICENSE_REVIEW.read_text(encoding="utf-8")

    assert project_data["tool"]["uv"]["required-version"] == "==0.11.2"
    assert "https://astral.sh/uv/0.11.2/install.sh" in readme
    assert "https://astral.sh/uv/0.11.2/install.ps1" in readme
    assert "| `uv` | 0.11.2 | Apache-2.0 OR MIT |" in review
    assert "workflow oparty na lockfile" in review
    assert "środowiska z lockfile" in review
    assert "pakiety przypięte w lockfile" in review
    assert "documentation-contract" not in review


def test_every_release_workflow_action_is_in_the_license_inventory() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    review = LICENSE_REVIEW.read_text(encoding="utf-8")
    action_references = set(
        re.findall(r"^\s+uses: ([^@\s]+)@([0-9a-f]{40})$", workflow, re.MULTILINE)
    )
    reviewed = set(
        re.findall(
            r"^\| `([^`]+)` \| `([0-9a-f]{40})` \|",
            review.split("## Decyzja o przyjęciu", maxsplit=1)[0],
            re.MULTILINE,
        )
    )

    assert action_references <= reviewed
