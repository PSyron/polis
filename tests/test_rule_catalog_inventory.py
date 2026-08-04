from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest

from polis.analyzer import AnalyzerConfig, _make_default_registry
from polis.core import Category
from polis.correction import policy as correction_policy

ROOT = Path(__file__).resolve().parents[1]
ARCHITECTURE_PATH = ROOT / "docs" / "architecture"
DECISION_PATH = ARCHITECTURE_PATH / "decisions" / "0021-rule-catalog-ownership.md"
INVENTORY_PATH = ROOT / "docs" / "architecture" / "rule-catalog-inventory.json"
INVENTORY_DOCUMENT_PATH = ARCHITECTURE_PATH / "rule-catalog-inventory.md"
CONSTRUCTION_OWNER = "polis.analyzer._make_default_registry"


class _UnusedLanguageToolTransport:
    def check(
        self, text: str, *, language: str, timeout_seconds: float
    ) -> Mapping[str, object]:
        raise AssertionError("inventory inspection must not analyze text")


class _UnusedContextMorphologyTransport:
    def synthesize_context(
        self,
        text: str,
        *,
        spans: tuple[tuple[int, int], ...],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        raise AssertionError("inventory inspection must not analyze text")


def _load_inventory() -> dict[str, object]:
    payload: object = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    assert all(isinstance(key, str) for key in payload)
    return payload


def _runtime_catalog_rows() -> list[dict[str, object]]:
    default_registry = _make_default_registry(AnalyzerConfig())
    default_sources = {str(rule.source) for rule in default_registry.rules()}
    complete_registry = _make_default_registry(
        AnalyzerConfig(),
        language_tool_transport=_UnusedLanguageToolTransport(),
        contextual_inflection_transport=_UnusedContextMorphologyTransport(),
    )
    policy_by_identity = {
        (
            str(entry.key.source),
            entry.key.category.value,
            entry.key.operation,
            entry.key.behavior_version,
            entry.key.source_policy_version,
        ): entry
        for entry in correction_policy._ACTIVE_POLICY_ENTRIES
    }

    rows: list[dict[str, object]] = []
    for registration in complete_registry._registrations:
        rule = registration.rule
        rule_category = getattr(rule, "_CATEGORY", None)
        if registration.categories is None:
            assert isinstance(rule_category, Category)
            category = rule_category
            registry_categories: list[str] | None = None
        else:
            assert len(registration.categories) == 1
            category = next(iter(registration.categories))
            registry_categories = sorted(item.value for item in registration.categories)

        behavior = complete_registry.source_behavior(rule.source)
        assert behavior is not None
        identity = (
            str(rule.source),
            category.value,
            behavior.operation,
            behavior.behavior_version,
            correction_policy.SOURCE_POLICY_VERSION,
        )
        policy_entry = policy_by_identity.get(identity)
        rows.append(
            {
                "source": str(rule.source),
                "class": f"{type(rule).__module__}.{type(rule).__qualname__}",
                "category": category.value,
                "operation": behavior.operation,
                "behavior_version": behavior.behavior_version,
                "availability": (
                    "default" if str(rule.source) in default_sources else "optional"
                ),
                "registry_categories": registry_categories,
                "construction_owner": CONSTRUCTION_OWNER,
                "automatic_correction": {
                    "disposition": (
                        "eligible" if policy_entry else "fail_closed_review_only"
                    ),
                    "minimum_confidence": (
                        policy_entry.minimum_confidence.value
                        if policy_entry is not None
                        else None
                    ),
                    "source_policy_version": (
                        policy_entry.key.source_policy_version
                        if policy_entry is not None
                        else correction_policy.SOURCE_POLICY_VERSION
                    ),
                },
            }
        )

    eligible_inventory_identities: set[tuple[object, ...]] = set()
    for row in rows:
        automatic_correction = row["automatic_correction"]
        assert isinstance(automatic_correction, dict)
        if automatic_correction["disposition"] == "eligible":
            eligible_inventory_identities.add(
                (
                    row["source"],
                    row["category"],
                    row["operation"],
                    row["behavior_version"],
                    automatic_correction["source_policy_version"],
                )
            )
    assert set(policy_by_identity) == eligible_inventory_identities
    return rows


def test_rule_catalog_inventory_matches_runtime_and_correction_policy() -> None:
    inventory = _load_inventory()

    assert inventory["schema_version"] == 1
    candidates = inventory["catalog_candidates"]
    assert isinstance(candidates, list)
    runtime_fields = set(_runtime_catalog_rows()[0])
    documented_runtime_rows: list[dict[str, object]] = []
    for candidate in candidates:
        assert isinstance(candidate, dict)
        assert set(candidate) == runtime_fields | {"role"}
        assert isinstance(candidate["role"], str)
        assert candidate["role"].strip()
        documented_runtime_rows.append(
            {key: value for key, value in candidate.items() if key in runtime_fields}
        )

    assert documented_runtime_rows == _runtime_catalog_rows()


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


def test_runtime_inventory_rejects_policy_version_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_entry, *remaining_entries = correction_policy._ACTIVE_POLICY_ENTRIES
    stale_entry = replace(
        first_entry,
        key=replace(
            first_entry.key,
            source_policy_version="stale-policy-version",
        ),
    )
    monkeypatch.setattr(
        correction_policy,
        "_ACTIVE_POLICY_ENTRIES",
        (stale_entry, *remaining_entries),
    )

    with pytest.raises(AssertionError):
        _runtime_catalog_rows()
