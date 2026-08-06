from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.release_identity_authority import JsonValue


def _read(path: Path) -> dict[str, JsonValue]:
    try:
        payload: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"cannot read release protection fixture: {path}") from error
    if not isinstance(payload, dict):
        raise SystemExit(f"release protection fixture must be a JSON object: {path}")
    return payload


def _validate_environment(payload: dict[str, JsonValue], reviewer: str) -> None:
    if payload.get("name") != "pypi":
        raise SystemExit("release environment name must be pypi")
    policy = payload.get("deployment_branch_policy")
    if not isinstance(policy, dict) or policy != {
        "protected_branches": False,
        "custom_branch_policies": True,
    }:
        raise SystemExit("release environment must use custom branch policies")
    rules = payload.get("protection_rules")
    if not isinstance(rules, list) or len(rules) != 1:
        raise SystemExit("release environment must have one reviewer rule")
    rule = rules[0]
    if not isinstance(rule, dict):
        raise SystemExit("release environment reviewer rule is malformed")
    if rule.get("type") != "required_reviewers":
        raise SystemExit("release environment reviewer rule is missing")
    if rule.get("prevent_self_review") is not False:
        raise SystemExit("release environment must allow self review")
    reviewers = rule.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) != 1:
        raise SystemExit("release environment must have one required reviewer")
    item = reviewers[0]
    if not isinstance(item, dict):
        raise SystemExit("release environment required reviewer is malformed")
    reviewer_value = item.get("reviewer")
    if (
        item.get("type") != "User"
        or not isinstance(reviewer_value, dict)
        or reviewer_value.get("login") != reviewer
    ):
        raise SystemExit("release environment required reviewer is wrong")


def _validate_branches(payload: dict[str, JsonValue], branch: str) -> None:
    policies = payload.get("branch_policies")
    if payload.get("total_count") != 1 or not isinstance(policies, list):
        raise SystemExit("release environment branch policy count is wrong")
    if (
        len(policies) != 1
        or not isinstance(policies[0], dict)
        or policies[0].get("name") != branch
    ):
        raise SystemExit("release environment branch policy is wrong")


def _validate_ruleset(payload: dict[str, JsonValue], tag_pattern: str) -> None:
    if payload.get("target") != "tag" or payload.get("enforcement") != "active":
        raise SystemExit("release tag ruleset must be active")
    conditions = payload.get("conditions")
    if not isinstance(conditions, dict):
        raise SystemExit("release tag ruleset tag pattern is wrong")
    ref_name = conditions.get("ref_name")
    if not isinstance(ref_name, dict) or ref_name != {
        "include": [tag_pattern],
        "exclude": [],
    }:
        raise SystemExit("release tag ruleset tag pattern is wrong")
    rules = payload.get("rules")
    if (
        not isinstance(rules, list)
        or any(not isinstance(item, dict) for item in rules)
        or {item.get("type") for item in rules if isinstance(item, dict)}
        != {"deletion", "update"}
    ):
        raise SystemExit("release tag ruleset must block update and deletion")
    bypasses = payload.get("bypass_actors")
    if not isinstance(bypasses, list) or not bypasses:
        raise SystemExit("release tag ruleset administrative bypass is missing")
    if any(
        isinstance(item, dict) and item.get("actor_type") == "Integration"
        for item in bypasses
    ):
        raise SystemExit("release tag ruleset has a workflow actor bypass")
    if any(
        not isinstance(item, dict)
        or item.get("actor_type") != "RepositoryRole"
        or item.get("actor_id") != 5
        for item in bypasses
    ):
        raise SystemExit("release tag ruleset has a non-administrative bypass")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate release environment and tag protection read-back."
    )
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--branch-policies", type=Path, required=True)
    parser.add_argument("--ruleset", type=Path, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--branch", required=True)
    parser.add_argument("--tag-pattern", required=True)
    args = parser.parse_args(argv)
    _validate_environment(_read(args.environment), args.reviewer)
    _validate_branches(_read(args.branch_policies), args.branch)
    _validate_ruleset(_read(args.ruleset), args.tag_pattern)
    print("release environment contract is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
