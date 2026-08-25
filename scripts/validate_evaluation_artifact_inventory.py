#!/usr/bin/env python3
"""Validate canonical regression-artifact names and legacy numeric parity."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Final

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY: Final[Path] = (
    ROOT / "docs" / "project" / "evaluation-artifact-inventory.json"
)
_INVENTORY_KEYS: Final[frozenset[str]] = frozenset(
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
_ALIAS_KEYS: Final[frozenset[str]] = frozenset(
    {"kind", "canonical", "legacy", "legacy_sha256"}
)
_KINDS: Final[frozenset[str]] = frozenset(
    {"baseline", "result", "comparison", "threshold"}
)


def _numeric_values(value: Any) -> tuple[tuple[str, int | float], ...]:
    if isinstance(value, bool):
        return ()
    if isinstance(value, int | float):
        return ((type(value).__name__, value),)
    if isinstance(value, dict):
        return tuple(
            item for key in sorted(value) for item in _numeric_values(value[key])
        )
    if isinstance(value, list):
        return tuple(item for child in value for item in _numeric_values(child))
    return ()


def _load_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load {label}: {path}") from error


def load_inventory(path: Path = DEFAULT_INVENTORY) -> dict[str, Any]:
    """Load the strict issue-428 artifact inventory."""

    raw = _load_json(path, "evaluation artifact inventory")
    if not isinstance(raw, dict) or set(raw) != _INVENTORY_KEYS:
        raise ValueError("evaluation artifact inventory has invalid top-level keys")
    if raw["schema_id"] != "polis.evaluation-artifact-inventory":
        raise ValueError("evaluation artifact inventory schema_id is invalid")
    if raw["schema_version"] != 2 or raw["issue"] != 428:
        raise ValueError("evaluation artifact inventory version or issue is invalid")
    if not isinstance(raw["purpose"], str) or not raw["purpose"].strip():
        raise ValueError("evaluation artifact inventory purpose is blank")
    if (
        not isinstance(raw["legacy_alias_policy"], str)
        or not raw["legacy_alias_policy"].strip()
    ):
        raise ValueError("evaluation artifact inventory alias policy is blank")
    for field in ("schema_ids", "legacy_schema_ids"):
        values = raw[field]
        if not isinstance(values, dict) or set(values) != _KINDS:
            raise ValueError(f"evaluation artifact inventory {field} is incomplete")
        if any(not isinstance(value, str) or not value for value in values.values()):
            raise ValueError(f"evaluation artifact inventory {field} has blank ids")
    aliases = raw["aliases"]
    if not isinstance(aliases, list) or not aliases:
        raise ValueError("evaluation artifact inventory aliases are missing")
    for index, alias in enumerate(aliases):
        if not isinstance(alias, dict) or set(alias) != _ALIAS_KEYS:
            raise ValueError(f"artifact alias {index} has invalid fields")
        if alias["kind"] not in _KINDS:
            raise ValueError(f"artifact alias {index} has an unknown kind")
        for field in ("canonical", "legacy"):
            value = alias[field]
            if not isinstance(value, str) or not value.startswith("docs/"):
                raise ValueError(f"artifact alias {index} has an invalid {field} path")
        digest = alias["legacy_sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            raise ValueError(f"artifact alias {index} has an invalid legacy SHA-256")
    return raw


def validate_inventory(root: Path = ROOT, path: Path = DEFAULT_INVENTORY) -> list[str]:
    """Return all naming and numeric-parity errors for the inventory."""

    try:
        inventory = load_inventory(path)
    except ValueError as error:
        return [str(error)]

    errors: list[str] = []
    canonical_ids = inventory["schema_ids"]
    legacy_ids = inventory["legacy_schema_ids"]
    seen_canonical: set[str] = set()
    seen_legacy: set[str] = set()
    for alias in inventory["aliases"]:
        kind = alias["kind"]
        canonical = alias["canonical"]
        legacy = alias["legacy"]
        if canonical in seen_canonical or legacy in seen_legacy:
            errors.append(f"duplicate artifact alias: {canonical} / {legacy}")
        seen_canonical.add(canonical)
        seen_legacy.add(legacy)
        if not Path(canonical).name.startswith(f"regression-{kind}-"):
            errors.append(f"canonical artifact has invalid name: {canonical}")
        if not Path(legacy).name.startswith("quality-"):
            errors.append(f"legacy artifact has invalid alias name: {legacy}")
        canonical_path = root / canonical
        legacy_path = root / legacy
        if not canonical_path.is_file():
            errors.append(f"missing canonical artifact: {canonical}")
            continue
        if not legacy_path.is_file():
            errors.append(f"missing legacy artifact: {legacy}")
            continue
        legacy_digest = hashlib.sha256(legacy_path.read_bytes()).hexdigest()
        if legacy_digest != alias["legacy_sha256"]:
            errors.append(f"legacy artifact bytes changed: {legacy}")
            continue
        try:
            canonical_payload = _load_json(canonical_path, "canonical artifact")
            legacy_payload = _load_json(legacy_path, "legacy artifact")
        except ValueError as error:
            errors.append(str(error))
            continue
        if not isinstance(canonical_payload, dict) or not isinstance(
            legacy_payload, dict
        ):
            errors.append(f"artifact is not a JSON object: {canonical}")
            continue
        if canonical_payload.get("schema_id") != canonical_ids[kind]:
            errors.append(f"canonical schema id drifted: {canonical}")
        if legacy_payload.get("schema_id") != legacy_ids[kind]:
            errors.append(f"legacy schema id drifted: {legacy}")
        if _numeric_values(canonical_payload) != _numeric_values(legacy_payload):
            errors.append(f"numeric parity drifted: {canonical} / {legacy}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate issue-428 regression artifact naming and parity."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    args = parser.parse_args(argv)
    errors = validate_inventory(args.root.resolve(), args.inventory.resolve())
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("evaluation artifact inventory is complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
