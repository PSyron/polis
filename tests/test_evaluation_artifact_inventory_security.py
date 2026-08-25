from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
import scripts.validate_evaluation_artifact_inventory as validator

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "project" / "evaluation-artifact-inventory.json"


def test_validate_inventory_defaults_to_inventory_under_custom_root(
    tmp_path: Path,
) -> None:
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    inventory_path = (
        tmp_path / "docs" / "project" / "evaluation-artifact-inventory.json"
    )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    inventory["aliases"][0]["legacy_sha256"] = "0" * 64
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )

    errors = validator.validate_inventory(tmp_path)

    assert any("legacy artifact bytes changed" in error for error in errors)


@pytest.mark.parametrize("field", ("schema_ids", "legacy_schema_ids"))
def test_load_inventory_rejects_noncanonical_schema_ids(
    tmp_path: Path, field: str
) -> None:
    inventory: dict[str, Any] = json.loads(INVENTORY.read_text(encoding="utf-8"))
    inventory[field]["baseline"] = "polis.untrusted-baseline"
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match=f"inventory {field} is invalid"):
        validator.load_inventory(inventory_path)


def test_load_inventory_rejects_incomplete_alias_universe(tmp_path: Path) -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    inventory["aliases"].pop()
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(
        json.dumps(inventory, ensure_ascii=True, indent=2) + "\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="aliases are incomplete"):
        validator.load_inventory(inventory_path)


def test_load_inventory_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    inventory_text = INVENTORY.read_text(encoding="utf-8")
    schema_line = '  "schema_id": "polis.evaluation-artifact-inventory",\n'
    duplicate_text = inventory_text.replace(schema_line, schema_line * 2, 1)
    inventory_path = tmp_path / "inventory.json"
    inventory_path.write_text(duplicate_text, encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate JSON key"):
        validator.load_inventory(inventory_path)


def test_validate_inventory_deduplicates_resolved_alias_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inventory: dict[str, Any] = json.loads(INVENTORY.read_text(encoding="utf-8"))
    inventory["aliases"][1]["canonical"] = "docs/project/../regression-baseline-v1.json"

    def fake_load_inventory(
        _path: Path, *, enforce_alias_universe: bool = True
    ) -> dict[str, Any]:
        return inventory

    monkeypatch.setattr(validator, "load_inventory", fake_load_inventory)

    errors = validator.validate_inventory(ROOT, INVENTORY)

    assert any("duplicate artifact alias" in error for error in errors)
