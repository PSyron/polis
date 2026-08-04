#!/usr/bin/env python3
"""Validate path-only coverage of the documentation migration inventory."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

ROOT: Final[Path] = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY: Final[Path] = (
    ROOT / "docs" / "project" / "documentation-migration-inventory.json"
)
_TOP_LEVEL_KEYS: Final[frozenset[str]] = frozenset(
    {"schema_version", "issue", "policy_version", "rules"}
)
_RULE_KEYS: Final[frozenset[str]] = frozenset(
    {"id", "disposition", "wave", "paths", "prefixes"}
)
_ALLOWED_DISPOSITIONS: Final[frozenset[str]] = frozenset(
    {
        "maintain_polish",
        "retain_historical_evidence",
        "retain_machine_facing_english",
        "retain_research_evidence",
        "retain_upstream_original",
        "translate_polish",
    }
)
_ALLOWED_WAVES: Final[frozenset[str]] = frozenset(
    {
        "architecture",
        "governance",
        "protected",
        "public-entry",
        "release-and-privacy",
        "runtime-and-research-guides",
    }
)
_PROTECTED_DISPOSITIONS: Final[frozenset[str]] = frozenset(
    {
        "retain_historical_evidence",
        "retain_research_evidence",
        "retain_upstream_original",
    }
)
_EVIDENCE_ROOTS: Final[tuple[str, ...]] = (
    "data/",
    "experiments/",
    "src/polis/evaluation/",
    "third_party/languagetool-pl/",
)
_EVIDENCE_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        "README.md",
        "config.json",
        "report.json",
        "results.json",
        "assembly.json",
        "cases.json",
        "holdout.started",
        "evaluated_source.json",
        "pre_evaluation_inputs.patch",
        "LICENSE-LGPL-2.1.txt",
        "NOTICE",
        "UPSTREAM.md",
        "BENCHMARK.md",
        "manifest.json",
        "0001-reproducible-build-metadata.patch",
    }
)
_FROZEN_REVIEW_CHECKLISTS: Final[frozenset[str]] = frozenset(
    {
        "docs/evaluation-corpus-v3-review-checklist.md",
        "docs/evaluation-safety-corpus-v1-review-checklist.md",
        "docs/evaluation-safety-corpus-v2-review-checklist.md",
    }
)


@dataclass(frozen=True, slots=True)
class InventoryRule:
    """One ordered path classification rule."""

    id: str
    disposition: str
    wave: str
    paths: tuple[str, ...]
    prefixes: tuple[str, ...]

    def matches(self, path: str) -> bool:
        return path in self.paths or any(
            path.startswith(prefix) for prefix in self.prefixes
        )


@dataclass(frozen=True, slots=True)
class DocumentationInventory:
    """Closed migration inventory contract."""

    schema_version: int
    issue: int
    policy_version: str
    rules: tuple[InventoryRule, ...]


def _require_non_blank(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-blank string")
    return value


def _require_string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    result = tuple(_require_non_blank(item, field) for item in value)
    if len(set(result)) != len(result):
        raise ValueError(f"{field} contains duplicate entries")
    return result


def load_inventory(path: Path) -> DocumentationInventory:
    """Load and strictly validate the closed inventory schema."""

    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load documentation inventory: {path}") from exc
    if not isinstance(raw, dict) or set(raw) != _TOP_LEVEL_KEYS:
        raise ValueError("documentation inventory has invalid top-level keys")
    if raw["schema_version"] != 1:
        raise ValueError("unsupported documentation inventory schema version")
    if raw["issue"] != 158:
        raise ValueError("documentation inventory must reference issue 158")
    policy_version = _require_non_blank(raw["policy_version"], "policy_version")
    rules_raw = raw["rules"]
    if not isinstance(rules_raw, list):
        raise ValueError("rules must be a list")

    rules: list[InventoryRule] = []
    for index, rule_raw in enumerate(rules_raw):
        if not isinstance(rule_raw, dict) or set(rule_raw) != _RULE_KEYS:
            raise ValueError(f"rule {index} has invalid keys")
        paths = _require_string_tuple(rule_raw["paths"], f"rule {index} paths")
        prefixes = _require_string_tuple(rule_raw["prefixes"], f"rule {index} prefixes")
        if not paths and not prefixes:
            raise ValueError(f"rule {index} must match at least one path or prefix")
        if any(
            prefix.startswith("/") or not prefix.endswith("/") for prefix in prefixes
        ):
            raise ValueError(f"rule {index} prefixes must be relative directories")
        if any(path.startswith("/") or path.endswith("/") for path in paths):
            raise ValueError(f"rule {index} paths must be relative files")
        disposition = _require_non_blank(
            rule_raw["disposition"], f"rule {index} disposition"
        )
        if disposition not in _ALLOWED_DISPOSITIONS:
            raise ValueError(f"unsupported disposition: {disposition}")
        wave = _require_non_blank(rule_raw["wave"], f"rule {index} wave")
        if wave not in _ALLOWED_WAVES:
            raise ValueError(f"unsupported wave: {wave}")
        rules.append(
            InventoryRule(
                id=_require_non_blank(rule_raw["id"], f"rule {index} id"),
                disposition=disposition,
                wave=wave,
                paths=paths,
                prefixes=prefixes,
            )
        )

    rule_ids = [rule.id for rule in rules]
    if len(set(rule_ids)) != len(rule_ids):
        raise ValueError("documentation inventory contains duplicate rule ids")
    return DocumentationInventory(
        schema_version=1,
        issue=158,
        policy_version=policy_version,
        rules=tuple(rules),
    )


def tracked_paths(root: Path, *pathspecs: str) -> tuple[str, ...]:
    """Return Git-tracked paths without reading their content."""

    command = ["git", "-C", str(root), "ls-files", "-z"]
    if pathspecs:
        command.extend(("--", *pathspecs))
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ValueError("cannot enumerate Git-tracked Markdown paths")
    return tuple(
        sorted(path.decode("utf-8") for path in result.stdout.split(b"\0") if path)
    )


def tracked_markdown_paths(root: Path) -> tuple[str, ...]:
    """Return Git-tracked Markdown paths without reading their content."""

    return tracked_paths(root, "*.md")


def _required_protected_disposition(path: str) -> str | None:
    if path == "CHANGELOG.md" or path.startswith(
        ("docs/architecture/decisions/", "docs/release-notes/", "docs/superpowers/")
    ):
        return "retain_historical_evidence"
    if path in _FROZEN_REVIEW_CHECKLISTS:
        return "retain_research_evidence"
    if not path.startswith(_EVIDENCE_ROOTS):
        return None
    filename = path.rsplit("/", maxsplit=1)[-1]
    if filename not in _EVIDENCE_FILENAMES and not (
        filename.startswith("frozen_") and filename.endswith(".json")
    ):
        return None
    if path.startswith("third_party/languagetool-pl/"):
        return "retain_upstream_original"
    return "retain_research_evidence"


def classify_path(
    path: str,
    rules: tuple[InventoryRule, ...],
) -> InventoryRule | None:
    """Return the first matching rule; order is explicit policy precedence."""

    return next((rule for rule in rules if rule.matches(path)), None)


def protected_rule_errors(inventory: DocumentationInventory) -> list[str]:
    """Require protected rules to use unshadowed exact path matches only."""

    errors: list[str] = []
    for rule in inventory.rules:
        if rule.disposition not in _PROTECTED_DISPOSITIONS:
            continue
        if rule.prefixes:
            errors.append(f"protected rule must not use prefixes: {rule.id}")
        for path in rule.paths:
            effective = classify_path(path, inventory.rules)
            if effective is not rule:
                effective_id = "<unclassified>" if effective is None else effective.id
                errors.append(
                    "protected exact path is shadowed by an earlier rule: "
                    f"{rule.id}: {path} -> {effective_id}"
                )
    return errors


def required_protected_artifact_errors(
    root: Path,
    inventory: DocumentationInventory,
) -> list[str]:
    """Discover required artifacts independently from inventory declarations."""

    errors: list[str] = []
    for path in tracked_paths(root):
        required = _required_protected_disposition(path)
        if required is None:
            continue
        effective = classify_path(path, inventory.rules)
        if (
            effective is None
            or path not in effective.paths
            or effective.disposition != required
        ):
            errors.append(
                f"required protected artifact must use an exact {required} rule: {path}"
            )
    return errors


def classify_inventory(
    root: Path,
    inventory: DocumentationInventory,
) -> tuple[dict[str, InventoryRule], list[str]]:
    """Classify every tracked Markdown path and report uncovered paths."""

    classifications: dict[str, InventoryRule] = {}
    errors: list[str] = []
    for path in tracked_markdown_paths(root):
        rule = classify_path(path, inventory.rules)
        if rule is None:
            errors.append(f"unclassified Markdown path: {path}")
        else:
            classifications[path] = rule
    return classifications, errors


def validate_inventory(root: Path, inventory_path: Path) -> list[str]:
    """Return all coverage errors for the selected repository and inventory."""

    try:
        inventory = load_inventory(inventory_path)
        _, errors = classify_inventory(root, inventory)
        errors.extend(protected_rule_errors(inventory))
        errors.extend(required_protected_artifact_errors(root, inventory))
    except ValueError as exc:
        return [str(exc)]
    return errors


def _summary(
    inventory: DocumentationInventory,
    classifications: dict[str, InventoryRule],
) -> dict[str, Any]:
    dispositions = Counter(rule.disposition for rule in classifications.values())
    waves = Counter(rule.wave for rule in classifications.values())
    return {
        "schema_version": inventory.schema_version,
        "issue": inventory.issue,
        "policy_version": inventory.policy_version,
        "tracked_markdown_paths": len(classifications),
        "dispositions": dict(sorted(dispositions.items())),
        "waves": dict(sorted(waves.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate the documentation migration inventory."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    inventory_path = (
        args.inventory.resolve()
        if args.inventory is not None
        else root / "docs" / "project" / "documentation-migration-inventory.json"
    )
    try:
        inventory = load_inventory(inventory_path)
        classifications, errors = classify_inventory(root, inventory)
        errors.extend(protected_rule_errors(inventory))
        errors.extend(required_protected_artifact_errors(root, inventory))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    summary = _summary(inventory, classifications)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(
            "documentation migration inventory is complete: "
            f"{summary['tracked_markdown_paths']} tracked Markdown paths"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
