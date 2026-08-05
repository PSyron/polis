from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE_PATH = ROOT / "docs" / "architecture"
DECISION_PATH = ARCHITECTURE_PATH / "decisions" / "0021-rule-catalog-ownership.md"
INVENTORY_PATH = ARCHITECTURE_PATH / "rule-catalog-inventory.json"
INVENTORY_DOCUMENT_PATH = ARCHITECTURE_PATH / "rule-catalog-inventory.md"


def _load_inventory() -> dict[str, object]:
    payload: object = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert all(isinstance(key, str) for key in payload)
    return payload


def test_rule_catalog_inventory_remains_a_static_historical_record() -> None:
    inventory = _load_inventory()

    assert inventory["schema_version"] == 1
    assert isinstance(inventory["catalog_candidates"], list)


def test_rule_catalog_decision_and_inventory_link_to_each_other() -> None:
    assert DECISION_PATH.is_file()
    decision = DECISION_PATH.read_text(encoding="utf-8")
    inventory = INVENTORY_DOCUMENT_PATH.read_text(encoding="utf-8")

    assert "../rule-catalog-inventory.md" in decision
    assert "decisions/0021-rule-catalog-ownership.md" in inventory


def test_rule_catalog_inventory_records_non_catalog_boundaries() -> None:
    inventory = _load_inventory()

    exclusions = inventory["excluded_source_families"]
    assert isinstance(exclusions, list)
    assert [entry["family"] for entry in exclusions] == [
        "llm_and_finding_backends",
        "transport_and_process_helpers",
        "extension_constructors",
        "test_only_rules",
    ]
    assert all(
        isinstance(entry, dict)
        and isinstance(entry.get("reason"), str)
        and entry["reason"].strip()
        for entry in exclusions
    )
