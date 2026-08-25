from __future__ import annotations

from typing import Final

INVENTORY_KEYS: Final[frozenset[str]] = frozenset(
    {
        "schema_id",
        "schema_version",
        "issue",
        "purpose",
        "legacy_alias_policy",
        "schema_ids",
        "legacy_schema_ids",
        "aliases",
    }
)
ALIAS_KEYS: Final[frozenset[str]] = frozenset(
    {"kind", "canonical", "legacy", "legacy_sha256"}
)
KINDS: Final[frozenset[str]] = frozenset(
    {"baseline", "result", "comparison", "threshold"}
)
CANONICAL_SCHEMA_IDS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("baseline", "polis.regression-baseline"),
        ("result", "polis.regression-result"),
        ("comparison", "polis.regression-comparison"),
        ("threshold", "polis.regression-threshold-proposal"),
    }
)
LEGACY_SCHEMA_IDS: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("baseline", "polis.quality-baseline"),
        ("result", "polis.quality-result"),
        ("comparison", "polis.quality-comparison"),
        ("threshold", "polis.quality-threshold-proposal"),
    }
)
_ALIAS_GROUPS: Final[tuple[tuple[str, str, str, tuple[str, ...]], ...]] = (
    (
        "baseline",
        "regression-baseline",
        "quality-baseline",
        (
            "v1",
            "v2-default",
            "v2-morphology",
            "v3-default",
            "v3-morphology",
            "v4-default",
            "v4-morphology",
        ),
    ),
    (
        "result",
        "regression-result",
        "quality-result",
        (
            "v2-default",
            "v2-morphology",
            "v3-default",
            "v3-morphology",
            "v4-default",
            "v4-morphology",
            "wave0-default",
            "wave0-morphology",
        ),
    ),
    ("comparison", "regression-comparison", "quality-comparison", ("v2", "v3", "v4")),
    (
        "threshold",
        "regression-threshold-proposal",
        "quality-threshold-proposal",
        ("v1", "v2", "v3", "v4"),
    ),
)
EXPECTED_ALIAS_UNIVERSE: Final[frozenset[tuple[str, str, str]]] = frozenset(
    (
        kind,
        f"docs/{canonical_prefix}-{version}.json",
        f"docs/{legacy_prefix}-{version}.json",
    )
    for kind, canonical_prefix, legacy_prefix, versions in _ALIAS_GROUPS
    for version in versions
)
