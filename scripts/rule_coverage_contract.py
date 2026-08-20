"""Strict repository contract for conservative v1 rule-coverage claims."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from polis.evaluation._quality_types import JsonValue

CONTRACT_PATH: Final = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "project"
    / "rule-coverage-contract-v1.json"
)
CONTRACT_SCHEMA_ID: Final = "polis.rule-coverage-contract"
CONTRACT_SCHEMA_VERSION: Final = 1
CONTRACT_CANONICAL_SHA256: Final = (
    "a78c3576e857cdae995633b446a8099737ce8cb8cb46ead8c46a0df9f8d45c00"
)
SOURCE_PRECEDENCE: Final = (
    "issue-and-accepted-maintainer-clarifications",
    "accepted-architecture-decisions",
    "PROMPT.md",
    "docs/project/ROADMAP.md",
    "docs/rules.md",
    "public-v3-quality-and-isolated-performance-artifacts",
)
PLANNING_BASELINE_FULL_SHA: Final = "165434e243360bb534d5eda8782ff089c087632c"
PLANNING_BASELINE_SOURCE_COUNT: Final = 60
PLANNING_BASELINE_SNAPSHOT_SHA256: Final = (
    "503f04cac68dc8d5aec782ac2a3bdbe26ad09bbf0c6cfde4f5562019d5b3e22d"
)
_RUNTIME_SOURCE_PATHS: Final = (
    "src/polis/__init__.py",
    "src/polis/analysis",
    "src/polis/analyzer.py",
    "src/polis/core",
    "src/polis/correction",
    "src/polis/rules",
    "src/polis/segmentation",
)
SUPPORTED_CATEGORY_ORDER: Final = (
    "agreement",
    "inflection",
    "punctuation",
    "spelling",
    "syntax",
)
SUPPORTED_CATEGORIES: Final = frozenset(SUPPORTED_CATEGORY_ORDER)
SUPPORTED_PROFILES: Final = frozenset({"provider-absent", "qualified-morphology"})
REQUIRED_SHAPE_STRATA: Final = frozenset(
    {
        "simple-local",
        "sentence-internal",
        "multi-sentence",
        "repeated-occurrence",
        "unicode-and-case",
        "quotation-or-literal",
        "conflict-or-abstention",
    }
)
REQUIRED_EXCLUSIONS: Final = frozenset(
    {
        "runtime rule registration or behavior changes",
        "authoring v4 cases or selecting v4 numeric thresholds",
        "qualifying exact new rule families",
        "automatic-correction promotion",
        "changing correction-policy eligibility",
        "optional research or research-only implementation",
        "calibration, holdout, sealed, private, or consumed research evidence",
        "models, network, Java, broad LanguageTool, or a new production dependency",
        "style, semantic, entity, world-knowledge, OCR, or unrestricted rewriting",
        "release and packaging work",
        "normative authority claims from corpora, frequency, dictionaries, or "
        "LanguageTool alone",
    }
)
REQUIRED_RELATIONSHIPS: Final = frozenset(
    {
        ("source-identity", "behavior-version"),
        ("rule-family", "source-identity"),
        ("linguistic-phenomenon", "rule-family"),
        ("public-evaluation-case", "expected-finding"),
        ("positive-hard-negative-pair", "public-evaluation-case"),
        ("category-capability-claim", "public-evaluation-case"),
        ("behavior-version", "expected-finding"),
    }
)


class RuleCoverageContractError(ValueError):
    """Raised when the maintained coverage contract is incomplete or ambiguous."""


@dataclass(frozen=True, slots=True)
class RuleCoverageContract:
    """Validated immutable view of the maintained v1 coverage contract."""

    data: dict[str, JsonValue]

    @property
    def schema_id(self) -> str:
        return _string(self.data, "schema_id", "contract")

    @property
    def schema_version(self) -> int:
        return _integer(self.data, "schema_version", "contract")

    @property
    def categories(self) -> tuple[str, ...]:
        scope = _object_field(self.data, "scope", "contract")
        return tuple(_string_list_field(scope, "categories", "scope"))

    @property
    def profiles(self) -> tuple[str, ...]:
        profiles = _list_field(self.data, "profiles", "contract")
        return tuple(
            _string(_object(item, "profile"), "id", "profile") for item in profiles
        )

    @property
    def metric_ids(self) -> frozenset[str]:
        metrics = _list_field(self.data, "metrics", "contract")
        return frozenset(
            _string(_object(item, "metric"), "id", "metric") for item in metrics
        )


def load_rule_coverage_contract(
    path: Path = CONTRACT_PATH,
    *,
    root: Path | None = None,
) -> RuleCoverageContract:
    """Load and strictly validate the maintained JSON contract."""

    try:
        raw = cast(
            JsonValue,
            json.loads(
                path.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_json_keys,
            ),
        )
    except FileNotFoundError as error:
        raise RuleCoverageContractError(f"contract file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise RuleCoverageContractError(
            "rule coverage contract is invalid JSON"
        ) from error
    contract = validate_rule_coverage_contract(raw)
    validate_live_parity(contract, root=root or path.parents[2])
    return contract


def _reject_duplicate_json_keys(
    pairs: list[tuple[str, JsonValue]],
) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise RuleCoverageContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _load_json_object(path: Path, label: str) -> dict[str, JsonValue]:
    try:
        raw = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_json_keys,
        )
    except FileNotFoundError as error:
        raise RuleCoverageContractError(f"{label} not found: {path}") from error
    except json.JSONDecodeError as error:
        raise RuleCoverageContractError(f"{label} is invalid JSON: {path}") from error
    return _object(cast(JsonValue, raw), label)


def _sha256_file(path: Path, label: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise RuleCoverageContractError(f"{label} unavailable: {path}") from error


def _validate_runtime_source_sha(repository_root: Path, source_sha: str) -> None:
    git_root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    git_root = (
        Path(git_root_result.stdout.strip())
        if git_root_result.returncode == 0
        else Path(__file__).resolve().parents[1]
    )
    resolved = subprocess.run(
        ["git", "rev-list", "--all"],
        cwd=git_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if resolved.returncode != 0 or source_sha not in resolved.stdout.splitlines():
        raise RuleCoverageContractError(
            "planning baseline source SHA is not a resolvable commit from "
            "an advertised ref"
        )
    for diff_args in (
        [
            "git",
            "diff",
            "--quiet",
            source_sha,
            "--",
            *_RUNTIME_SOURCE_PATHS,
        ],
        [
            "git",
            "diff",
            "--cached",
            "--quiet",
            source_sha,
            "--",
            *_RUNTIME_SOURCE_PATHS,
        ],
    ):
        diff = subprocess.run(
            diff_args,
            cwd=git_root,
            capture_output=True,
            text=True,
            check=False,
        )
        if diff.returncode != 0:
            raise RuleCoverageContractError(
                "live runtime differs from the planning baseline source SHA"
            )


def validate_live_parity(
    contract: RuleCoverageContract,
    *,
    root: Path | None = None,
) -> None:
    """Fail closed when live public identities drift from the accepted contract."""

    repository_root = root or CONTRACT_PATH.parents[2]
    from polis import Analyzer, AnalyzerConfig
    from polis.correction import policy as correction_policy

    snapshot = tuple(Analyzer(AnalyzerConfig()).source_identity_snapshot)
    source_governance = _object_field(contract.data, "source_governance", "contract")
    runtime_snapshot = _object_field(
        source_governance, "runtime_snapshot", "source governance"
    )
    baseline = _object_field(runtime_snapshot, "planning_baseline", "runtime snapshot")
    _validate_runtime_source_sha(
        repository_root, _string(baseline, "full_sha", "planning baseline")
    )
    if len(snapshot) != _integer(baseline, "source_count", "planning baseline"):
        raise RuleCoverageContractError("live source count does not match the contract")
    encoded_snapshot = json.dumps(
        [
            {
                "source": identity.source,
                "operation": identity.operation,
                "behavior_version": identity.behavior_version,
            }
            for identity in snapshot
        ],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if hashlib.sha256(encoded_snapshot).hexdigest() != _string(
        baseline, "snapshot_sha256", "planning baseline"
    ):
        raise RuleCoverageContractError("live source snapshot digest drifted")

    documented_rows = _read_documented_rule_inventory(repository_root / "docs/rules.md")
    inventory_governance = _object_field(
        source_governance, "maintained_rule_inventory", "source governance"
    )
    encoded_inventory = json.dumps(
        [dict(row) for row in documented_rows],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if hashlib.sha256(encoded_inventory).hexdigest() != _string(
        inventory_governance, "rows_sha256", "maintained rule inventory"
    ):
        raise RuleCoverageContractError(
            "maintained rule inventory category or scope digest drifted"
        )
    documented = tuple(row["source"] for row in documented_rows)
    live_sources = tuple(identity.source for identity in snapshot)
    if len(documented) != len(set(documented)) or documented != live_sources:
        raise RuleCoverageContractError(
            "maintained rule inventory is not exact ordered parity with the runtime"
        )
    _validate_normative_candidate_inventory(contract, repository_root, documented_rows)

    policy_governance = _object_field(
        source_governance, "correction_policy", "source governance"
    )
    if correction_policy.SOURCE_POLICY_VERSION != _string(
        policy_governance, "policy_version", "correction policy"
    ):
        raise RuleCoverageContractError("correction policy version drifted")
    expected_policy = tuple(
        {
            "source": _string(entry, "source", "expected correction policy entry"),
            "category": _string(entry, "category", "expected correction policy entry"),
            "operation": _string(
                entry, "operation", "expected correction policy entry"
            ),
            "behavior_version": _string(
                entry, "behavior_version", "expected correction policy entry"
            ),
            "source_policy_version": _string(
                entry, "source_policy_version", "expected correction policy entry"
            ),
        }
        for entry in _list_field(
            policy_governance, "active_automatic_entries", "correction policy"
        )
    )
    live_policy = tuple(
        {
            "source": str(entry.key.source),
            "category": entry.key.category.value,
            "operation": entry.key.operation,
            "behavior_version": entry.key.behavior_version,
            "source_policy_version": entry.key.source_policy_version,
        }
        for entry in correction_policy._ACTIVE_POLICY_ENTRIES
    )
    if live_policy != expected_policy:
        raise RuleCoverageContractError(
            "correction policy active entries are not exact parity with the contract"
        )
    live_by_source = {identity.source: identity for identity in snapshot}
    for entry in live_policy:
        identity = live_by_source.get(entry["source"])
        if identity is None or (
            identity.operation != entry["operation"]
            or identity.behavior_version != entry["behavior_version"]
        ):
            raise RuleCoverageContractError(
                f"correction policy parity drift for {entry['source']}"
            )
    _validate_quality_artifact_parity(contract, repository_root)


def _read_documented_rule_inventory(
    path: Path,
) -> tuple[dict[str, str], ...]:
    try:
        markdown = path.read_text(encoding="utf-8")
    except OSError as error:
        raise RuleCoverageContractError(
            f"maintained rule inventory unavailable: {path}"
        ) from error
    header = re.compile(r"^\|\s*Źródło\s*\|\s*Kategoria\s*\|\s*Zakres\s*\|\s*$")
    source = re.compile(r"^`(rule:[^`|]+)`$")
    lines = iter(markdown.splitlines())
    if not any(header.fullmatch(line.strip()) for line in lines):
        raise RuleCoverageContractError("maintained rule inventory table is missing")
    separator = re.compile(
        r"^\|\s*:?-{3,}:?\s*\|\s*:?-{3,}:?\s*\|\s*:?-{3,}:?\s*\|\s*$"
    )
    rows: list[dict[str, str]] = []
    for line in lines:
        if not line.strip():
            break
        stripped = line.strip()
        if separator.fullmatch(stripped):
            continue
        cells = _split_markdown_row(stripped)
        if cells is None:
            raise RuleCoverageContractError("malformed maintained rule inventory row")
        source_match = source.fullmatch(cells[0].strip())
        if source_match is None:
            raise RuleCoverageContractError("malformed maintained rule inventory row")
        category = cells[1].strip().strip("`").strip()
        scope = cells[2].strip()
        if not category or not scope:
            raise RuleCoverageContractError(
                "maintained rule inventory rows require category and scope"
            )
        rows.append(
            {
                "source": source_match.group(1),
                "category": category,
                "scope": scope,
            }
        )
    return tuple(rows)


def _split_markdown_row(line: str) -> tuple[str, str, str] | None:
    if not line.startswith("|") or not line.endswith("|"):
        return None
    cells: list[str] = []
    current: list[str] = []
    index = 1
    while index < len(line) - 1:
        character = line[index]
        if character == "\\" and index + 1 < len(line) - 1:
            next_character = line[index + 1]
            if next_character == "|":
                current.append("|")
                index += 2
                continue
        if character == "|":
            cells.append("".join(current))
            current = []
        else:
            current.append(character)
        index += 1
    cells.append("".join(current))
    if len(cells) != 3:
        return None
    return (cells[0], cells[1], cells[2])


def _validate_normative_candidate_inventory(
    contract: RuleCoverageContract,
    root: Path,
    documented_rows: tuple[dict[str, str], ...],
) -> None:
    source_governance = _object_field(contract.data, "source_governance", "contract")
    governance = _object_field(
        source_governance, "normative_candidate_inventory", "source governance"
    )
    path = _relative_artifact_path(
        root, _string(governance, "path", "normative/candidate inventory")
    )
    if _sha256_file(path, "normative/candidate inventory") != _string(
        governance, "sha256", "normative/candidate inventory"
    ):
        raise RuleCoverageContractError("normative/candidate inventory digest drifted")
    inventory = _load_json_object(path, "normative/candidate inventory")
    _exact_fields(
        inventory,
        {
            "schema_id",
            "schema_version",
            "issue",
            "purpose",
            "verification",
            "normative_authorities",
            "candidate_sources",
            "category_mappings",
            "source_parity",
        },
        "normative/candidate inventory",
    )
    _literal(
        inventory,
        "schema_id",
        "polis.rule-normative-candidate-inventory",
        "normative/candidate inventory",
    )
    _literal(inventory, "schema_version", 1, "normative/candidate inventory")
    _literal(inventory, "issue", 364, "normative/candidate inventory")
    _string(inventory, "purpose", "normative/candidate inventory")
    verification = _object_field(
        inventory, "verification", "normative/candidate inventory"
    )
    _exact_fields(
        verification,
        {"network", "normative_rule", "missing_or_extra"},
        "normative/candidate verification",
    )
    _require_fragments(
        _string(verification, "network", "normative/candidate verification"),
        ("locally", "never fetches"),
        "normative/candidate network rule",
    )
    _require_fragments(
        _string(verification, "normative_rule", "normative/candidate verification"),
        ("explicitly listed authority", "candidate sources", "cannot establish"),
        "normative/candidate authority rule",
    )
    _require_fragments(
        _string(verification, "missing_or_extra", "normative/candidate verification"),
        ("Missing, extra, duplicate, reordered", "fail closed"),
        "normative/candidate parity rule",
    )

    authorities = _list_field(
        inventory, "normative_authorities", "normative/candidate inventory"
    )
    if _ordered_ids(authorities, "normative authority") != (
        "rjp-2026-orthography-interpunkcja",
    ):
        raise RuleCoverageContractError("normative authority inventory is not exact")
    authority = _object(authorities[0], "normative authority")
    _exact_fields(
        authority,
        {
            "id",
            "title",
            "publisher",
            "landing_page",
            "document_url",
            "effective_from",
            "categories",
            "authority_boundary",
        },
        "normative authority",
    )
    _literal(
        authority, "id", "rjp-2026-orthography-interpunkcja", "normative authority"
    )
    _literal(authority, "effective_from", "2026-01-01", "normative authority")
    _literal(
        authority,
        "landing_page",
        "https://rjp.pan.pl/zasady-pisowni-i-interpunkcji-polskiej-2/",
        "normative authority",
    )
    _literal(
        authority,
        "document_url",
        "https://rjp.pan.pl/app/uploads/2026/03/Zalacznik-do-komunikatu-11-25-wersja-ostateczna-jednolita.pdf",
        "normative authority",
    )
    if _string_list_field(authority, "categories", "normative authority") != [
        "punctuation",
        "spelling",
    ]:
        raise RuleCoverageContractError("normative authority categories are not exact")
    _string(authority, "authority_boundary", "normative authority")

    candidates = _list_field(
        inventory, "candidate_sources", "normative/candidate inventory"
    )
    if _ordered_ids(candidates, "candidate source") != (
        "maintained-rule-inventory",
        "public-v3-quality-artifacts",
    ):
        raise RuleCoverageContractError("candidate source inventory is not exact")
    for item in candidates:
        candidate = _object(item, "candidate source")
        _exact_fields(candidate, {"id", "path", "role", "boundary"}, "candidate source")
        _string(candidate, "path", "candidate source")
        _string(candidate, "role", "candidate source")
        _string(candidate, "boundary", "candidate source")

    mappings = _list_field(
        inventory, "category_mappings", "normative/candidate inventory"
    )
    if _ordered_ids(mappings, "normative/candidate category mapping") != (
        SUPPORTED_CATEGORY_ORDER
    ):
        raise RuleCoverageContractError(
            "normative/candidate category mappings are not exact"
        )
    mapping_by_category: dict[str, dict[str, JsonValue]] = {}
    for item in mappings:
        mapping = _object(item, "normative/candidate category mapping")
        _exact_fields(
            mapping,
            {
                "id",
                "category",
                "normative_authority_ids",
                "candidate_source_ids",
                "normative_claim",
                "claim_boundary",
            },
            "normative/candidate category mapping",
        )
        category = _string(mapping, "category", "normative/candidate category mapping")
        mapping_by_category[category] = mapping
        authorities_for_category = _string_list_field(
            mapping, "normative_authority_ids", "normative/candidate category mapping"
        )
        if any(
            authority_id != "rjp-2026-orthography-interpunkcja"
            for authority_id in authorities_for_category
        ):
            raise RuleCoverageContractError(
                "unknown normative authority in category mapping"
            )
        candidates_for_category = _string_list_field(
            mapping, "candidate_source_ids", "normative/candidate category mapping"
        )
        if candidates_for_category != [
            "maintained-rule-inventory",
            "public-v3-quality-artifacts",
        ]:
            raise RuleCoverageContractError("candidate source mapping is incomplete")
        claim = _string(
            mapping, "normative_claim", "normative/candidate category mapping"
        )
        if claim not in {"not-claimed", "bounded-rjp-backed"}:
            raise RuleCoverageContractError(
                "normative claim status is not conservative"
            )
        _string(mapping, "claim_boundary", "normative/candidate category mapping")
    if set(mapping_by_category) != SUPPORTED_CATEGORIES:
        raise RuleCoverageContractError(
            "normative/candidate category mappings omit a category"
        )
    for category in ("agreement", "inflection", "syntax"):
        mapping = mapping_by_category[category]
        if (
            mapping["normative_authority_ids"] != []
            or mapping["normative_claim"] != "not-claimed"
        ):
            raise RuleCoverageContractError(
                f"{category} must not claim an RJP authority"
            )
    for category in ("punctuation", "spelling"):
        mapping = mapping_by_category[category]
        if (
            mapping["normative_authority_ids"] != ["rjp-2026-orthography-interpunkcja"]
            or mapping["normative_claim"] != "bounded-rjp-backed"
        ):
            raise RuleCoverageContractError(f"{category} must be explicitly RJP-backed")

    source_parity = _object_field(
        inventory, "source_parity", "normative/candidate inventory"
    )
    _exact_fields(
        source_parity,
        {
            "runtime_source_fields",
            "maintained_inventory_path",
            "mapping_rule",
            "digest_rule",
        },
        "normative/candidate source parity",
    )
    if _string_list_field(
        source_parity, "runtime_source_fields", "normative/candidate source parity"
    ) != ["source", "category", "scope"]:
        raise RuleCoverageContractError(
            "normative/candidate source fields are not exact"
        )
    _literal(
        source_parity,
        "maintained_inventory_path",
        "docs/rules.md",
        "normative/candidate source parity",
    )
    _require_fragments(
        _string(source_parity, "mapping_rule", "normative/candidate source parity"),
        ("Every ordered runtime source", "exactly one category mapping"),
        "normative/candidate mapping rule",
    )
    _require_fragments(
        _string(source_parity, "digest_rule", "normative/candidate source parity"),
        ("ordered runtime source set", "independently"),
        "normative/candidate digest rule",
    )
    for row in documented_rows:
        if row["category"] not in mapping_by_category:
            raise RuleCoverageContractError(
                "normative/candidate inventory has no category mapping for "
                f"{row['source']}"
            )


def _validate_quality_artifact_parity(
    contract: RuleCoverageContract,
    root: Path,
) -> None:
    comparison_path = root / "docs/quality-comparison-v3.json"
    comparison = _load_json_object(comparison_path, "quality comparison")
    _literal(comparison, "schema_id", "polis.quality-comparison", "quality comparison")
    source_governance = _object_field(contract.data, "source_governance", "contract")
    quality_governance = _object_field(
        source_governance, "quality_artifacts", "source governance"
    )
    if _sha256_file(comparison_path, "quality comparison") != _string(
        quality_governance, "comparison_sha256", "quality artifact governance"
    ):
        raise RuleCoverageContractError("quality comparison digest drifted")
    provenance_path = _relative_artifact_path(
        root,
        _string(
            quality_governance,
            "provenance_manifest_path",
            "quality artifact governance",
        ),
    )
    if _sha256_file(provenance_path, "quality provenance manifest") != _string(
        quality_governance,
        "provenance_manifest_sha256",
        "quality artifact governance",
    ):
        raise RuleCoverageContractError("quality provenance manifest digest drifted")
    _validate_quality_artifact_provenance(
        _load_json_object(provenance_path, "quality provenance manifest"),
        (
            _string(
                quality_governance,
                "baseline_source_git_sha",
                "quality artifact governance",
            ),
            _string(
                quality_governance,
                "result_source_git_sha",
                "quality artifact governance",
            ),
        ),
    )
    _literal(
        comparison,
        "source_git_sha",
        _string(
            quality_governance,
            "comparison_source_git_sha",
            "quality artifact governance",
        ),
        "quality comparison",
    )
    _literal(
        comparison,
        "source_snapshot_sha256",
        quality_governance.get("comparison_source_snapshot_sha256"),
        "quality comparison",
    )
    dataset_sha = _string(comparison, "dataset_sha256", "quality comparison")
    if len(dataset_sha) != 64:
        raise RuleCoverageContractError(
            "quality comparison dataset identity is invalid"
        )
    profiles = _object_field(comparison, "profiles", "quality comparison")
    if set(profiles) != {"default", "morphology"}:
        raise RuleCoverageContractError("quality comparison profiles are incomplete")
    contract_profiles = {
        _string(profile, "id", "profile"): profile
        for profile in (
            _object(item, "profile")
            for item in _list_field(contract.data, "profiles", "contract")
        )
    }
    qualified = _object(
        contract_profiles["qualified-morphology"].get("provider_identity"),
        "qualified provider identity",
    )
    expected_provider = {
        "provider": _string(qualified, "provider", "provider identity"),
        "package_version": _string(qualified, "package_version", "provider identity"),
        "dictionary_id": _string(qualified, "dictionary_id", "provider identity"),
        "dictionary_notice_sha256": _string(
            qualified, "dictionary_notice_sha256", "provider identity"
        ),
    }
    dataset_sha256 = _string(comparison, "dataset_sha256", "quality comparison")
    for profile_id, raw_report in profiles.items():
        report = _object(raw_report, f"quality profile {profile_id}")
        _literal(report, "profile_id", profile_id, f"quality profile {profile_id}")
        baseline_path = _relative_artifact_path(
            root, _string(report, "baseline_path", f"quality profile {profile_id}")
        )
        if _sha256_file(baseline_path, "quality baseline") != _string(
            report, "baseline_sha256", f"quality profile {profile_id}"
        ):
            raise RuleCoverageContractError(
                f"quality baseline digest drift for {profile_id}"
            )
        baseline = _load_json_object(baseline_path, f"quality baseline {profile_id}")
        _literal(
            _object_field(baseline, "source", f"quality baseline {profile_id}"),
            "git_sha",
            _string(
                quality_governance,
                "baseline_source_git_sha",
                "quality artifact governance",
            ),
            f"quality baseline {profile_id}",
        )
        dataset = _object_field(baseline, "dataset", f"quality baseline {profile_id}")
        if _string(dataset, "sha256", "quality baseline dataset") != dataset_sha256:
            raise RuleCoverageContractError(
                f"quality baseline dataset drift for {profile_id}"
            )
        baseline_profile = _object_field(
            baseline, "profile", f"quality baseline {profile_id}"
        )
        _literal(
            baseline_profile, "id", profile_id, f"quality baseline profile {profile_id}"
        )
        provider = baseline_profile.get("morphology_provider")
        if profile_id == "default":
            if provider is not None:
                raise RuleCoverageContractError(
                    "default quality baseline unexpectedly has a provider"
                )
        elif _object(provider, "morphology provider") != expected_provider:
            raise RuleCoverageContractError(
                "qualified quality baseline provider identity drifted"
            )
        result_path = _relative_artifact_path(
            root, _string(report, "result_path", f"quality profile {profile_id}")
        )
        if _sha256_file(result_path, "quality result") != _string(
            report, "result_sha256", f"quality profile {profile_id}"
        ):
            raise RuleCoverageContractError(
                f"quality result digest drift for {profile_id}"
            )
        result = _load_json_object(result_path, f"quality result {profile_id}")
        _literal(
            _object_field(result, "source", f"quality result {profile_id}"),
            "git_sha",
            _string(
                quality_governance,
                "result_source_git_sha",
                "quality artifact governance",
            ),
            f"quality result {profile_id}",
        )
        result_profile = _object_field(
            result, "profile", f"quality result {profile_id}"
        )
        _literal(
            result_profile, "id", profile_id, f"quality result profile {profile_id}"
        )
        result_provider = result_profile.get("morphology_provider")
        if profile_id == "default":
            if result_provider is not None:
                raise RuleCoverageContractError(
                    "default quality result unexpectedly has a provider"
                )
        elif _object(result_provider, "morphology provider") != expected_provider:
            raise RuleCoverageContractError(
                "qualified quality result provider identity drifted"
            )


def _validate_quality_artifact_provenance(
    manifest: dict[str, JsonValue],
    expected_source_shas: tuple[str, ...],
) -> None:
    _exact_fields(
        manifest,
        {"schema_id", "schema_version", "repository", "verification", "sources"},
        "quality provenance manifest",
    )
    _literal(
        manifest,
        "schema_id",
        "polis.rule-coverage-quality-artifact-provenance",
        "quality provenance manifest",
    )
    _literal(manifest, "schema_version", 1, "quality provenance manifest")
    _literal(manifest, "repository", "PSyron/polis", "quality provenance manifest")
    _require_fragments(
        _string(manifest, "verification", "quality provenance manifest"),
        ("immutable provenance record", "offline", "never fetches the network"),
        "quality provenance verification",
    )
    entries = _list_field(manifest, "sources", "quality provenance manifest")
    if len(entries) != len(expected_source_shas):
        raise RuleCoverageContractError(
            "quality provenance source entries are incomplete"
        )
    seen: set[str] = set()
    for item in entries:
        entry = _object(item, "quality provenance source")
        _exact_fields(
            entry,
            {
                "source_git_sha",
                "authoritative_url",
                "tree_sha",
                "parent_shas",
                "message",
            },
            "quality provenance source",
        )
        source_sha = _string(entry, "source_git_sha", "quality provenance source")
        if source_sha not in expected_source_shas or source_sha in seen:
            raise RuleCoverageContractError(
                "quality provenance source identity drifted"
            )
        seen.add(source_sha)
        expected_url = f"https://github.com/PSyron/polis/commit/{source_sha}"
        _literal(entry, "authoritative_url", expected_url, "quality provenance source")
        tree_sha = _string(entry, "tree_sha", "quality provenance source")
        if re.fullmatch(r"[0-9a-f]{40}", tree_sha) is None:
            raise RuleCoverageContractError(
                "quality provenance tree identity is invalid"
            )
        parents = _string_list_field(entry, "parent_shas", "quality provenance source")
        if any(re.fullmatch(r"[0-9a-f]{40}", parent) is None for parent in parents):
            raise RuleCoverageContractError(
                "quality provenance parent identity is invalid"
            )
        _string(entry, "message", "quality provenance source")
    if seen != set(expected_source_shas):
        raise RuleCoverageContractError(
            "quality provenance source identities are incomplete"
        )


def _relative_artifact_path(root: Path, value: str) -> Path:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise RuleCoverageContractError(
            f"artifact path is not repository-relative: {value}"
        )
    return root / relative


def validate_rule_coverage_contract(raw: JsonValue) -> RuleCoverageContract:
    """Validate every decision-bearing field and reject silent contract drift."""

    contract = _object(raw, "contract")
    _exact_fields(
        contract,
        {
            "schema_id",
            "schema_version",
            "contract_id",
            "status",
            "effective_date",
            "issue",
            "parent_issue",
            "decision_owner",
            "scope",
            "source_precedence",
            "coverage_units",
            "relationships",
            "profiles",
            "metrics",
            "gates",
            "sampling",
            "ambiguity_policy",
            "correction_governance",
            "source_governance",
            "exclusions",
            "maintainer_approval",
        },
        "contract",
    )
    _literal(contract, "schema_id", CONTRACT_SCHEMA_ID, "contract")
    _literal(contract, "schema_version", CONTRACT_SCHEMA_VERSION, "contract")
    _literal(contract, "contract_id", "polis-conservative-v1-rule-coverage", "contract")
    _literal(contract, "status", "accepted", "contract")
    _string(contract, "effective_date", "contract")
    _literal(contract, "issue", 364, "contract")
    _literal(contract, "parent_issue", 363, "contract")
    _string(contract, "decision_owner", "contract")

    _validate_scope(_object_field(contract, "scope", "contract"))
    if _string_list_field(contract, "source_precedence", "contract") != list(
        SOURCE_PRECEDENCE
    ):
        raise RuleCoverageContractError(
            "source precedence must preserve the accepted authority order"
        )
    _validate_coverage_units(_list_field(contract, "coverage_units", "contract"))
    _validate_relationships(_list_field(contract, "relationships", "contract"))
    _validate_profiles(_list_field(contract, "profiles", "contract"))
    _validate_metrics(_list_field(contract, "metrics", "contract"))
    _validate_gates(_object_field(contract, "gates", "contract"))
    _validate_sampling(_object_field(contract, "sampling", "contract"))
    _validate_ambiguity_policy(_object_field(contract, "ambiguity_policy", "contract"))
    _validate_correction_governance(
        _object_field(contract, "correction_governance", "contract")
    )
    _validate_source_governance(
        _object_field(contract, "source_governance", "contract")
    )
    exclusions = _string_list_field(contract, "exclusions", "contract")
    if frozenset(exclusions) != REQUIRED_EXCLUSIONS or len(exclusions) != len(
        REQUIRED_EXCLUSIONS
    ):
        raise RuleCoverageContractError(
            "contract exclusions must name all v1 non-goals"
        )
    _validate_maintainer_approval(
        _object_field(contract, "maintainer_approval", "contract")
    )
    encoded = json.dumps(
        contract,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if hashlib.sha256(encoded).hexdigest() != CONTRACT_CANONICAL_SHA256:
        raise RuleCoverageContractError(
            "contract canonical digest does not match the accepted v1 contract"
        )
    return RuleCoverageContract(data=contract)


def _validate_scope(scope: dict[str, JsonValue]) -> None:
    _exact_fields(
        scope,
        {
            "product",
            "categories",
            "claim_boundary",
            "runtime_behavior_change",
            "numeric_v4_thresholds",
        },
        "scope",
    )
    _literal(scope, "product", "conservative deterministic Polis v1", "scope")
    categories = _string_list_field(scope, "categories", "scope")
    if frozenset(categories) != SUPPORTED_CATEGORIES or len(categories) != len(
        SUPPORTED_CATEGORIES
    ):
        raise RuleCoverageContractError(
            "scope categories must contain each supported category exactly once"
        )
    for field in ("claim_boundary", "runtime_behavior_change", "numeric_v4_thresholds"):
        _string(scope, field, "scope")


def _validate_coverage_units(units: list[JsonValue]) -> None:
    required = {
        "source-identity",
        "behavior-version",
        "rule-family",
        "linguistic-phenomenon",
        "public-evaluation-case",
        "expected-finding",
        "positive-hard-negative-pair",
        "category-capability-claim",
    }
    parsed = _unique_ids(units, "coverage unit")
    if parsed != required:
        raise RuleCoverageContractError(
            f"coverage units must be exactly {sorted(required)}"
        )
    for item in units:
        unit = _object(item, "coverage unit")
        _exact_fields(unit, {"id", "definition", "evidence_role"}, "coverage unit")
        _string(unit, "id", "coverage unit")
        _string(unit, "definition", "coverage unit")
        _string(unit, "evidence_role", "coverage unit")


def _validate_relationships(relationships: list[JsonValue]) -> None:
    if len(relationships) != len(REQUIRED_RELATIONSHIPS):
        raise RuleCoverageContractError("coverage relationships are incomplete")
    parsed: set[tuple[str, str]] = set()
    for item in relationships:
        relation = _object(item, "coverage relationship")
        _exact_fields(relation, {"from", "to", "rule"}, "coverage relationship")
        origin = _string(relation, "from", "coverage relationship")
        target = _string(relation, "to", "coverage relationship")
        _string(relation, "rule", "coverage relationship")
        pair = (origin, target)
        if pair in parsed or pair not in REQUIRED_RELATIONSHIPS:
            raise RuleCoverageContractError(
                "coverage relationships must contain each required edge exactly once"
            )
        parsed.add(pair)


def _validate_profiles(profiles: list[JsonValue]) -> None:
    parsed = _unique_ids(profiles, "profile")
    if parsed != SUPPORTED_PROFILES:
        raise RuleCoverageContractError(
            "profiles must contain provider-absent and qualified-morphology "
            "exactly once"
        )
    for item in profiles:
        profile = _object(item, "profile")
        _exact_fields(
            profile,
            {
                "id",
                "claim",
                "provider_identity",
                "expected_source_families",
                "provider_absence_or_drift",
                "comparability",
            },
            "profile",
        )
        profile_id = _string(profile, "id", "profile")
        _string(profile, "claim", "profile")
        provider_identity = profile.get("provider_identity")
        if profile_id == "provider-absent":
            if provider_identity is not None:
                raise RuleCoverageContractError(
                    "provider-absent profile must have no provider identity"
                )
        else:
            provider = _object(
                provider_identity, "qualified-morphology.provider_identity"
            )
            _exact_fields(
                provider,
                {
                    "provider",
                    "package_version",
                    "dictionary_id",
                    "dictionary_notice_sha256",
                    "identity_rule",
                },
                "qualified-morphology.provider_identity",
            )
            _literal(provider, "provider", "morfeusz2", "provider identity")
            _literal(provider, "package_version", "1.99.15", "provider identity")
            _literal(
                provider,
                "dictionary_id",
                "pl.sgjp.sgjp-2026.06.01",
                "provider identity",
            )
            _literal(
                provider,
                "dictionary_notice_sha256",
                "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
                "provider identity",
            )
            _require_fragments(
                _string(provider, "identity_rule", "provider identity"),
                ("package", "dictionary", "notice identity", "checked"),
                "provider identity rule",
            )
        families = _object_field(profile, "expected_source_families", "profile")
        _exact_fields(
            families,
            {"execute", "abstain", "failure"},
            f"profile {profile_id} source families",
        )
        for field in ("execute", "abstain"):
            if not _string_list_field(families, field, f"profile {profile_id}"):
                raise RuleCoverageContractError(
                    f"profile {profile_id} {field} source families are empty"
                )
        _string(families, "failure", f"profile {profile_id} source families")
        provider_rule = _string(profile, "provider_absence_or_drift", "profile")
        if profile_id == "provider-absent":
            _require_fragments(
                provider_rule,
                ("abstention boundary", "not be replaced"),
                "provider-absent provider rule",
            )
            _require_fragments(
                _string(families, "failure", f"profile {profile_id} source families"),
                ("not a runtime failure", "abstain"),
                "provider-absent failure rule",
            )
        else:
            _require_fragments(
                provider_rule,
                ("exact provider identity", "abstention"),
                "qualified-morphology provider rule",
            )
        if not _string_list_field(profile, "comparability", "profile"):
            raise RuleCoverageContractError(
                f"profile {profile_id} comparability is empty"
            )


def _validate_metrics(metrics: list[JsonValue]) -> None:
    required = {
        "exact-edit-true-positives",
        "exact-edit-false-positives",
        "exact-edit-false-negatives",
        "exact-edit-precision",
        "exact-edit-recall",
        "exact-edit-f1",
        "exact-half-open-span-accuracy",
        "exact-suggestion-accuracy",
        "correct-sentence-false-alarm-rate",
        "category-counts-and-rates",
        "shape-stratum-counts-and-rates",
        "source-identity-and-behavior-consistency",
        "isolated-runtime-performance",
    }
    parsed = _unique_ids(metrics, "metric")
    if parsed != required:
        raise RuleCoverageContractError(f"metrics must be exactly {sorted(required)}")
    for item in metrics:
        metric = _object(item, "metric")
        _exact_fields(
            metric,
            {
                "id",
                "scope",
                "formula",
                "numerator",
                "denominator",
                "zero_denominator",
                "conflict_handling",
                "abstention_handling",
            },
            "metric",
        )
        for field in (
            "id",
            "scope",
            "formula",
            "numerator",
            "denominator",
            "zero_denominator",
            "conflict_handling",
            "abstention_handling",
        ):
            _string(metric, field, "metric")
        _validate_metric_semantics(metric)


def _validate_metric_semantics(metric: dict[str, JsonValue]) -> None:
    metric_id = _string(metric, "id", "metric")
    required_fragments = {
        "exact-edit-true-positives": (
            ("category", "start", "end", "original", "suggestion"),
            ("unused expected",),
        ),
        "exact-edit-false-positives": (("not matched", "same case"), ()),
        "exact-edit-false-negatives": (("expected findings", "unmatched"), ()),
        "exact-edit-precision": (("TP / (TP + FP)",), ("true positives",)),
        "exact-edit-recall": (("TP / (TP + FN)",), ("false negatives",)),
        "exact-edit-f1": (("2 * TP / (2 * TP + FP + FN)",), ()),
        "exact-half-open-span-accuracy": (
            ("[start, end)", "unused expected", "determinate incorrect cases"),
            ("expected findings",),
        ),
        "exact-suggestion-accuracy": (
            ("suggestion exactly equals",),
            ("matched spans",),
        ),
        "correct-sentence-false-alarm-rate": (
            ("correct cases", "at least one finding"),
            (),
        ),
        "category-counts-and-rates": (("restricting", "category"), ()),
        "shape-stratum-counts-and-rates": (("restricting cases", "stratum"), ()),
        "source-identity-and-behavior-consistency": (
            ("Exact ordered parity",),
            ("fail",),
        ),
        "isolated-runtime-performance": (("protocol-v2",), ("harness",)),
    }
    field_fragments: dict[str, dict[str, tuple[str, ...]]] = {
        "exact-edit-true-positives": {
            "zero_denominator": ("zero",),
            "conflict_handling": ("Exclude conflict cases",),
            "abstention_handling": ("Exclude abstention", "separately"),
        },
        "exact-edit-false-positives": {
            "zero_denominator": ("zero",),
            "conflict_handling": ("Do not convert",),
            "abstention_handling": (
                "abstention violation",
                "not an exact-edit false positive",
            ),
        },
        "exact-edit-false-negatives": {
            "zero_denominator": ("zero",),
            "conflict_handling": ("no determinate edit denominator",),
            "abstention_handling": ("Expected findings are absent",),
        },
        "exact-edit-precision": {
            "zero_denominator": ("null", "gate-unavailable"),
            "conflict_handling": ("determinate",),
            "abstention_handling": ("abstention violations separately",),
        },
        "exact-edit-recall": {
            "zero_denominator": ("null", "gate-unavailable"),
            "conflict_handling": ("determinate",),
            "abstention_handling": ("unavailable and abstention strata separately",),
        },
        "exact-edit-f1": {
            "zero_denominator": ("null", "gate-unavailable"),
            "conflict_handling": ("determinate",),
            "abstention_handling": ("abstention violations separately",),
        },
        "exact-half-open-span-accuracy": {
            "zero_denominator": ("null", "gate-unavailable"),
            "conflict_handling": ("Overlapping conflict findings", "not this rate"),
            "abstention_handling": ("no span denominator",),
        },
        "exact-suggestion-accuracy": {
            "zero_denominator": ("null", "gate-unavailable"),
            "conflict_handling": ("canonical expected suggestion", "ambiguous"),
            "abstention_handling": ("suggestion", "violation"),
        },
        "correct-sentence-false-alarm-rate": {
            "zero_denominator": ("null", "gate-unavailable"),
            "conflict_handling": ("never silently reclassified",),
            "abstention_handling": ("not correct cases",),
        },
        "category-counts-and-rates": {
            "zero_denominator": ("null", "gate-unavailable"),
            "conflict_handling": ("separate in the category report",),
            "abstention_handling": ("Category abstention violations",),
        },
        "shape-stratum-counts-and-rates": {
            "zero_denominator": ("null", "gate-unavailable"),
            "conflict_handling": ("Conflict-or-abstention",),
            "abstention_handling": ("silent omission is invalid",),
        },
        "source-identity-and-behavior-consistency": {
            "zero_denominator": ("missing fields fail",),
            "conflict_handling": ("fail closed",),
            "abstention_handling": ("never a pass",),
        },
        "isolated-runtime-performance": {
            "zero_denominator": ("invalid protocol run",),
            "conflict_handling": ("cannot waive",),
            "abstention_handling": ("unavailable evidence", "fails the gate"),
        },
    }
    rule_fragments, additional_fragments = required_fragments[metric_id]
    text = " ".join(
        _string(metric, field, "metric")
        for field in (
            "formula",
            "numerator",
            "denominator",
            "zero_denominator",
            "conflict_handling",
            "abstention_handling",
        )
    )
    _require_fragments(text, rule_fragments, f"metric {metric_id}")
    _require_fragments(text, additional_fragments, f"metric {metric_id}")
    for field, fragments in field_fragments[metric_id].items():
        _require_fragments(
            _string(metric, field, "metric"),
            fragments,
            f"metric {metric_id} {field}",
        )


def _validate_gates(gates: dict[str, JsonValue]) -> None:
    required = {
        "precision",
        "correct_sentence_false_alarm",
        "category",
        "aggregate_recall",
        "thresholds",
        "evidence",
        "runtime_performance",
    }
    if set(gates) != required:
        raise RuleCoverageContractError(f"gates must be exactly {sorted(required)}")
    for key, value in gates.items():
        gate = _object(value, f"gate {key}")
        _exact_fields(gate, {"rule", "failure_mode"}, f"gate {key}")
        rule = _string(gate, "rule", f"gate {key}")
        failure_mode = _string(gate, "failure_mode", f"gate {key}")
        required_fragments = {
            "precision": ("precision regression", "cannot waive false positives"),
            "correct_sentence_false_alarm": (
                "false-alarm regression",
                "Zero-tolerance",
            ),
            "category": ("supported category", "under-sampled"),
            "aggregate_recall": ("Aggregate recall", "cannot waive"),
            "thresholds": ("reviewed baseline", "does not invent"),
            "evidence": ("public provenance", "not a pass"),
            "runtime_performance": ("protocol-v2", "cannot waive"),
        }
        required_rule, required_failure = required_fragments[key]
        if required_rule not in rule or required_failure not in failure_mode:
            raise RuleCoverageContractError(
                f"gate {key} does not preserve its fail-closed semantics"
            )


def _validate_sampling(sampling: dict[str, JsonValue]) -> None:
    _exact_fields(
        sampling,
        {
            "global_pair_requirement",
            "shape_strata",
            "categories",
            "category_applicability",
            "provider_distinction",
        },
        "sampling",
    )
    _require_fragments(
        _string(sampling, "global_pair_requirement", "sampling"),
        ("Every supported category", "every applicable required shape stratum"),
        "global sampling requirement",
    )
    strata = _list_field(sampling, "shape_strata", "sampling")
    parsed_strata = _unique_ids(strata, "shape stratum")
    if parsed_strata != REQUIRED_SHAPE_STRATA:
        raise RuleCoverageContractError(
            "sampling shape strata must cover every required input shape"
        )
    for item in strata:
        stratum = _object(item, "shape stratum")
        _exact_fields(
            stratum,
            {
                "id",
                "definition",
                "minimum_positive_cases",
                "minimum_hard_negative_cases",
            },
            "shape stratum",
        )
        _string(stratum, "id", "shape stratum")
        _string(stratum, "definition", "shape stratum")
        _positive_integer(stratum, "minimum_positive_cases", "shape stratum")
        _positive_integer(stratum, "minimum_hard_negative_cases", "shape stratum")
    categories = _list_field(sampling, "categories", "sampling")
    if _unique_ids(categories, "category sampling") != SUPPORTED_CATEGORIES:
        raise RuleCoverageContractError(
            "sampling must define agreement, inflection, punctuation, spelling, syntax"
        )
    for item in categories:
        category = _object(item, "category sampling")
        _exact_fields(
            category,
            {
                "id",
                "capability_claim",
                "claim_boundary",
                "minimum_positive_expected_findings",
                "minimum_correct_hard_negative_cases",
                "minimum_phenomenon_or_family_count",
                "minimum_paired_positive_negative_examples",
                "required_shape_strata",
            },
            "category sampling",
        )
        category_id = _string(category, "id", "category sampling")
        _string(category, "capability_claim", "category sampling")
        _string(category, "claim_boundary", "category sampling")
        required_minima = {
            "minimum_positive_expected_findings": 8,
            "minimum_correct_hard_negative_cases": 16,
            "minimum_phenomenon_or_family_count": 3,
            "minimum_paired_positive_negative_examples": 4,
        }
        for field, minimum in required_minima.items():
            value = _positive_integer(
                category, field, f"category sampling {category_id}"
            )
            if value < minimum:
                raise RuleCoverageContractError(
                    f"category sampling {category_id} {field} is below {minimum}"
                )
        if (
            len(
                _string_list_field(
                    category, "required_shape_strata", "category sampling"
                )
            )
            != len(REQUIRED_SHAPE_STRATA)
            or frozenset(
                _string_list_field(
                    category, "required_shape_strata", "category sampling"
                )
            )
            != REQUIRED_SHAPE_STRATA
        ):
            raise RuleCoverageContractError(
                f"category sampling {category_id} omits a required shape stratum"
            )
    applicability = _object_field(sampling, "category_applicability", "sampling")
    if set(applicability) != SUPPORTED_CATEGORIES:
        raise RuleCoverageContractError(
            "category applicability must define every supported category"
        )
    for category_id in SUPPORTED_CATEGORIES:
        category_applicability = _object_field(
            applicability, category_id, "category applicability"
        )
        _exact_fields(
            category_applicability,
            set(REQUIRED_SHAPE_STRATA) | {"not_applicable_reasons"},
            f"category applicability {category_id}",
        )
        reasons = _object_field(
            category_applicability,
            "not_applicable_reasons",
            f"category applicability {category_id}",
        )
        if set(reasons) - REQUIRED_SHAPE_STRATA:
            raise RuleCoverageContractError(
                f"category applicability {category_id} has an unknown reason stratum"
            )
        for stratum_id in REQUIRED_SHAPE_STRATA:
            status = _string(
                category_applicability,
                stratum_id,
                f"category applicability {category_id}",
            )
            if status == "required":
                if stratum_id in reasons:
                    raise RuleCoverageContractError(
                        "required stratum cannot have an applicability reason: "
                        f"{category_id}/{stratum_id}"
                    )
            elif status == "not-applicable":
                _string(
                    reasons,
                    stratum_id,
                    f"category applicability {category_id} reason",
                )
            else:
                raise RuleCoverageContractError(
                    "category applicability has an unknown status: "
                    f"{category_id}/{stratum_id}"
                )
    distinction = _object_field(sampling, "provider_distinction", "sampling")
    _exact_fields(
        distinction,
        {
            "when_applicable",
            "provider_absent_minimum_cases",
            "provider_present_minimum_cases",
        },
        "provider distinction",
    )
    _string(distinction, "when_applicable", "provider distinction")
    if (
        _positive_integer(
            distinction, "provider_absent_minimum_cases", "provider distinction"
        )
        < 2
        or _positive_integer(
            distinction, "provider_present_minimum_cases", "provider distinction"
        )
        < 2
    ):
        raise RuleCoverageContractError(
            "provider distinction minima must be at least 2"
        )


def _validate_ambiguity_policy(policy: dict[str, JsonValue]) -> None:
    required = {
        "overlapping_expected_findings",
        "multiple_valid_corrections",
        "conflicting_rule_families",
        "repeated_occurrences",
        "same_span_different_sources",
        "ambiguous_morphology",
        "correct_text_resembling_template",
        "malformed_or_unsupported_input",
    }
    if set(policy) != required:
        raise RuleCoverageContractError(
            f"ambiguity policy must be exactly {sorted(required)}"
        )
    for key in policy:
        value = _string(policy, key, "ambiguity policy")
        required_fragments = {
            "overlapping_expected_findings": ("explicit conflict", "abstain"),
            "multiple_valid_corrections": ("normative", "ambiguous"),
            "conflicting_rule_families": ("Do not rank", "abstention"),
            "repeated_occurrences": ("independently", "[start, end)"),
            "same_span_different_sources": ("distinct", "drop"),
            "ambiguous_morphology": ("abstention",),
            "correct_text_resembling_template": ("hard negative",),
            "malformed_or_unsupported_input": ("no suggestion",),
        }
        _require_fragments(value, required_fragments[key], f"ambiguity policy {key}")


def _validate_correction_governance(governance: dict[str, JsonValue]) -> None:
    _exact_fields(
        governance,
        {
            "new_family_default",
            "automatic_promotion",
            "automatic_identity_key",
            "automatic_requirements",
        },
        "correction governance",
    )
    _literal(
        governance,
        "new_family_default",
        "review-only",
        "correction governance",
    )
    _string(governance, "automatic_promotion", "correction governance")
    key = _string_list_field(
        governance, "automatic_identity_key", "correction governance"
    )
    if key != [
        "source",
        "category",
        "operation",
        "behavior_version",
        "source_policy_version",
    ]:
        raise RuleCoverageContractError(
            "automatic identity key is incomplete or reordered"
        )
    if (
        len(
            _string_list_field(
                governance, "automatic_requirements", "correction governance"
            )
        )
        < 4
    ):
        raise RuleCoverageContractError(
            "automatic correction requirements are incomplete"
        )


def _validate_source_governance(governance: dict[str, JsonValue]) -> None:
    _exact_fields(
        governance,
        {
            "runtime_snapshot",
            "maintained_rule_inventory",
            "behavior_versions",
            "correction_policy",
            "quality_artifacts",
            "normative_candidate_inventory",
            "parity_failure",
        },
        "source governance",
    )
    snapshot = _object_field(governance, "runtime_snapshot", "source governance")
    _exact_fields(
        snapshot,
        {"derivation", "fields", "order", "digest", "planning_baseline"},
        "runtime snapshot",
    )
    _require_fragments(
        _string(snapshot, "derivation", "runtime snapshot"),
        ("Analyzer(AnalyzerConfig()).source_identity_snapshot",),
        "runtime snapshot derivation",
    )
    if _string_list_field(snapshot, "fields", "runtime snapshot") != [
        "source",
        "operation",
        "behavior_version",
    ]:
        raise RuleCoverageContractError(
            "runtime snapshot fields are incomplete or reordered"
        )
    _require_fragments(
        _string(snapshot, "order", "runtime snapshot"),
        ("registration order", "sets"),
        "runtime snapshot order",
    )
    digest = _object_field(snapshot, "digest", "runtime snapshot")
    _exact_fields(digest, {"algorithm", "canonicalization"}, "runtime snapshot digest")
    _literal(digest, "algorithm", "sha256", "runtime snapshot digest")
    _string(digest, "canonicalization", "runtime snapshot digest")
    baseline = _object_field(snapshot, "planning_baseline", "runtime snapshot")
    _exact_fields(
        baseline, {"full_sha", "source_count", "snapshot_sha256"}, "planning baseline"
    )
    _literal(
        baseline,
        "full_sha",
        PLANNING_BASELINE_FULL_SHA,
        "planning baseline",
    )
    _literal(
        baseline,
        "source_count",
        PLANNING_BASELINE_SOURCE_COUNT,
        "planning baseline",
    )
    _literal(
        baseline,
        "snapshot_sha256",
        PLANNING_BASELINE_SNAPSHOT_SHA256,
        "planning baseline",
    )
    if _string(digest, "canonicalization", "runtime snapshot digest") != (
        "UTF-8 JSON array of ordered identity objects, sorted object keys, "
        "compact separators, ensure_ascii=false."
    ):
        raise RuleCoverageContractError(
            "runtime snapshot canonicalization is not the accepted protocol"
        )
    for field in (
        "maintained_rule_inventory",
        "behavior_versions",
        "correction_policy",
        "quality_artifacts",
        "normative_candidate_inventory",
    ):
        value = _object_field(governance, field, "source governance")
        expected_fields = {"path", "parity_rule"}
        if field == "maintained_rule_inventory":
            expected_fields |= {"rows_sha256", "row_canonicalization"}
        elif field == "correction_policy":
            expected_fields |= {"policy_version", "active_automatic_entries"}
        elif field == "quality_artifacts":
            expected_fields |= {
                "comparison_source_git_sha",
                "comparison_source_snapshot_sha256",
                "comparison_sha256",
                "baseline_source_git_sha",
                "result_source_git_sha",
                "provenance_manifest_path",
                "provenance_manifest_sha256",
            }
        elif field == "normative_candidate_inventory":
            expected_fields |= {"schema_id", "schema_version", "sha256"}
        _exact_fields(value, expected_fields, field)
        path = _string(value, "path", field)
        parity_rule = _string(value, "parity_rule", field)
        required = {
            "maintained_rule_inventory": (
                ("docs/rules.md",),
                (
                    "Every runtime source identity",
                    "missing, extra, duplicate, category, or scope",
                ),
            ),
            "behavior_versions": (
                ("Analyzer.source_identity_snapshot",),
                ("operation", "behavior_version", "error"),
            ),
            "correction_policy": (
                ("src/polis/correction/policy.py",),
                ("complete exact policy key", "unknown status", "fails"),
            ),
            "quality_artifacts": (
                ("docs/quality-comparison-v3.json",),
                (
                    "published source SHA",
                    "dataset identity",
                    "profile",
                    "provider identity",
                    "provenance manifest",
                    "runtime snapshot",
                    "behavior versions",
                ),
            ),
            "normative_candidate_inventory": (
                ("rule-coverage-normative-candidate-inventory-v1.json",),
                ("normative authorities", "candidate sources", "unmapped"),
            ),
        }
        path_fragments, parity_fragments = required[field]
        _require_fragments(path, path_fragments, f"{field} path")
        _require_fragments(parity_rule, parity_fragments, f"{field} parity rule")
        if field == "maintained_rule_inventory":
            rows_sha = _string(value, "rows_sha256", field)
            if re.fullmatch(r"[0-9a-f]{64}", rows_sha) is None:
                raise RuleCoverageContractError(
                    "maintained rule inventory rows digest must be SHA-256"
                )
            if _string(value, "row_canonicalization", field) != (
                "UTF-8 JSON array of ordered source, category, and scope objects, "
                "sorted object keys, compact separators, ensure_ascii=false."
            ):
                raise RuleCoverageContractError(
                    "maintained rule inventory canonicalization is not accepted"
                )
        if field == "quality_artifacts":
            provenance_path = _string(value, "provenance_manifest_path", field)
            if provenance_path != (
                "docs/project/rule-coverage-quality-artifact-provenance-v1.json"
            ):
                raise RuleCoverageContractError(
                    "quality provenance manifest path is not accepted"
                )
            provenance_sha = _string(value, "provenance_manifest_sha256", field)
            if re.fullmatch(r"[0-9a-f]{64}", provenance_sha) is None:
                raise RuleCoverageContractError(
                    "quality provenance manifest digest must be SHA-256"
                )
            comparison_sha = _string(value, "comparison_sha256", field)
            if re.fullmatch(r"[0-9a-f]{64}", comparison_sha) is None:
                raise RuleCoverageContractError(
                    "quality comparison digest must be SHA-256"
                )
            for key in (
                "comparison_source_git_sha",
                "baseline_source_git_sha",
                "result_source_git_sha",
            ):
                source_sha = _string(value, key, "quality artifact governance")
                if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
                    raise RuleCoverageContractError(
                        f"quality artifact governance {key} must be a git SHA"
                    )
            snapshot_sha = value.get("comparison_source_snapshot_sha256")
            if snapshot_sha is not None and (
                not isinstance(snapshot_sha, str)
                or re.fullmatch(r"[0-9a-f]{64}", snapshot_sha) is None
            ):
                raise RuleCoverageContractError(
                    "quality artifact snapshot digest must be null or SHA-256"
                )
        if field == "normative_candidate_inventory":
            _literal(
                value,
                "schema_id",
                "polis.rule-normative-candidate-inventory",
                field,
            )
            _literal(value, "schema_version", 1, field)
            inventory_sha = _string(value, "sha256", field)
            if re.fullmatch(r"[0-9a-f]{64}", inventory_sha) is None:
                raise RuleCoverageContractError(
                    "normative/candidate inventory digest must be SHA-256"
                )
        if field == "correction_policy":
            _literal(value, "policy_version", "1.2", field)
            entries = _list_field(value, "active_automatic_entries", field)
            if not entries:
                raise RuleCoverageContractError(
                    "correction_policy active entries must not be empty"
                )
            seen: set[tuple[str, str, str, str, str]] = set()
            for item in entries:
                entry = _object(item, "correction policy entry")
                _exact_fields(
                    entry,
                    {
                        "source",
                        "category",
                        "operation",
                        "behavior_version",
                        "source_policy_version",
                    },
                    "correction policy entry",
                )
                identity = (
                    _string(entry, "source", "correction policy entry"),
                    _string(entry, "category", "correction policy entry"),
                    _string(entry, "operation", "correction policy entry"),
                    _string(entry, "behavior_version", "correction policy entry"),
                    _string(entry, "source_policy_version", "correction policy entry"),
                )
                if identity in seen:
                    raise RuleCoverageContractError("duplicate correction policy entry")
                seen.add(identity)
    _require_fragments(
        _string(governance, "parity_failure", "source governance"),
        ("Missing", "duplicate", "drift", "fail"),
        "source parity failure",
    )


def _validate_maintainer_approval(approval: dict[str, JsonValue]) -> None:
    _exact_fields(
        approval,
        {"status", "approver", "approved_date", "issue", "scope", "record"},
        "maintainer approval",
    )
    _literal(approval, "status", "approved", "maintainer approval")
    _string(approval, "approver", "maintainer approval")
    _string(approval, "approved_date", "maintainer approval")
    _literal(approval, "issue", 364, "maintainer approval")
    if set(_string_list_field(approval, "scope", "maintainer approval")) != {
        "sampling requirements",
        "gate policy",
    }:
        raise RuleCoverageContractError(
            "maintainer approval must cover sampling and gates"
        )
    _string(approval, "record", "maintainer approval")


def _unique_ids(values: list[JsonValue], label: str) -> set[str]:
    identifiers: list[str] = []
    for value in values:
        item = _object(value, label)
        identifiers.append(_string(item, "id", label))
    if len(set(identifiers)) != len(identifiers):
        raise RuleCoverageContractError(f"duplicate {label} id")
    return set(identifiers)


def _ordered_ids(values: list[JsonValue], label: str) -> tuple[str, ...]:
    identifiers = tuple(_string(_object(value, label), "id", label) for value in values)
    if len(set(identifiers)) != len(identifiers):
        raise RuleCoverageContractError(f"duplicate {label} id")
    return identifiers


def _object(value: JsonValue, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise RuleCoverageContractError(f"{label} must be an object")
    return value


def _object_field(
    value: dict[str, JsonValue],
    field: str,
    label: str,
    *,
    allow_none: bool = False,
) -> dict[str, JsonValue]:
    raw = value.get(field)
    if allow_none and raw is None:
        return {}
    return _object(raw, f"{label}.{field}")


def _list_field(value: dict[str, JsonValue], field: str, label: str) -> list[JsonValue]:
    raw = value.get(field)
    if not isinstance(raw, list):
        raise RuleCoverageContractError(f"{label}.{field} must be a list")
    return raw


def _string_list_field(
    value: dict[str, JsonValue], field: str, label: str
) -> list[str]:
    raw = _list_field(value, field, label)
    if any(not isinstance(item, str) or not item.strip() for item in raw):
        raise RuleCoverageContractError(
            f"{label}.{field} must contain non-empty strings"
        )
    return cast(list[str], raw)


def _string(value: dict[str, JsonValue], field: str, label: str) -> str:
    raw = value.get(field)
    if not isinstance(raw, str) or not raw.strip():
        raise RuleCoverageContractError(f"{label}.{field} must be a non-empty string")
    return raw


def _integer(value: dict[str, JsonValue], field: str, label: str) -> int:
    raw = value.get(field)
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise RuleCoverageContractError(f"{label}.{field} must be an integer")
    return raw


def _positive_integer(value: dict[str, JsonValue], field: str, label: str) -> int:
    raw = _integer(value, field, label)
    if raw < 1:
        raise RuleCoverageContractError(f"{label}.{field} must be positive")
    return raw


def _literal(
    value: dict[str, JsonValue], field: str, expected: JsonValue, label: str
) -> None:
    actual = value.get(field)
    if type(actual) is not type(expected) or actual != expected:
        raise RuleCoverageContractError(f"{label}.{field} must equal {expected!r}")


def _require_fragments(value: str, fragments: tuple[str, ...], label: str) -> None:
    if any(fragment not in value for fragment in fragments):
        raise RuleCoverageContractError(f"{label} does not preserve required semantics")


def _exact_fields(value: dict[str, JsonValue], expected: set[str], label: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise RuleCoverageContractError(
            f"{label} fields mismatch; missing={missing}; extra={extra}"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Validate the checked-in rule-coverage contract and live parity."""

    parser = argparse.ArgumentParser(
        description="Validate the conservative v1 rule-coverage contract."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=CONTRACT_PATH.parents[2],
        help="repository root containing docs/project and docs/rules.md",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()
    path = root / "docs" / "project" / "rule-coverage-contract-v1.json"
    try:
        load_rule_coverage_contract(path, root=root)
    except RuleCoverageContractError as error:
        print(f"rule coverage contract validation failed: {error}", file=sys.stderr)
        return 1
    print("rule coverage contract is valid")
    return 0


__all__ = [
    "CONTRACT_PATH",
    "CONTRACT_SCHEMA_ID",
    "CONTRACT_SCHEMA_VERSION",
    "REQUIRED_SHAPE_STRATA",
    "RuleCoverageContract",
    "RuleCoverageContractError",
    "load_rule_coverage_contract",
    "main",
    "validate_rule_coverage_contract",
]


if __name__ == "__main__":
    raise SystemExit(main())
