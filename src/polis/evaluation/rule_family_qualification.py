"""Validate the pre-approval matrix for deterministic v1 rule families.

The module deliberately owns qualification evidence and GitHub read-only
validation only.  It does not register rules, change correction policy, or
create GitHub issues.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, cast

MATRIX_SCHEMA_ID: Final = "polis.rule-family-qualification"
MATRIX_SCHEMA_VERSION: Final = 1
ISSUE_NUMBER: Final = 368
UMBRELLA_ISSUE_NUMBER: Final = 363
RJP_ISSUE_NUMBER: Final = 365
QUALITY_ISSUE_NUMBER: Final = 367
CONTRACT_ISSUE_NUMBER: Final = 364
MATRIX_RELATIVE_PATH: Final = Path("docs/project/rule-family-qualification-v1.json")
ALLOWED_DISPOSITIONS: Final = frozenset(
    {
        "accept: deterministic provider-absent",
        "accept: deterministic qualified-morphology",
        "reject: normative uncertainty",
        "reject: insufficient public evidence",
        "reject: cannot fail closed",
        "reject: style/semantic/entity/world-knowledge scope",
        "reject: unsupported/new provider dependency",
        "reject: duplicate of current source or #354",
        "defer: explicit maintainer decision required",
    }
)
ACCEPTED_DISPOSITIONS: Final = frozenset(
    {
        "accept: deterministic provider-absent",
        "accept: deterministic qualified-morphology",
    }
)
REQUIRED_PROFILES: Final = ("provider-absent", "qualified-morphology")
REQUIRED_SHAPE_STRATA: Final = (
    "simple-local",
    "sentence-internal",
    "multi-sentence",
    "repeated-occurrence",
    "unicode-and-case",
    "quotation-or-literal",
    "conflict-or-abstention",
)
REQUIRED_ROW_SECTIONS: Final = (
    "identity_and_origin",
    "normative_assessment",
    "deterministic_boundary",
    "output_contract",
    "public_evidence",
    "expected_value",
    "risk_and_cost",
    "decision",
)


class QualificationError(ValueError):
    """Raised when a qualification matrix or child mapping is not fail-closed."""


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise QualificationError(f"{name} must be an object")
    return cast(dict[str, Any], value)


def _list(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise QualificationError(f"{name} must be a list")
    return value


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise QualificationError(f"{name} must be a non-empty string")
    return value


def _repo_root(path: Path) -> Path:
    root = path.resolve()
    if not root.is_dir():
        raise QualificationError(f"repository root is not a directory: {path}")
    return root


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root)
    except ValueError:
        return False
    return True


def load_matrix(path: Path) -> dict[str, Any]:
    """Load a JSON matrix without accepting JSON fragments."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QualificationError(f"cannot read matrix {path}: {error}") from error
    return _object(raw, "matrix")


def _canonical_payload(matrix: Mapping[str, Any]) -> dict[str, Any]:
    payload = copy.deepcopy(dict(matrix))
    # Lifecycle and approval fields attest to the qualification content; they
    # are not themselves qualification content.  Excluding every attestation
    # location keeps the proposal digest stable across the later transition
    # from pre-approval to approved and avoids a circular row-level hash.
    payload.pop("stage", None)
    payload.pop("status", None)
    payload.pop("approval", None)
    integrity = payload.get("integrity")
    if isinstance(integrity, dict):
        integrity.pop("matrix_sha256", None)
        integrity.pop("digest_status", None)
    rows = payload.get("rows")
    if isinstance(rows, list):
        for raw_row in rows:
            if not isinstance(raw_row, dict):
                continue
            decision = raw_row.get("decision")
            if isinstance(decision, dict):
                decision.pop("maintainer_approval", None)
    return payload


def canonical_matrix_bytes(matrix: Mapping[str, Any]) -> bytes:
    """Return the non-circular canonical UTF-8 representation of a matrix."""

    return json.dumps(
        _canonical_payload(matrix),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def matrix_digest(matrix: Mapping[str, Any]) -> str:
    """Calculate the SHA-256 digest bound by a future maintainer approval."""

    return hashlib.sha256(canonical_matrix_bytes(matrix)).hexdigest()


def _load_json(repo: Path, relative: str) -> dict[str, Any]:
    path = repo / relative
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QualificationError(f"cannot read evidence {relative}: {error}") from error
    return _object(raw, relative)


def _rjp_number(row: Mapping[str, Any]) -> str:
    name = _string(row.get("official_number_or_name"), "RJP change name")
    match = re.match(r"RJP-([0-9]+[a-z]?)\s*:", name, re.IGNORECASE)
    if match is None:
        raise QualificationError(f"cannot derive RJP change number from {name!r}")
    return match.group(1).lower()


def _slug(value: str) -> str:
    value = value.lower().replace("/", "-")
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "candidate"


def _input(
    origin_id: str,
    origin_type: str,
    source_issue: int,
    key: str,
    candidate_id: str,
) -> dict[str, Any]:
    return {
        "origin_id": origin_id,
        "origin_type": origin_type,
        "source_issue": source_issue,
        "key": key,
        "candidate_id": candidate_id,
    }


def _v4_gap_inputs(repo: Path) -> list[dict[str, Any]]:
    """Extract only explicit, measured FN gaps from the four v4 artifacts.

    Unmeasured source rows are not gaps: the reviewed v4 handoff distinguishes
    them from false negatives.  No v4 artifact in the accepted handoff emits an
    unexplained gap, so the current result is intentionally an empty list.
    """

    paths = (
        "docs/regression-baseline-v4-default.json",
        "docs/regression-baseline-v4-morphology.json",
        "docs/regression-result-v4-default.json",
        "docs/regression-result-v4-morphology.json",
    )
    gaps: list[dict[str, Any]] = []
    seen: set[str] = set()
    for relative in paths:
        document = _load_json(repo, relative)
        diagnostics = _object(document.get("diagnostics"), f"{relative}.diagnostics")
        source_rows = _list(diagnostics.get("source"), f"{relative}.diagnostics.source")
        profile_document = _object(document.get("profile"), f"{relative}.profile")
        profile = _string(profile_document.get("id"), f"{relative}.profile.id")
        for raw_row in source_rows:
            row = _object(raw_row, f"{relative}.diagnostics.source row")
            count = row.get("false_negative_count", 0)
            if not isinstance(count, int):
                raise QualificationError(
                    f"{relative}: false_negative_count must be an integer"
                )
            if count <= 0:
                continue
            source = _string(row.get("source"), f"{relative}.source")
            key = f"{profile}:{source}"
            if key in seen:
                continue
            seen.add(key)
            candidate_id = f"v4-gap-{_slug(profile)}-{_slug(source)}"
            gaps.append(
                _input(
                    f"issue-367:gap:{key}",
                    "issue-367-unexplained-v4-gap",
                    QUALITY_ISSUE_NUMBER,
                    key,
                    candidate_id,
                )
            )
    return gaps


def expected_input_universe(repo: Path) -> list[dict[str, Any]]:
    """Derive the exact candidate universe from the accepted input artifacts."""

    rjp = _load_json(repo, "docs/project/rule-coverage-rjp-2026.json")
    rows = _list(rjp.get("change_rows"), "RJP audit change_rows")
    result: list[dict[str, Any]] = []
    for raw_row in rows:
        row = _object(raw_row, "RJP audit change row")
        disposition = _string(
            row.get("implementation_disposition"),
            "RJP implementation_disposition",
        )
        number = _rjp_number(row)
        if disposition in {
            "deterministic_v1_candidate",
            "provider_dependent_candidate",
        }:
            candidate_id = f"rjp-2026-{number}"
            result.append(
                _input(
                    f"issue-365:change:RJP-{number.upper()}",
                    "issue-365-candidate",
                    RJP_ISSUE_NUMBER,
                    f"RJP-{number.upper()}",
                    candidate_id,
                )
            )

    source_rows = _list(rjp.get("source_rows"), "RJP audit source_rows")
    for raw_row in source_rows:
        row = _object(raw_row, "RJP audit source row")
        if row.get("conformance_disposition") != "change_required":
            continue
        source = _string(row.get("source"), "change_required source")
        result.append(
            _input(
                f"issue-365:source-change-required:{source}",
                "issue-365-change-required-source",
                RJP_ISSUE_NUMBER,
                source,
                f"source-change-required-{_slug(source)}",
            )
        )

    result.extend(_v4_gap_inputs(repo))

    # The contract has no machine-readable conflict feed.  A conflict is an
    # input only when an accepted artifact explicitly emits one; none does.
    contract = _load_json(repo, "docs/project/rule-coverage-contract-v1.json")
    conflicts = contract.get("actual_conflicts", [])
    if conflicts not in ([], None):
        for raw_conflict in _list(conflicts, "contract actual_conflicts"):
            conflict = _object(raw_conflict, "contract conflict")
            key = _string(conflict.get("id"), "contract conflict id")
            result.append(
                _input(
                    f"issue-364:conflict:{key}",
                    "issue-364-contract-conflict",
                    CONTRACT_ISSUE_NUMBER,
                    key,
                    f"contract-conflict-{_slug(key)}",
                )
            )

    ids = [item["origin_id"] for item in result]
    if len(ids) != len(set(ids)):
        raise QualificationError("input artifacts emit duplicate origin IDs")
    return result


def _require_keys(value: Mapping[str, Any], keys: Iterable[str], name: str) -> None:
    missing = [key for key in keys if key not in value]
    if missing:
        raise QualificationError(
            f"{name} missing required fields: {', '.join(missing)}"
        )


def _require_nonempty_list(value: Mapping[str, Any], key: str, name: str) -> list[Any]:
    items = _list(value.get(key), f"{name}.{key}")
    if not items:
        raise QualificationError(f"{name}.{key} must not be empty")
    return items


def _quality_cases(repo: Path) -> dict[str, dict[str, Any]]:
    dataset = _load_json(repo, "src/polis/evaluation/datasets/quality/v4/cases.json")
    result: dict[str, dict[str, Any]] = {}
    for raw_case in _list(dataset.get("cases"), "quality v4 cases"):
        case = _object(raw_case, "quality v4 case")
        case_id = _string(case.get("id"), "quality v4 case id")
        if case_id in result:
            raise QualificationError(f"duplicate quality v4 case ID: {case_id}")
        result[case_id] = case
    return result


def _evidence_cases(
    evidence: Mapping[str, Any],
    key: str,
    cases: Mapping[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    case_ids = _list(evidence[key], f"row.public_evidence.{key}")
    if len(case_ids) != len(set(case_ids)):
        raise QualificationError(f"accepted row has duplicate {key}")
    resolved: list[dict[str, Any]] = []
    for raw_case_id in case_ids:
        case_id = _string(raw_case_id, f"row.public_evidence.{key} case ID")
        try:
            resolved.append(cases[case_id])
        except KeyError:
            raise QualificationError(
                f"accepted row references unknown public evidence case {case_id}"
            ) from None
    return resolved


def _validate_evidence(
    row: Mapping[str, Any],
    category: str,
    accepted: bool,
    repo: Path,
    proposed_source_identity: str,
) -> None:
    evidence = _object(row.get("public_evidence"), "row.public_evidence")
    _require_keys(
        evidence,
        (
            "v4_positive_case_ids",
            "v4_hard_negative_case_ids",
            "controlled_pair_ids",
            "category_stratum_counts",
            "provider_profile_coverage",
            "conflict_abstention_case_ids",
            "evidence_gaps",
            "executable_risk_evidence",
        ),
        "row.public_evidence",
    )
    for key in (
        "v4_positive_case_ids",
        "v4_hard_negative_case_ids",
        "controlled_pair_ids",
        "conflict_abstention_case_ids",
        "evidence_gaps",
        "executable_risk_evidence",
    ):
        _list(evidence[key], f"row.public_evidence.{key}")

    strata = _object(
        evidence.get("category_stratum_counts"),
        "row.public_evidence.category_stratum_counts",
    )
    category_section = _object(strata.get("category"), "category counts")
    category_counts = _object(
        category_section.get(category), f"category counts for {category}"
    )
    _require_keys(
        category_counts,
        ("positive_cases", "hard_negative_cases", "paired_examples"),
        f"category counts for {category}",
    )
    all_strata = _object(strata.get("shape_strata"), "shape stratum counts")
    for stratum in REQUIRED_SHAPE_STRATA:
        counts = _object(all_strata.get(stratum), f"shape stratum {stratum}")
        _require_keys(counts, ("positive_cases", "hard_negative_cases"), stratum)

    profiles = _object(
        evidence.get("provider_profile_coverage"), "provider profile coverage"
    )
    for profile in REQUIRED_PROFILES:
        coverage = _object(profiles.get(profile), f"profile coverage {profile}")
        _require_keys(
            coverage,
            ("positive_cases", "hard_negative_cases", "status"),
            f"profile coverage {profile}",
        )

    if not accepted:
        return

    if evidence["evidence_gaps"]:
        raise QualificationError("accepted row has public evidence gaps")
    if evidence["executable_risk_evidence"] == []:
        raise QualificationError("accepted row has no executable risk evidence")
    if len(evidence["v4_positive_case_ids"]) < 8:
        raise QualificationError("accepted row lacks required public positives")
    if len(evidence["v4_hard_negative_case_ids"]) < 16:
        raise QualificationError("accepted row lacks required public hard negatives")
    if len(evidence["controlled_pair_ids"]) < 4:
        raise QualificationError("accepted row lacks required controlled pairs")
    if len(evidence["conflict_abstention_case_ids"]) < 1:
        raise QualificationError("accepted row lacks conflict/abstention evidence")

    cases = _quality_cases(repo)
    positives = _evidence_cases(evidence, "v4_positive_case_ids", cases)
    negatives = _evidence_cases(evidence, "v4_hard_negative_case_ids", cases)
    controls = _evidence_cases(evidence, "conflict_abstention_case_ids", cases)
    for case, expected_kind in [
        *((case, "error") for case in positives),
        *((case, "correct") for case in negatives),
    ]:
        case_id = _string(case.get("id"), "evidence case id")
        if case.get("kind") != expected_kind or case.get("category") != category:
            raise QualificationError(
                f"accepted row evidence case {case_id} has wrong kind or category"
            )
        traceability = _object(case.get("traceability"), f"{case_id}.traceability")
        if traceability.get("source_identity") != proposed_source_identity:
            raise QualificationError(
                f"accepted row evidence case {case_id} does not bind proposed source"
            )

    pair_ids = [
        _string(value, "controlled pair ID")
        for value in _list(evidence["controlled_pair_ids"], "controlled pair IDs")
    ]
    if len(pair_ids) != len(set(pair_ids)):
        raise QualificationError("accepted row has duplicate controlled pair IDs")
    positive_pairs = {case.get("pair_id") for case in positives}
    negative_pairs = {case.get("pair_id") for case in negatives}
    if any(
        pair_id not in positive_pairs or pair_id not in negative_pairs
        for pair_id in pair_ids
    ):
        raise QualificationError(
            "accepted row controlled pairs are not backed by selected positive "
            "and hard-negative cases"
        )

    expected_category_counts = {
        "positive_cases": len(positives),
        "hard_negative_cases": len(negatives),
        "paired_examples": len(pair_ids),
    }
    for key, expected_count in expected_category_counts.items():
        if category_counts[key] != expected_count:
            raise QualificationError(
                f"accepted row category {key} does not match public case IDs"
            )
    for stratum in REQUIRED_SHAPE_STRATA:
        counts = cast(dict[str, Any], all_strata[stratum])
        positive_count = sum(
            stratum in _list(case.get("shape_strata"), "positive shape strata")
            for case in positives
        )
        negative_count = sum(
            stratum in _list(case.get("shape_strata"), "negative shape strata")
            for case in negatives
        )
        if (
            counts["positive_cases"] != positive_count
            or counts["hard_negative_cases"] != negative_count
        ):
            raise QualificationError(
                f"accepted row {stratum} counts do not match public case IDs"
            )
        if positive_count < 1 or negative_count < 1:
            raise QualificationError(f"accepted row lacks complete {stratum} evidence")
    for profile in REQUIRED_PROFILES:
        coverage = cast(dict[str, Any], profiles[profile])
        provider_key = profile.replace("-", "_")
        positive_count = sum(
            _object(case.get("provider_behavior"), "positive provider behavior").get(
                provider_key
            )
            == "execute"
            for case in positives
        )
        negative_count = sum(
            _object(case.get("provider_behavior"), "negative provider behavior").get(
                provider_key
            )
            == "execute"
            for case in negatives
        )
        if (
            coverage["positive_cases"] != positive_count
            or coverage["hard_negative_cases"] != negative_count
        ):
            raise QualificationError(
                f"accepted row {profile} counts do not match public case IDs"
            )
        if positive_count < 2 or negative_count < 2:
            raise QualificationError(f"accepted row lacks complete {profile} evidence")
    for control in controls:
        case_id = _string(control.get("id"), "control case id")
        control_strata = _list(control.get("shape_strata"), f"{case_id}.shape_strata")
        if (
            control.get("kind") not in {"conflict", "abstention"}
            or "conflict-or-abstention" not in control_strata
        ):
            raise QualificationError(
                f"accepted row control {case_id} is not conflict/abstention evidence"
            )
    for raw_path in _list(
        evidence["executable_risk_evidence"], "executable risk evidence"
    ):
        relative = Path(_string(raw_path, "executable risk evidence path"))
        evidence_path = repo / relative
        if (
            relative.is_absolute()
            or not _inside(evidence_path, repo)
            or not evidence_path.is_file()
        ):
            raise QualificationError(
                "accepted row executable risk evidence is not a repository file: "
                f"{relative}"
            )


def _validate_row(
    row: Mapping[str, Any],
    expected: Mapping[str, Any],
    *,
    stage: str,
    matrix_digest_value: str,
    repo: Path,
) -> None:
    _require_keys(row, REQUIRED_ROW_SECTIONS + ("input_origins",), "qualification row")
    identity = _object(row["identity_and_origin"], "row.identity_and_origin")
    _require_keys(
        identity,
        (
            "candidate_id",
            "proposed_family_name",
            "category",
            "phenomenon",
            "originating_365_audit_rows",
            "originating_367_gap_case_ids",
            "current_related_source_identities",
            "exact_normative_references",
            "proposed_provider_profile",
        ),
        "row.identity_and_origin",
    )
    candidate_id = _string(identity["candidate_id"], "candidate_id")
    if candidate_id != expected["candidate_id"]:
        raise QualificationError(
            f"origin {expected['origin_id']} maps to {candidate_id}, "
            f"expected {expected['candidate_id']}"
        )
    category = _string(identity["category"], "row category")
    if category not in {"agreement", "inflection", "punctuation", "spelling", "syntax"}:
        raise QualificationError(f"unsupported row category: {category}")
    _require_nonempty_list(identity, "exact_normative_references", "identity")
    for key in (
        "originating_365_audit_rows",
        "originating_367_gap_case_ids",
        "current_related_source_identities",
    ):
        _list(identity[key], f"identity.{key}")

    origins = _list(row["input_origins"], "row.input_origins")
    if len(origins) != 1:
        raise QualificationError(
            f"{candidate_id} must map exactly one candidate-universe input"
        )
    origin = _object(origins[0], "row input origin")
    if origin.get("origin_id") != expected["origin_id"]:
        raise QualificationError(
            f"{candidate_id} has incorrect origin mapping: {origin.get('origin_id')!r}"
        )

    normative = _object(row["normative_assessment"], "row.normative_assessment")
    _require_keys(
        normative,
        (
            "normative_certainty",
            "effective_date",
            "behavior_status",
            "rationale",
            "unresolved_normative_questions",
        ),
        "row.normative_assessment",
    )
    if normative["normative_certainty"] not in {"clear", "uncertain", "not-governed"}:
        raise QualificationError("invalid normative certainty")
    _list(
        normative["unresolved_normative_questions"],
        "normative unresolved questions",
    )

    expected_value = _object(row["expected_value"], "row.expected_value")
    _require_keys(
        expected_value,
        (
            "exact_v4_false_negatives",
            "expected_category_recall_delta",
            "expected_aggregate_delta_context_only",
            "source_or_phenomenon_coverage",
            "user_value_rationale",
        ),
        "row.expected_value",
    )
    for key in ("exact_v4_false_negatives", "source_or_phenomenon_coverage"):
        _list(expected_value[key], f"expected value.{key}")
    for key in (
        "expected_category_recall_delta",
        "expected_aggregate_delta_context_only",
        "user_value_rationale",
    ):
        _string(expected_value[key], f"expected value.{key}")

    risk = _object(row["risk_and_cost"], "row.risk_and_cost")
    _require_keys(
        risk,
        (
            "false_positive_risk",
            "conflicts_with_current_sources",
            "ambiguity_risk",
            "provider_drift_risk",
            "offset_suggestion_risk",
            "correction_policy_interaction",
            "estimated_dispatch_performance_cost",
            "maintenance_norm_change_risk",
            "mitigation_or_abstention_strategy",
            "executable_risk_evidence",
        ),
        "row.risk_and_cost",
    )
    if risk["false_positive_risk"] not in {"low", "medium", "high"}:
        raise QualificationError("invalid false-positive risk")
    for key in (
        "conflicts_with_current_sources",
        "ambiguity_risk",
        "provider_drift_risk",
        "offset_suggestion_risk",
        "correction_policy_interaction",
        "estimated_dispatch_performance_cost",
        "maintenance_norm_change_risk",
        "mitigation_or_abstention_strategy",
    ):
        _string(risk[key], f"risk.{key}")
    _list(risk["executable_risk_evidence"], "risk.executable_risk_evidence")

    boundary = _object(row["deterministic_boundary"], "row.deterministic_boundary")
    _require_keys(
        boundary,
        (
            "exact_locally_observable_trigger",
            "token_context_window",
            "explicit_exclusions",
            "case_unicode_punctuation_handling",
            "repeated_occurrence_and_multi_sentence",
            "quotation_literal_behavior",
            "overlap_conflict_behavior",
            "provider_absent_behavior",
            "fail_closed_conditions",
        ),
        "row.deterministic_boundary",
    )
    for key in (
        "exact_locally_observable_trigger",
        "token_context_window",
        "case_unicode_punctuation_handling",
        "repeated_occurrence_and_multi_sentence",
        "quotation_literal_behavior",
        "overlap_conflict_behavior",
        "provider_absent_behavior",
    ):
        _string(boundary[key], f"boundary.{key}")
    for key in ("explicit_exclusions", "fail_closed_conditions"):
        _list(boundary[key], f"boundary.{key}")

    output = _object(row["output_contract"], "row.output_contract")
    _require_keys(
        output,
        (
            "category",
            "operation_type",
            "exact_half_open_span_rule",
            "exact_minimal_suggestion_rule",
            "confidence_policy",
            "proposed_source_identity",
            "proposed_behavior_version",
            "review_only_first",
        ),
        "row.output_contract",
    )
    if output["category"] != category:
        raise QualificationError("row identity and output categories differ")
    for key in (
        "operation_type",
        "exact_half_open_span_rule",
        "exact_minimal_suggestion_rule",
        "confidence_policy",
        "proposed_source_identity",
        "proposed_behavior_version",
    ):
        _string(output[key], f"output.{key}")
    if output["review_only_first"] is not True:
        raise QualificationError("qualification output must be review-only first")

    decision = _object(row["decision"], "row.decision")
    _require_keys(
        decision,
        (
            "disposition",
            "rationale",
            "maintainer_approval",
            "reopening_evidence",
            "child_allowed",
        ),
        "row.decision",
    )
    disposition = _string(decision["disposition"], "row disposition")
    if disposition not in ALLOWED_DISPOSITIONS:
        raise QualificationError(f"invalid disposition: {disposition}")
    if not isinstance(decision["child_allowed"], bool):
        raise QualificationError("decision.child_allowed must be boolean")
    approval = _object(decision["maintainer_approval"], "row maintainer approval")
    _require_keys(
        approval,
        ("status", "approved_by", "approved_at", "bound_matrix_sha256"),
        "row approval",
    )
    if stage == "pre-approval":
        if approval["status"] != "pending" or approval["approved_by"] is not None:
            raise QualificationError("row maintainer approval must remain pending")
        if (
            approval["approved_at"] is not None
            or approval["bound_matrix_sha256"] is not None
        ):
            raise QualificationError("pre-approval row cannot bind approval")
    else:
        if approval["status"] != "approved":
            raise QualificationError("approved row must declare approved status")
        if approval["approved_by"] != "Paweł Cyroń":
            raise QualificationError("approved row has an unexpected approver")
        if not isinstance(approval["approved_at"], str) or not approval["approved_at"]:
            raise QualificationError("approved row needs approved_at")
        if approval["bound_matrix_sha256"] != matrix_digest_value:
            raise QualificationError("row approval is not bound to the matrix digest")
    _list(decision["reopening_evidence"], "row reopening evidence")
    if disposition not in ACCEPTED_DISPOSITIONS:
        if decision["child_allowed"]:
            raise QualificationError("rejected or deferred row cannot allow a child")
        if not decision["reopening_evidence"]:
            raise QualificationError(
                "rejected or deferred row needs reopening evidence"
            )
        if not _string(decision["rationale"], "decision rationale"):
            raise QualificationError("rejected or deferred row needs rationale")
    else:
        if decision["child_allowed"] is not True:
            raise QualificationError("accepted row must allow exactly one future child")
        if normative["normative_certainty"] != "clear":
            raise QualificationError("accepted row needs clear normative certainty")

    _validate_evidence(
        row,
        category,
        disposition in ACCEPTED_DISPOSITIONS,
        repo,
        _string(output["proposed_source_identity"], "proposed source identity"),
    )


def _priority_key(row: Mapping[str, Any]) -> tuple[int, ...]:
    identity = _object(row["identity_and_origin"], "row.identity_and_origin")
    evidence = _object(row["public_evidence"], "row.public_evidence")
    risk = _object(row["risk_and_cost"], "row.risk_and_cost")
    provider = identity.get("proposed_provider_profile")
    evidence_score = len(_list(evidence.get("v4_positive_case_ids"), "positive IDs"))
    false_positive = _string(risk.get("false_positive_risk"), "false positive risk")
    risk_score = (
        0 if false_positive == "low" else 1 if false_positive == "medium" else 2
    )
    provider_score = 0 if provider == "provider-absent" else 1
    scope_score = 0
    if "broad" in _string(risk.get("estimated_dispatch_performance_cost"), "cost"):
        scope_score = 1
    # Python's tuple comparison is reproducible.  The candidate ID is applied
    # as an explicit final key by _validate_prioritization, avoiding locale or
    # process-randomized ordering.
    return (-evidence_score, risk_score, provider_score, scope_score)


def _validate_prioritization(
    matrix: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]
) -> None:
    prioritization = _object(matrix.get("prioritization"), "prioritization")
    _require_keys(
        prioritization,
        (
            "method",
            "dimensions",
            "precision_safety_rule",
            "accepted_row_ids",
            "ranked_rows",
            "tie_breaker",
        ),
        "prioritization",
    )
    accepted = sorted(
        [
            row
            for row in rows
            if _object(row["decision"], "row.decision")["disposition"]
            in ACCEPTED_DISPOSITIONS
        ],
        key=lambda row: (
            _priority_key(row),
            _string(
                _object(row["identity_and_origin"], "row.identity_and_origin")[
                    "candidate_id"
                ],
                "candidate id",
            ),
        ),
    )
    expected_ids = [
        _string(
            _object(row["identity_and_origin"], "row.identity_and_origin")[
                "candidate_id"
            ],
            "candidate id",
        )
        for row in accepted
    ]
    actual_ids = _list(prioritization["accepted_row_ids"], "accepted_row_ids")
    ranked = _list(prioritization["ranked_rows"], "ranked_rows")
    if actual_ids != expected_ids:
        raise QualificationError("prioritization accepted_row_ids is not reproducible")
    if [
        _string(_object(item, "ranked row").get("candidate_id"), "ranked candidate id")
        for item in ranked
    ] != expected_ids:
        raise QualificationError("prioritization ranked_rows is not reproducible")
    if not _string(prioritization["precision_safety_rule"], "precision safety rule"):
        raise QualificationError("prioritization needs a precision safety rule")


def validate_matrix_document(matrix: Mapping[str, Any], repo: Path) -> dict[str, Any]:
    """Validate schema, exact input parity, admissions, digest, and ranking."""

    root = _repo_root(repo)
    _require_keys(
        matrix,
        (
            "schema_id",
            "schema_version",
            "stage",
            "issue",
            "parent_issue",
            "candidate_universe",
            "rows",
            "prioritization",
            "approval",
            "canonicalization",
            "integrity",
            "child_issue_template",
        ),
        "matrix",
    )
    if (
        matrix["schema_id"] != MATRIX_SCHEMA_ID
        or matrix["schema_version"] != MATRIX_SCHEMA_VERSION
    ):
        raise QualificationError("unsupported qualification matrix schema")
    if (
        matrix["stage"] not in {"pre-approval", "approved"}
        or matrix["issue"] != ISSUE_NUMBER
    ):
        raise QualificationError(
            "matrix is not a supported #368 qualification artifact"
        )
    if matrix["parent_issue"] != UMBRELLA_ISSUE_NUMBER:
        raise QualificationError("matrix parent issue mismatch")

    canonicalization = _object(matrix["canonicalization"], "canonicalization")
    _require_keys(
        canonicalization,
        ("algorithm", "encoding", "json", "excluded_paths", "digest_field"),
        "canonicalization",
    )
    if (
        canonicalization["algorithm"] != "SHA-256"
        or canonicalization["encoding"] != "UTF-8"
    ):
        raise QualificationError("unsupported matrix digest canonicalization")
    if canonicalization["excluded_paths"] != [
        "stage",
        "status",
        "approval",
        "integrity.matrix_sha256",
        "integrity.digest_status",
        "rows[*].decision.maintainer_approval",
    ]:
        raise QualificationError("matrix digest exclusions are not canonical")
    integrity = _object(matrix["integrity"], "integrity")
    digest = _string(integrity.get("matrix_sha256"), "integrity.matrix_sha256")
    calculated = matrix_digest(matrix)
    if digest != calculated:
        raise QualificationError(
            f"matrix digest mismatch: recorded {digest}, calculated {calculated}"
        )
    if integrity.get("digest_status") not in {"proposal", "approved"}:
        raise QualificationError("matrix digest has an unsupported status")

    approval = _object(matrix["approval"], "approval")
    _require_keys(
        approval,
        (
            "status",
            "decision_owner",
            "approved_by",
            "approved_at",
            "bound_matrix_sha256",
            "child_creation_allowed",
        ),
        "approval",
    )
    if approval["decision_owner"] != "Paweł Cyroń":
        raise QualificationError("unexpected maintainer decision owner")
    if matrix["stage"] == "pre-approval":
        if approval["status"] != "pending" or approval["approved_by"] is not None:
            raise QualificationError("maintainer approval must remain PENDING")
        if (
            approval["bound_matrix_sha256"] is not None
            or approval["approved_at"] is not None
        ):
            raise QualificationError("PRE-APPROVAL matrix cannot bind final approval")
        if approval["child_creation_allowed"] is not False:
            raise QualificationError(
                "child creation must remain disabled before approval"
            )
    else:
        if approval["status"] != "approved":
            raise QualificationError("approved matrix must declare approved status")
        if approval["approved_by"] != "Paweł Cyroń":
            raise QualificationError("approved matrix has an unexpected approver")
        if not isinstance(approval["approved_at"], str) or not approval["approved_at"]:
            raise QualificationError("approved matrix needs approved_at")
        if approval["bound_matrix_sha256"] != digest:
            raise QualificationError("approval is not bound to the matrix digest")
        if approval["child_creation_allowed"] is not True:
            raise QualificationError("approved matrix must enable child validation")

    universe = _object(matrix["candidate_universe"], "candidate_universe")
    _require_keys(
        universe,
        ("definition", "inputs", "unexplained_v4_gap_count", "contract_conflict_count"),
        "candidate_universe",
    )
    inputs = _list(universe["inputs"], "candidate_universe.inputs")
    expected = expected_input_universe(root)
    expected_by_origin = {item["origin_id"]: item for item in expected}
    actual_by_origin: dict[str, dict[str, Any]] = {}
    for raw_input in inputs:
        item = _object(raw_input, "candidate universe input")
        origin_id = _string(item.get("origin_id"), "candidate universe origin_id")
        if origin_id in actual_by_origin:
            raise QualificationError(f"duplicate candidate-universe input: {origin_id}")
        actual_by_origin[origin_id] = item
        if origin_id not in expected_by_origin:
            raise QualificationError(f"unrelated candidate-universe input: {origin_id}")
        for key in ("origin_type", "source_issue", "key", "candidate_id"):
            if item.get(key) != expected_by_origin[origin_id][key]:
                raise QualificationError(
                    f"candidate-universe metadata mismatch for {origin_id}"
                )
    if set(actual_by_origin) != set(expected_by_origin):
        missing = sorted(set(expected_by_origin) - set(actual_by_origin))
        extra = sorted(set(actual_by_origin) - set(expected_by_origin))
        raise QualificationError(
            f"candidate-universe parity failure; missing={missing}, extra={extra}"
        )
    if universe["unexplained_v4_gap_count"] != sum(
        item["origin_type"] == "issue-367-unexplained-v4-gap" for item in expected
    ):
        raise QualificationError("v4 gap count does not match emitted gaps")
    if universe["contract_conflict_count"] != sum(
        item["origin_type"] == "issue-364-contract-conflict" for item in expected
    ):
        raise QualificationError(
            "contract conflict count does not match emitted conflicts"
        )

    rows = _list(matrix["rows"], "rows")
    row_by_id: dict[str, Mapping[str, Any]] = {}
    mapped_origins: list[str] = []
    for raw_row in rows:
        row = _object(raw_row, "qualification row")
        identity = _object(row.get("identity_and_origin"), "row.identity_and_origin")
        candidate_id = _string(identity.get("candidate_id"), "candidate_id")
        if candidate_id in row_by_id:
            raise QualificationError(f"duplicate qualification row: {candidate_id}")
        row_by_id[candidate_id] = row
        origins = _list(row.get("input_origins"), f"{candidate_id}.input_origins")
        mapped_origins.extend(
            _string(_object(origin, "input origin").get("origin_id"), "origin_id")
            for origin in origins
        )
        expected_candidates = [
            item for item in expected if item["candidate_id"] == candidate_id
        ]
        if len(expected_candidates) != 1:
            raise QualificationError(
                f"unknown or duplicated candidate row: {candidate_id}"
            )
        _validate_row(
            row,
            expected_candidates[0],
            stage=cast(str, matrix["stage"]),
            matrix_digest_value=digest,
            repo=root,
        )
    if len(mapped_origins) != len(set(mapped_origins)):
        raise QualificationError("candidate-universe input is mapped more than once")
    if set(mapped_origins) != set(expected_by_origin):
        raise QualificationError(
            "qualification rows do not map the exact input universe"
        )
    if set(row_by_id) != {item["candidate_id"] for item in expected}:
        raise QualificationError("qualification row candidate parity failure")

    _validate_prioritization(matrix, list(row_by_id.values()))
    return {
        "matrix_sha256": digest,
        "candidate_count": len(rows),
        "accepted_count": sum(
            _object(row["decision"], "row.decision")["disposition"]
            in ACCEPTED_DISPOSITIONS
            for row in rows
        ),
        "dispositions": {
            disposition: sum(
                _object(row["decision"], "row.decision")["disposition"] == disposition
                for row in rows
            )
            for disposition in sorted(ALLOWED_DISPOSITIONS)
            if any(
                _object(row["decision"], "row.decision")["disposition"] == disposition
                for row in rows
            )
        },
    }


def validate_matrix(path: Path, repo: Path) -> dict[str, Any]:
    """Load and validate a matrix path inside ``repo``."""

    root = _repo_root(repo)
    matrix_path = path if path.is_absolute() else root / path
    if not _inside(matrix_path, root):
        raise QualificationError("matrix must be inside the repository")
    return validate_matrix_document(load_matrix(matrix_path), root)


def _github_issues(repo: str) -> list[dict[str, Any]]:
    """Read all repository issues through an explicitly GET-only gh command."""

    if not re.fullmatch(r"[^/\s]+/[^/\s]+", repo):
        raise QualificationError("--repo must be OWNER/REPOSITORY")
    command = [
        "gh",
        "api",
        "--method",
        "GET",
        "--paginate",
        "--slurp",
        f"repos/{repo}/issues?state=all&per_page=100",
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError as error:
        raise QualificationError(
            f"cannot run read-only GitHub query: {error}"
        ) from error
    if completed.returncode != 0:
        raise QualificationError(
            f"read-only GitHub query failed: {completed.stderr.strip()}"
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise QualificationError(f"GitHub returned invalid JSON: {error}") from error
    pages: list[Any]
    if isinstance(payload, list) and all(isinstance(page, list) for page in payload):
        pages = payload
    elif isinstance(payload, list):
        pages = [payload]
    else:
        raise QualificationError("GitHub issue response must be a JSON array")
    return [_object(issue, "GitHub issue") for page in pages for issue in page]


def _issue_labels(issue: Mapping[str, Any]) -> set[str]:
    labels = _list(issue.get("labels"), "GitHub issue labels")
    result: set[str] = set()
    for raw_label in labels:
        if isinstance(raw_label, str):
            result.add(raw_label)
        else:
            label = _object(raw_label, "GitHub issue label")
            result.add(_string(label.get("name"), "GitHub label name"))
    return result


def validate_children_document(
    matrix: Mapping[str, Any], issues: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Validate exact live child discovery against an already fetched issue list."""

    # The CLI performs full repository-backed validation first.  This helper
    # independently enforces the approval and digest boundary as well, so a
    # caller using mocked live issues cannot validate a child before approval.
    rows = _list(matrix.get("rows"), "rows")
    expected_by_id: dict[str, Mapping[str, Any]] = {}
    for raw_row in rows:
        row = _object(raw_row, "qualification row")
        identity = _object(row.get("identity_and_origin"), "row.identity_and_origin")
        candidate_id = _string(identity.get("candidate_id"), "candidate_id")
        expected_by_id[candidate_id] = row

    accepted_rows = [
        row
        for row in expected_by_id.values()
        if _object(row.get("decision"), "row.decision").get("disposition")
        in ACCEPTED_DISPOSITIONS
    ]
    integrity = _object(matrix.get("integrity"), "integrity")
    digest = _string(integrity.get("matrix_sha256"), "integrity.matrix_sha256")
    if digest != matrix_digest(matrix):
        raise QualificationError("child validation matrix digest mismatch")
    if accepted_rows:
        approval = _object(matrix.get("approval"), "approval")
        if (
            matrix.get("stage") != "approved"
            or approval.get("status") != "approved"
            or approval.get("approved_by") != "Paweł Cyroń"
            or not isinstance(approval.get("approved_at"), str)
            or not approval.get("approved_at")
            or approval.get("bound_matrix_sha256") != digest
            or approval.get("child_creation_allowed") is not True
        ):
            raise QualificationError(
                "accepted children require final maintainer approval bound to "
                "the matrix digest"
            )
        for accepted_row in accepted_rows:
            decision = _object(accepted_row.get("decision"), "row.decision")
            row_approval = _object(
                decision.get("maintainer_approval"), "row maintainer approval"
            )
            if (
                row_approval.get("status") != "approved"
                or row_approval.get("approved_by") != "Paweł Cyroń"
                or not isinstance(row_approval.get("approved_at"), str)
                or not row_approval.get("approved_at")
                or row_approval.get("bound_matrix_sha256") != digest
            ):
                raise QualificationError(
                    "accepted child row lacks final approval bound to the matrix digest"
                )

    markers: dict[str, list[Mapping[str, Any]]] = {key: [] for key in expected_by_id}
    marker_prefix = "Qualification row ID:"
    for live_issue in issues:
        body = live_issue.get("body")
        if not isinstance(body, str):
            body = ""
        for candidate_id in expected_by_id:
            marker = f"{marker_prefix} {candidate_id}"
            if body.count(marker) != 0:
                # A marker repeated in one body is also a duplicate mapping.
                markers[candidate_id].extend([live_issue] * body.count(marker))

    errors: list[str] = []
    accepted_ids: list[str] = []
    template = _object(matrix.get("child_issue_template"), "child_issue_template")
    required_sections = [
        _string(x, "template section")
        for x in _list(template.get("required_body_sections"), "template sections")
    ]
    metadata = _object(template.get("required_metadata"), "template metadata")
    for candidate_id, qualification_row in expected_by_id.items():
        decision = _object(qualification_row["decision"], "row.decision")
        disposition = _string(decision["disposition"], "disposition")
        matches = markers[candidate_id]
        if disposition not in ACCEPTED_DISPOSITIONS:
            if matches:
                errors.append(f"child exists for rejected/deferred row {candidate_id}")
            continue
        accepted_ids.append(candidate_id)
        if len(matches) != 1:
            errors.append(
                f"expected exactly one child for {candidate_id}, found {len(matches)}"
            )
            continue
        live_issue = matches[0]
        body = cast(str, live_issue.get("body", ""))
        for section in required_sections:
            if section not in body:
                errors.append(f"child {candidate_id} missing template text: {section}")
        identity = _object(
            qualification_row["identity_and_origin"], "row.identity_and_origin"
        )
        output = _object(qualification_row["output_contract"], "row.output_contract")
        evidence = _object(qualification_row["public_evidence"], "row.public_evidence")
        exact_body_values = (
            ("Qualification matrix SHA-256:", digest),
            ("Disposition:", _string(decision.get("disposition"), "disposition")),
            (
                "Proposed source identity:",
                _string(output.get("proposed_source_identity"), "source identity"),
            ),
            (
                "Proposed behavior version:",
                _string(output.get("proposed_behavior_version"), "behavior version"),
            ),
            (
                "Supported provider profile:",
                _string(identity.get("proposed_provider_profile"), "provider profile"),
            ),
        )
        for label, value in exact_body_values:
            if f"{label} {value}" not in body:
                errors.append(
                    f"child {candidate_id} misses exact {label.lower()} value"
                )
        for evidence_key, label in (
            ("v4_positive_case_ids", "v4 positive case IDs"),
            ("v4_hard_negative_case_ids", "v4 hard-negative case IDs"),
            ("controlled_pair_ids", "controlled pair IDs"),
        ):
            values = _list(evidence.get(evidence_key), f"{candidate_id}.{evidence_key}")
            if values and not all(f"{value}" in body for value in values):
                errors.append(f"child {candidate_id} misses exact {label}")
        for key, expected_value in metadata.items():
            if key == "labels":
                if not set(cast(list[str], expected_value)) <= _issue_labels(
                    live_issue
                ):
                    errors.append(f"child {candidate_id} has incorrect labels")
            elif key == "milestone":
                milestone = live_issue.get("milestone")
                title = milestone.get("title") if isinstance(milestone, dict) else None
                if title != expected_value:
                    errors.append(f"child {candidate_id} has incorrect milestone")
            elif key == "title_prefix":
                title = live_issue.get("title")
                if not isinstance(title, str) or not title.startswith(expected_value):
                    errors.append(f"child {candidate_id} has incorrect title")
            elif key == "state":
                if live_issue.get("state") != expected_value:
                    errors.append(f"child {candidate_id} has incorrect state")
            elif key == "parent_issue":
                if f"Parent #{expected_value}" not in body:
                    errors.append(
                        f"child {candidate_id} misses Parent #{expected_value}"
                    )
            elif key == "umbrella_issue":
                if f"Umbrella #{expected_value}" not in body:
                    errors.append(
                        f"child {candidate_id} misses Umbrella #{expected_value}"
                    )
            elif key == "blocked_by":
                for dependency in cast(list[int], expected_value):
                    if f"#{dependency}" not in body:
                        errors.append(
                            f"child {candidate_id} misses blocked-by #{dependency}"
                        )

    unknown_markers: set[str] = set()
    for issue in issues:
        body = issue.get("body")
        if not isinstance(body, str) or marker_prefix not in body:
            continue
        for match in re.findall(r"Qualification row ID:\s*([^\s#]+)", body):
            if match not in expected_by_id:
                unknown_markers.add(match)
    issue_candidate_ids: dict[int, set[str]] = {}
    for candidate_id, matches in markers.items():
        for live_issue in matches:
            issue_candidate_ids.setdefault(id(live_issue), set()).add(candidate_id)
    for candidate_ids in issue_candidate_ids.values():
        if len(candidate_ids) > 1:
            errors.append(
                "one live child maps multiple qualification rows: "
                + ", ".join(sorted(candidate_ids))
            )
    if unknown_markers:
        errors.append(
            f"child maps unknown qualification rows: {sorted(unknown_markers)}"
        )
    if errors:
        raise QualificationError("; ".join(errors))
    return {"accepted_count": len(accepted_ids), "validated_child_ids": accepted_ids}


def validate_children(
    path: Path,
    repo: Path,
    issues: Sequence[Mapping[str, Any]] | None = None,
    *,
    github_repo: str = "PSyron/polis",
) -> dict[str, Any]:
    """Validate the matrix and then perform a read-only live-child check."""

    root = _repo_root(repo)
    matrix_path = path if path.is_absolute() else root / path
    if not _inside(matrix_path, root):
        raise QualificationError("matrix must be inside the repository")
    matrix = load_matrix(matrix_path)
    validate_matrix_document(matrix, root)
    live_issues = list(issues) if issues is not None else _github_issues(github_repo)
    return validate_children_document(matrix, live_issues)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate #368 rule-family qualification"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate-matrix", "validate-children"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--matrix", type=Path, required=True)
        sub.add_argument(
            "--repo",
            required=True,
            help=(
                "GitHub OWNER/REPOSITORY for validate-children; "
                "local root for validate-matrix"
            ),
        )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-matrix":
            local_root = Path(args.repo)
            if not local_root.is_dir():
                raise QualificationError(
                    "validate-matrix --repo must be a local repository root"
                )
            result = validate_matrix(args.matrix, local_root)
        else:
            # The documented command uses --repo OWNER/REPOSITORY.  Matrix
            # paths are resolved from the current checkout, while GitHub is
            # queried with a GET-only gh api call.
            result = validate_children(
                args.matrix,
                Path.cwd(),
                github_repo=args.repo,
            )
    except QualificationError as error:
        print(f"qualification validation failed: {error}")
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


__all__ = [
    "ALLOWED_DISPOSITIONS",
    "ACCEPTED_DISPOSITIONS",
    "QualificationError",
    "canonical_matrix_bytes",
    "expected_input_universe",
    "load_matrix",
    "main",
    "matrix_digest",
    "validate_children_document",
    "validate_matrix",
    "validate_matrix_document",
]


if __name__ == "__main__":
    raise SystemExit(main())
