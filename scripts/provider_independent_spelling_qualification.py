from __future__ import annotations

import argparse
import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from scripts.morphology_provider_json import (
    ContractError,
    JsonValue,
    boolean,
    canonical_bytes,
    exact_fields,
    integer,
    mapping,
    string,
)

REQUIRED_SHAPE_STRATA: Final = (
    "simple-local",
    "sentence-internal",
    "multi-sentence",
    "repeated-occurrence",
    "unicode-and-case",
    "quotation-or-literal",
    "conflict-or-abstention",
)
MINIMUM_POSITIVE_FINDINGS: Final = 8
MINIMUM_POSITIVE_CASES: Final = 8
MINIMUM_HARD_NEGATIVES: Final = 16
MINIMUM_CONTROLLED_PAIRS: Final = 4
DATASET_ID: Final = "polis-provider-independent-spelling-qualification-v1"
APPROVED_EVIDENCE_SHA256: Final = (
    "a82a4c93338e9bde8ea011f89d47010642a74ed43800cec53b8f298c6b46f727"
)
APPROVED_CASE_ID_SHA256: Final = (
    "44e0adf2322307827329285da4b474083e332eb656164a331b5a87741ec66168"
)
APPROVED_MATRIX_SHA256: Final = (
    "b0486476564de67b3e9e40a4026ad1fa422121c17146e6ebc58331875aaa906e"
)
APPROVAL_DATE: Final = "2026-08-21"
APPROVAL_NOTE: Final = (
    "Approval binds the exact six-row qualification content after independent "
    "validation; runtime implementation remains forbidden in #402."
)
EXPECTED_AUTHORITIES: Final = {
    "frequency_report_2024": (
        "https://nadwyraz.com/userdata/public/assets/"
        "2024%20raport%20b%C5%82%C4%99d%C3%B3w/"
        "Kt%C3%B3re%20b%C5%82%C4%99dy%20j%C4%99zykowe%20"
        "pope%C5%82niamy%20najcz%C4%99%C5%9Bciej%20Raport%20o%20"
        "kondycji%20polszczyzny%20w%20internecie%20w%202024%20roku.pdf"
    ),
    "nck_co_niemiara": (
        "https://nck.pl/projekty-kulturalne/projekty/"
        "ojczysty-dodaj-do-ulubionych/ciekawostki-jezykowe/"
        "co-niemiara-%2Cc.ajax"
    ),
    "wsjp_zlodziej": "https://wsjp.pl/haslo/podglad/10848/zlodziej",
    "wsjp_co_nieco": "https://wsjp.pl/haslo/podglad/58987/co-nieco",
    "wsjp_in_vitro": "https://wsjp.pl/haslo/podglad/67446/in-vitro",
    "wsjp_naprzeciwko": "https://wsjp.pl/haslo/podglad/3712/naprzeciwko",
    "rjp_2026": (
        "https://rjp.pan.pl/app/uploads/2026/03/"
        "Zalacznik-do-komunikatu-11-25-wersja-ostateczna-jednolita.pdf"
    ),
}
POSITIVE_GUARDS: Final = frozenset(
    {"natural-language", "natural-language-dialogue", "mixed-prose-and-mention"}
)
REQUIRED_HARD_NEGATIVE_GUARDS: Final = frozenset(
    {
        "already-correct",
        "metalinguistic-mention",
        "identifier",
        "url",
        "email",
        "code",
        "command-flag",
        "substring",
        "hyphenated-token",
        "proper-name",
        "path",
        "mixed-script",
        "sentence-boundary",
        "interrupted-token",
        "repeated-mentions",
    }
)
REQUIRED_BOUNDARY_GUARDS: Final = (
    "metalinguistic quotation",
    "code/literal",
    "URL",
    "e-mail",
    "identifier",
    "substring",
    "mixed script",
    "cross-sentence span",
    "unsupported internal punctuation",
    "proper-name/product context",
)
REQUIRED_RISK_MECHANISMS: Final = (
    "literal mentions and technical wrappers",
    "token/subtoken boundary ambiguity",
    "proper-name or product use",
    "mixed script",
)
CONTROLLED_PAIR_CASE_CONTRACTS: Final = (
    ("01", "p01", "natural-language", "n01", "already-correct"),
    (
        "02",
        "p06",
        "natural-language-dialogue",
        "n02",
        "metalinguistic-mention",
    ),
    ("03", "p02", "natural-language", "n03", "identifier"),
    ("04", "p03", "natural-language", "n14", "sentence-boundary"),
)


@dataclass(frozen=True, slots=True)
class CandidateContract:
    id: str
    incorrect_surface: str
    minimal_target: str
    source_identity: str
    behavior_version: str
    operation: str
    normative_authority_id: str


CANDIDATE_CONTRACTS: Final = (
    CandidateContract(
        id="PI-TYPO-01",
        incorrect_surface="coniemiara",
        minimal_target="co niemiara",
        source_identity="rule:spelling.co_niemiara",
        behavior_version="spelling-co-niemiara/1.0",
        operation="replace.closed_literal_spacing",
        normative_authority_id="nck_co_niemiara",
    ),
    CandidateContract(
        id="PI-TYPO-02",
        incorrect_surface="złodzieji",
        minimal_target="złodziei",
        source_identity="rule:spelling.zlodzieji",
        behavior_version="spelling-zlodzieji/1.0",
        operation="replace.closed_literal",
        normative_authority_id="wsjp_zlodziej",
    ),
    CandidateContract(
        id="PI-TYPO-03",
        incorrect_surface="conieco",
        minimal_target="co nieco",
        source_identity="rule:spelling.co_nieco",
        behavior_version="spelling-co-nieco/1.0",
        operation="replace.closed_literal_spacing",
        normative_authority_id="wsjp_co_nieco",
    ),
    CandidateContract(
        id="PI-TYPO-04",
        incorrect_surface="invitro",
        minimal_target="in vitro",
        source_identity="rule:spelling.in_vitro",
        behavior_version="spelling-in-vitro/1.0",
        operation="replace.closed_literal_spacing",
        normative_authority_id="wsjp_in_vitro",
    ),
    CandidateContract(
        id="PI-TYPO-05",
        incorrect_surface="na przeciwko",
        minimal_target="naprzeciwko",
        source_identity="rule:spelling.naprzeciwko_spacing",
        behavior_version="spelling-naprzeciwko-spacing/1.0",
        operation="replace.closed_literal_spacing",
        normative_authority_id="wsjp_naprzeciwko",
    ),
    CandidateContract(
        id="PI-TYPO-06",
        incorrect_surface="niewiem",
        minimal_target="nie wiem",
        source_identity="rule:spelling.nie_wiem",
        behavior_version="spelling-nie-wiem/1.0",
        operation="replace.closed_literal_spacing",
        normative_authority_id="rjp_2026",
    ),
)
EXPECTED_CANDIDATE_IDS: Final = tuple(item.id for item in CANDIDATE_CONTRACTS)
EXPECTED_BY_ID: Final = {item.id: item for item in CANDIDATE_CONTRACTS}


@dataclass(frozen=True, slots=True)
class EvidenceSummary:
    case_count: int
    positive_expected_finding_count: int
    hard_negative_case_count: int
    candidates: dict[str, dict[str, JsonValue]]
    controlled_pair_ids: dict[str, tuple[str, ...]]
    authorities: dict[str, str]
    case_ids: tuple[str, ...]


def _reject_duplicate_keys(
    pairs: list[tuple[str, JsonValue]],
) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_json(path: Path) -> JsonValue:
    try:
        value: JsonValue = json.loads(
            path.read_text(), object_pairs_hook=_reject_duplicate_keys
        )
    except ContractError as error:
        raise ContractError(f"cannot read JSON {path}: {error}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"cannot read JSON {path}: {error}") from error
    return value


def _array(value: JsonValue, context: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise ContractError(f"{context} must be an array")
    return value


def _strings(value: JsonValue, context: str) -> tuple[str, ...]:
    return tuple(
        string(item, f"{context}[{index}]")
        for index, item in enumerate(_array(value, context))
    )


def _candidate_ids(document: dict[str, JsonValue], key: str) -> tuple[str, ...]:
    identifiers: list[str] = []
    for index, value in enumerate(_array(document.get(key), key)):
        row = mapping(value, f"{key}[{index}]")
        identifiers.append(string(row.get("id"), f"{key}[{index}].id"))
    return tuple(identifiers)


def _canonical_matrix_payload(
    matrix: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    payload = copy.deepcopy(matrix)
    payload.pop("stage", None)
    payload.pop("status", None)
    payload.pop("approval", None)
    integrity_value = payload.get("integrity")
    if isinstance(integrity_value, dict):
        integrity_value.pop("matrix_sha256", None)
        integrity_value.pop("digest_status", None)
    rows_value = payload.get("rows")
    if isinstance(rows_value, list):
        for raw_row in rows_value:
            if not isinstance(raw_row, dict):
                continue
            decision_value = raw_row.get("decision")
            if isinstance(decision_value, dict):
                decision_value.pop("maintainer_approval", None)
    return payload


def matrix_digest(matrix: dict[str, JsonValue]) -> str:
    """Return the non-circular canonical SHA-256 for the qualification matrix."""

    return hashlib.sha256(
        canonical_bytes(_canonical_matrix_payload(matrix))
    ).hexdigest()


def _validate_span(
    value: JsonValue,
    text: str,
    context: str,
    *,
    finding: bool,
) -> None:
    span = mapping(value, context)
    expected_fields = {"start", "end", "original"}
    if finding:
        expected_fields |= {"category", "suggestion"}
    exact_fields(span, frozenset(expected_fields), context)
    start = integer(span.get("start"), f"{context}.start")
    end = integer(span.get("end"), f"{context}.end")
    original = string(span.get("original"), f"{context}.original")
    if start < 0 or end <= start or end > len(text) or text[start:end] != original:
        raise ContractError(f"{context} does not match the exact original span")
    if not finding:
        return
    if span.get("category") != "spelling":
        raise ContractError(f"{context}.category must be spelling")
    string(span.get("suggestion"), f"{context}.suggestion")


def _casing_replacements(contract: CandidateContract) -> dict[str, str]:
    return {
        contract.incorrect_surface: contract.minimal_target,
        contract.incorrect_surface.capitalize(): contract.minimal_target.capitalize(),
        contract.incorrect_surface.upper(): contract.minimal_target.upper(),
    }


def _has_metalinguistic_prefix(text: str, start: int) -> bool:
    prefix = text[:start].casefold().rstrip().rstrip("„\"'`").rstrip()
    return any(
        prefix.endswith(marker)
        for marker in (
            "czy zapis",
            "napis",
            "słowo",
            "wyrażenie",
            "forma",
            "forma zapisu",
        )
    )


def _validate_case(
    raw_case: JsonValue,
    contract: CandidateContract,
    role: str,
    seen_case_ids: set[str],
) -> tuple[str, str | None, tuple[str, ...], int, tuple[str, ...]]:
    case = mapping(raw_case, f"{contract.id} {role} case")
    exact_fields(
        case,
        frozenset(
            {
                "id",
                "candidate_id",
                "kind",
                "role",
                "text",
                "expected_findings",
                "probes",
                "pair_id",
                "shape_strata",
                "guard",
                "rationale",
                "provider_behavior",
            }
        ),
        f"{contract.id} {role} case",
    )
    case_id = string(case.get("id"), "case.id")
    if case_id in seen_case_ids:
        raise ContractError(f"duplicate case ID: {case_id}")
    seen_case_ids.add(case_id)
    if case.get("candidate_id") != contract.id or case.get("role") != role:
        raise ContractError(f"{case_id} candidate or role mismatch")
    expected_kind = "error" if role == "positive" else "correct"
    if case.get("kind") != expected_kind:
        raise ContractError(f"{case_id}.kind must be {expected_kind}")
    text = string(case.get("text"), f"{case_id}.text")
    guard = string(case.get("guard"), f"{case_id}.guard")
    string(case.get("rationale"), f"{case_id}.rationale")
    if role == "positive" and guard not in POSITIVE_GUARDS:
        raise ContractError(f"{case_id} has invalid positive guard")

    findings = _array(case.get("expected_findings"), f"{case_id}.expected_findings")
    probes = _array(case.get("probes"), f"{case_id}.probes")
    if role == "positive":
        if not findings or probes:
            raise ContractError(f"{case_id} positive evidence contract mismatch")
    elif findings or not probes:
        raise ContractError(f"{case_id} hard-negative evidence contract mismatch")
    finding_originals: list[str] = []
    for index, value in enumerate(findings):
        _validate_span(
            value, text, f"{case_id}.expected_findings[{index}]", finding=True
        )
        finding = mapping(value, f"{case_id}.expected_findings[{index}]")
        original = string(
            finding.get("original"), f"{case_id}.expected_findings[{index}].original"
        )
        finding_originals.append(original)
        suggestion = string(
            finding.get("suggestion"),
            f"{case_id}.expected_findings[{index}].suggestion",
        )
        if _casing_replacements(contract).get(original) != suggestion:
            raise ContractError(
                f"{case_id}.expected_findings[{index}] has invalid "
                "casing-aware suggestion"
            )
        start = integer(
            finding.get("start"), f"{case_id}.expected_findings[{index}].start"
        )
        if _has_metalinguistic_prefix(text, start):
            raise ContractError(
                f"{case_id}.expected_findings[{index}] is metalinguistic evidence"
            )
    for index, value in enumerate(probes):
        _validate_span(value, text, f"{case_id}.probes[{index}]", finding=False)

    strata_values = _array(case.get("shape_strata"), f"{case_id}.shape_strata")
    strata = tuple(string(value, f"{case_id}.shape_strata") for value in strata_values)
    if len(strata) != len(set(strata)) or not set(strata) <= set(REQUIRED_SHAPE_STRATA):
        raise ContractError(f"{case_id} has invalid shape strata")

    pair_value = case.get("pair_id")
    if pair_value is not None and not isinstance(pair_value, str):
        raise ContractError(f"{case_id}.pair_id must be a string or null")
    pair_id = pair_value if isinstance(pair_value, str) else None

    behavior = mapping(case.get("provider_behavior"), f"{case_id}.provider_behavior")
    exact_fields(
        behavior,
        frozenset({"provider-absent", "qualified-morphology"}),
        f"{case_id}.provider_behavior",
    )
    expected_behavior = "execute" if role == "positive" else "abstain"
    if (
        behavior.get("provider-absent") != expected_behavior
        or behavior.get("qualified-morphology") != expected_behavior
    ):
        raise ContractError(
            f"{case_id} must behave identically without a provider and with morphology"
        )
    return case_id, pair_id, strata, len(findings), tuple(finding_originals)


def _validate_candidate_evidence(
    candidate: dict[str, JsonValue],
    contract: CandidateContract,
    seen_case_ids: set[str],
) -> tuple[tuple[str, ...], tuple[str, ...], int, tuple[str, ...]]:
    exact_fields(
        candidate,
        frozenset(
            {
                "id",
                "incorrect_surface",
                "minimal_target",
                "proposed_source_identity",
                "proposed_behavior_version",
                "operation",
                "normative_authority_id",
                "priority_rank",
                "positive_cases",
                "hard_negative_cases",
            }
        ),
        contract.id,
    )
    expected_values = {
        "id": contract.id,
        "incorrect_surface": contract.incorrect_surface,
        "minimal_target": contract.minimal_target,
        "proposed_source_identity": contract.source_identity,
        "proposed_behavior_version": contract.behavior_version,
        "operation": contract.operation,
        "normative_authority_id": contract.normative_authority_id,
    }
    for key, expected in expected_values.items():
        if candidate.get(key) != expected:
            raise ContractError(f"{contract.id}.{key} mismatch")
    string(candidate.get("normative_authority_id"), f"{contract.id}.authority")
    integer(candidate.get("priority_rank"), f"{contract.id}.priority_rank")

    positives = _array(candidate.get("positive_cases"), f"{contract.id}.positive_cases")
    negatives = _array(
        candidate.get("hard_negative_cases"), f"{contract.id}.hard_negative_cases"
    )
    if len(positives) < MINIMUM_POSITIVE_CASES:
        raise ContractError(
            f"{contract.id} must contain at least "
            f"{MINIMUM_POSITIVE_CASES} positive cases"
        )
    if len(negatives) != MINIMUM_HARD_NEGATIVES:
        raise ContractError(f"{contract.id} must contain exactly 16 hard negatives")

    positive_ids: list[str] = []
    negative_ids: list[str] = []
    positive_findings = 0
    pair_roles: dict[str, set[str]] = {}
    pair_cases: dict[str, dict[str, tuple[str, str]]] = {}
    positive_strata: set[str] = set()
    negative_strata: set[str] = set()
    positive_originals: set[str] = set()
    hard_negative_guards: set[str] = set()
    for role, values, identifiers, covered_strata in (
        ("positive", positives, positive_ids, positive_strata),
        ("hard-negative", negatives, negative_ids, negative_strata),
    ):
        for raw_case in values:
            case_id, pair_id, strata, finding_count, finding_originals = _validate_case(
                raw_case, contract, role, seen_case_ids
            )
            identifiers.append(case_id)
            positive_findings += finding_count
            covered_strata.update(strata)
            if role == "positive":
                positive_originals.update(finding_originals)
            else:
                case = mapping(raw_case, f"{contract.id} hard-negative case")
                hard_negative_guards.add(string(case.get("guard"), f"{case_id}.guard"))
            if pair_id is not None:
                pair_roles.setdefault(pair_id, set()).add(role)
                case = mapping(raw_case, f"{contract.id} controlled-pair case")
                guard = string(case.get("guard"), f"{case_id}.guard")
                pair_cases.setdefault(pair_id, {})[role] = (case_id, guard)

    if positive_findings < MINIMUM_POSITIVE_FINDINGS:
        raise ContractError(
            f"{contract.id} lacks {MINIMUM_POSITIVE_FINDINGS} positive findings"
        )
    required_casing_originals = set(_casing_replacements(contract))
    if not required_casing_originals <= positive_originals:
        raise ContractError(f"{contract.id} lacks required positive casing coverage")
    if positive_strata != set(REQUIRED_SHAPE_STRATA):
        missing = sorted(set(REQUIRED_SHAPE_STRATA) - positive_strata)
        raise ContractError(
            f"{contract.id} positive evidence misses shape stratum {missing[0]}"
        )
    if negative_strata != set(REQUIRED_SHAPE_STRATA):
        missing = sorted(set(REQUIRED_SHAPE_STRATA) - negative_strata)
        raise ContractError(
            f"{contract.id} hard negatives miss shape stratum {missing[0]}"
        )
    if not REQUIRED_HARD_NEGATIVE_GUARDS <= hard_negative_guards:
        raise ContractError(
            f"{contract.id} lacks required hard-negative guard coverage"
        )
    if len(pair_roles) != MINIMUM_CONTROLLED_PAIRS or any(
        roles != {"positive", "hard-negative"} for roles in pair_roles.values()
    ):
        raise ContractError(
            f"{contract.id} must contain {MINIMUM_CONTROLLED_PAIRS} controlled pairs"
        )
    case_prefix = contract.id.lower()
    expected_pair_cases = {
        f"{contract.id}-PAIR-{pair_number}": {
            "positive": (
                f"{case_prefix}-{positive_suffix}",
                positive_guard,
            ),
            "hard-negative": (
                f"{case_prefix}-{negative_suffix}",
                negative_guard,
            ),
        }
        for (
            pair_number,
            positive_suffix,
            positive_guard,
            negative_suffix,
            negative_guard,
        ) in CONTROLLED_PAIR_CASE_CONTRACTS
    }
    if pair_cases != expected_pair_cases:
        raise ContractError(f"{contract.id} controlled pair semantics mismatch")
    return (
        tuple(positive_ids),
        tuple(negative_ids),
        positive_findings,
        tuple(sorted(pair_roles)),
    )


def _validate_evidence(evidence: dict[str, JsonValue]) -> EvidenceSummary:
    exact_fields(
        evidence,
        frozenset(
            {
                "schema_id",
                "schema_version",
                "dataset_id",
                "dataset_version",
                "issue",
                "license",
                "source",
                "authorities",
                "profile_contract",
                "required_shape_strata",
                "case_count",
                "positive_case_count",
                "positive_expected_finding_count",
                "hard_negative_case_count",
                "candidates",
            }
        ),
        "evidence",
    )
    if (
        evidence.get("schema_id")
        != "polis.provider-independent-spelling-qualification-evidence"
        or evidence.get("schema_version") != 1
        or evidence.get("dataset_id") != DATASET_ID
        or evidence.get("dataset_version") != 1
        or evidence.get("issue") != 402
        or evidence.get("license") != "CC0-1.0"
    ):
        raise ContractError("unsupported evidence identity")
    source = mapping(evidence.get("source"), "evidence.source")
    exact_fields(
        source,
        frozenset(
            {
                "author",
                "created",
                "description",
                "provenance",
                "protected_data_overlap",
                "private_text_used",
            }
        ),
        "evidence.source fields",
    )
    if (
        source.get("author") != "Paweł Cyroń"
        or source.get("protected_data_overlap") is not False
        or source.get("private_text_used") is not False
    ):
        raise ContractError("evidence provenance is not public/project-authored")
    for field in ("created", "description", "provenance"):
        string(source.get(field), f"evidence.source.{field}")

    raw_authorities = mapping(evidence.get("authorities"), "evidence.authorities")
    exact_fields(
        raw_authorities,
        frozenset(EXPECTED_AUTHORITIES),
        "evidence.authorities fields",
    )
    authorities = {
        authority_id: string(
            raw_authorities.get(authority_id),
            f"evidence.authorities.{authority_id}",
        )
        for authority_id in EXPECTED_AUTHORITIES
    }
    if authorities != EXPECTED_AUTHORITIES:
        raise ContractError("evidence authority URL mismatch")

    profile = mapping(evidence.get("profile_contract"), "evidence.profile_contract")
    exact_fields(
        profile,
        frozenset({"supported_profile", "comparison_profile", "required_relation"}),
        "evidence.profile_contract fields",
    )
    if (
        profile.get("supported_profile") != "provider-absent"
        or profile.get("comparison_profile") != "qualified-morphology"
        or "identical"
        not in string(profile.get("required_relation"), "profile.required_relation")
    ):
        raise ContractError("provider-absent profile contract mismatch")
    declared_strata = tuple(
        string(value, "required shape stratum")
        for value in _array(
            evidence.get("required_shape_strata"), "required_shape_strata"
        )
    )
    if declared_strata != REQUIRED_SHAPE_STRATA:
        raise ContractError("required shape strata mismatch")
    if _candidate_ids(evidence, "candidates") != EXPECTED_CANDIDATE_IDS:
        raise ContractError("evidence candidate universe mismatch")

    candidates_values = _array(evidence.get("candidates"), "evidence.candidates")
    candidates: dict[str, dict[str, JsonValue]] = {}
    controlled_pair_ids: dict[str, tuple[str, ...]] = {}
    seen_case_ids: set[str] = set()
    case_ids: list[str] = []
    positive_case_count = 0
    positive_finding_count = 0
    hard_negative_count = 0
    for contract, raw_candidate in zip(
        CANDIDATE_CONTRACTS, candidates_values, strict=True
    ):
        candidate = mapping(raw_candidate, contract.id)
        (
            positive_ids,
            negative_ids,
            finding_count,
            candidate_pair_ids,
        ) = _validate_candidate_evidence(candidate, contract, seen_case_ids)
        authority_id = string(
            candidate.get("normative_authority_id"),
            f"{contract.id}.normative_authority_id",
        )
        if authority_id not in authorities:
            raise ContractError(f"{contract.id} uses an unknown normative authority")
        candidates[contract.id] = candidate
        controlled_pair_ids[contract.id] = candidate_pair_ids
        case_ids.extend(positive_ids)
        case_ids.extend(negative_ids)
        positive_case_count += len(positive_ids)
        positive_finding_count += finding_count
        hard_negative_count += len(negative_ids)

    case_count = positive_case_count + hard_negative_count
    declared_counts = {
        "case_count": case_count,
        "positive_case_count": positive_case_count,
        "positive_expected_finding_count": positive_finding_count,
        "hard_negative_case_count": hard_negative_count,
    }
    for key, expected in declared_counts.items():
        if integer(evidence.get(key), f"evidence.{key}") != expected:
            raise ContractError(f"evidence.{key} does not match cases")
    return EvidenceSummary(
        case_count=case_count,
        positive_expected_finding_count=positive_finding_count,
        hard_negative_case_count=hard_negative_count,
        candidates=candidates,
        controlled_pair_ids=controlled_pair_ids,
        authorities=authorities,
        case_ids=tuple(case_ids),
    )


def _validate_manifest(
    manifest: dict[str, JsonValue],
    evidence: dict[str, JsonValue],
    summary: EvidenceSummary,
) -> None:
    exact_fields(
        manifest,
        frozenset(
            {
                "schema_id",
                "schema_version",
                "dataset_id",
                "dataset_version",
                "evidence_path",
                "evidence_sha256",
                "license",
                "reviewed_by",
                "reviewed_at",
                "review_status",
                "reviewed_candidate_ids",
                "reviewed_case_ids",
                "case_id_sha256",
                "case_id_canonicalization",
                "protected_data_overlap",
            }
        ),
        "manifest",
    )
    if (
        manifest.get("schema_id")
        != "polis.provider-independent-spelling-qualification-manifest"
        or manifest.get("schema_version") != 1
        or manifest.get("dataset_id") != evidence.get("dataset_id")
        or manifest.get("dataset_version") != evidence.get("dataset_version")
        or manifest.get("evidence_path")
        != "tests/fixtures/v1/provider_independent_spelling_qualification.json"
        or manifest.get("license") != "CC0-1.0"
        or manifest.get("reviewed_by") != "Paweł Cyroń"
        or manifest.get("review_status") != "complete"
        or manifest.get("protected_data_overlap") is not False
    ):
        raise ContractError("manifest identity or review status mismatch")
    if manifest.get("reviewed_at") != APPROVAL_DATE:
        raise ContractError("manifest review metadata mismatch")
    if (
        manifest.get("case_id_canonicalization")
        != "UTF-8 ordered JSON array with compact separators and ensure_ascii=false"
    ):
        raise ContractError("manifest case-ID canonicalization mismatch")
    evidence_digest = hashlib.sha256(canonical_bytes(evidence)).hexdigest()
    if manifest.get("evidence_sha256") != evidence_digest:
        raise ContractError("manifest evidence SHA-256 mismatch")
    reviewed_candidates = tuple(
        string(value, "manifest reviewed candidate")
        for value in _array(
            manifest.get("reviewed_candidate_ids"), "manifest.reviewed_candidate_ids"
        )
    )
    if reviewed_candidates != EXPECTED_CANDIDATE_IDS:
        raise ContractError("manifest reviewed candidate universe mismatch")
    reviewed_cases = tuple(
        string(value, "manifest reviewed case")
        for value in _array(
            manifest.get("reviewed_case_ids"), "manifest.reviewed_case_ids"
        )
    )
    if reviewed_cases != summary.case_ids:
        raise ContractError("manifest reviewed case set mismatch")
    case_id_digest = hashlib.sha256(canonical_bytes(list(summary.case_ids))).hexdigest()
    if manifest.get("case_id_sha256") != case_id_digest:
        raise ContractError("manifest case ID SHA-256 mismatch")
    if evidence_digest != APPROVED_EVIDENCE_SHA256:
        raise ContractError("evidence does not match the approved evidence digest")
    if case_id_digest != APPROVED_CASE_ID_SHA256:
        raise ContractError("case IDs do not match the approved case-ID digest")


def _case_ids(
    candidate: dict[str, JsonValue], key: str, context: str
) -> tuple[str, ...]:
    return tuple(
        string(mapping(value, context).get("id"), f"{context}.id")
        for value in _array(candidate.get(key), context)
    )


def _shape_counts(candidate: dict[str, JsonValue], key: str) -> dict[str, int]:
    counts = {stratum: 0 for stratum in REQUIRED_SHAPE_STRATA}
    for raw_case in _array(candidate.get(key), key):
        case = mapping(raw_case, key)
        for raw_stratum in _array(case.get("shape_strata"), f"{key}.shape_strata"):
            stratum = string(raw_stratum, f"{key}.shape_strata")
            counts[stratum] += 1
    return counts


def _validate_row(
    row: dict[str, JsonValue],
    contract: CandidateContract,
    candidate: dict[str, JsonValue],
    controlled_pair_ids: tuple[str, ...],
    authorities: dict[str, str],
    digest: str,
) -> None:
    exact_fields(
        row,
        frozenset(
            {
                "id",
                "identity",
                "normative_basis",
                "deterministic_boundary",
                "output_contract",
                "public_evidence",
                "expected_value",
                "risk_and_cost",
                "decision",
            }
        ),
        f"matrix row {contract.id}",
    )
    if row.get("id") != contract.id:
        raise ContractError(f"matrix row {contract.id} ID mismatch")

    identity = mapping(
        row.get("identity"), f"{contract.id} matrix row contract identity"
    )
    exact_fields(
        identity,
        frozenset(
            {
                "incorrect_surface",
                "minimal_target",
                "proposed_source_identity",
                "proposed_behavior_version",
                "category",
                "operation",
                "provider_profile",
            }
        ),
        f"{contract.id} identity fields",
    )

    normative_basis = mapping(
        row.get("normative_basis"),
        f"{contract.id} matrix row contract normative basis",
    )
    exact_fields(
        normative_basis,
        frozenset(
            {
                "authority_id",
                "authority_url",
                "frequency_report_role",
                "rule_status",
            }
        ),
        f"{contract.id} normative basis fields",
    )
    authority_id = string(
        candidate.get("normative_authority_id"),
        f"{contract.id}.normative_authority_id",
    )
    if (
        normative_basis.get("authority_id") != authority_id
        or normative_basis.get("authority_url") != authorities[authority_id]
    ):
        raise ContractError(f"{contract.id} normative basis mismatch")
    expected_frequency_role = (
        "not-ranked; project-selected closed literal"
        if contract.id == "PI-TYPO-06"
        else "prioritization-only; not normative"
    )
    if (
        normative_basis.get("frequency_report_role") != expected_frequency_role
        or normative_basis.get("rule_status") != "required spelling form is explicit"
    ):
        raise ContractError(f"{contract.id} normative status mismatch")

    boundary = mapping(
        row.get("deterministic_boundary"),
        f"{contract.id} matrix row contract deterministic boundary",
    )
    exact_fields(
        boundary,
        frozenset(
            {
                "trigger",
                "guards",
                "casing",
                "unicode",
                "repetition",
                "multi_sentence",
                "conflict",
            }
        ),
        f"{contract.id} deterministic boundary fields",
    )
    trigger = string(boundary.get("trigger"), f"{contract.id}.trigger")
    if contract.incorrect_surface not in trigger:
        raise ContractError(f"{contract.id} trigger does not name the exact surface")
    if _strings(boundary.get("guards"), f"{contract.id}.guards") != (
        REQUIRED_BOUNDARY_GUARDS
    ):
        raise ContractError(f"{contract.id} deterministic guards mismatch")
    expected_boundary_values = {
        "casing": (
            "preserve lower, sentence/title initial, and coherent all-uppercase "
            "forms only; otherwise abstain"
        ),
        "unicode": (
            "match NFC text without folding mixed scripts; offsets remain original "
            "code-point indexes"
        ),
        "repetition": (
            "emit every non-overlapping qualified occurrence in document order"
        ),
        "multi_sentence": (
            "evaluate within sentence boundaries and map spans to original text"
        ),
        "conflict": (
            "use existing normalization/deduplication; overlapping or competing "
            "edits fail closed"
        ),
    }
    if any(
        boundary.get(field) != expected
        for field, expected in expected_boundary_values.items()
    ):
        raise ContractError(f"{contract.id} deterministic boundary contract mismatch")

    output = mapping(
        row.get("output_contract"),
        f"{contract.id} matrix row contract output contract",
    )
    exact_fields(
        output,
        frozenset(
            {
                "category",
                "operation",
                "span_rule",
                "suggestion_rule",
                "source_identity",
                "behavior_version",
                "severity",
                "policy",
                "automatic_policy_entry",
                "explicit_apply_required",
            }
        ),
        f"{contract.id} output contract fields",
    )
    if (
        output.get("span_rule")
        != "minimal exact incorrect surface only, half-open [start,end) against "
        "original text"
    ):
        raise ContractError(f"{contract.id} output span contract mismatch")

    evidence = mapping(
        row.get("public_evidence"),
        f"{contract.id} matrix row contract public evidence",
    )
    exact_fields(
        evidence,
        frozenset(
            {
                "dataset_id",
                "positive_case_ids",
                "positive_expected_finding_count",
                "hard_negative_case_ids",
                "controlled_pair_ids",
                "shape_strata",
                "provider_profiles",
                "evidence_gaps",
            }
        ),
        f"{contract.id} public evidence fields",
    )
    if evidence.get("dataset_id") != DATASET_ID:
        raise ContractError(f"{contract.id} public evidence dataset mismatch")

    expected_value = mapping(
        row.get("expected_value"),
        f"{contract.id} matrix row contract expected value",
    )
    exact_fields(
        expected_value,
        frozenset({"priority_rank", "measured_public_frequency_role", "runtime_claim"}),
        f"{contract.id} expected value fields",
    )
    if expected_value.get("priority_rank") != candidate.get("priority_rank"):
        raise ContractError(f"{contract.id} expected-value rank mismatch")
    expected_measured_role = (
        "not ranked" if contract.id == "PI-TYPO-06" else "candidate ordering only"
    )
    if (
        expected_value.get("measured_public_frequency_role") != expected_measured_role
        or expected_value.get("runtime_claim")
        != "one exact closed literal family; no generic spellchecking claim"
    ):
        raise ContractError(f"{contract.id} expected-value contract mismatch")

    risk = mapping(
        row.get("risk_and_cost"), f"{contract.id} matrix row contract risk and cost"
    )
    exact_fields(
        risk,
        frozenset(
            {
                "false_positive_mechanisms",
                "mitigation",
                "provider_drift_risk",
                "offset_risk",
                "performance_cost",
                "maintenance_risk",
            }
        ),
        f"{contract.id} risk and cost fields",
    )
    if (
        _strings(
            risk.get("false_positive_mechanisms"),
            f"{contract.id}.false_positive_mechanisms",
        )
        != REQUIRED_RISK_MECHANISMS
    ):
        raise ContractError(f"{contract.id} false-positive mechanisms mismatch")
    expected_risk_values = {
        "mitigation": "all listed guards abstain; prefer no finding",
        "provider_drift_risk": "none; provider-independent",
        "offset_risk": "minimal span is explicitly enumerated in public cases",
        "performance_cost": (
            "one bounded literal matcher in a later implementation issue; not "
            "measured or implemented here"
        ),
        "maintenance_risk": (
            "normative URL and exact target are recorded; norm changes require a "
            "new behavior version"
        ),
    }
    if any(
        risk.get(field) != expected for field, expected in expected_risk_values.items()
    ):
        raise ContractError(f"{contract.id} risk and cost contract mismatch")

    decision = mapping(
        row.get("decision"), f"{contract.id} matrix row contract decision"
    )
    exact_fields(
        decision,
        frozenset(
            {
                "disposition",
                "rationale",
                "child_allowed",
                "reopening_evidence",
                "maintainer_approval",
            }
        ),
        f"{contract.id} decision fields",
    )
    if (
        decision.get("rationale")
        != "Normative target and exact local trigger are explicit; project-authored "
        "evidence meets all per-candidate minima and fail-closed guards."
        or decision.get("reopening_evidence")
        != "A normative change, a demonstrated unguardable false positive, or a "
        "failing controlled case reopens qualification."
    ):
        raise ContractError(f"{contract.id} decision rationale mismatch")

    expected_identity: dict[str, JsonValue] = {
        "incorrect_surface": contract.incorrect_surface,
        "minimal_target": contract.minimal_target,
        "proposed_source_identity": contract.source_identity,
        "proposed_behavior_version": contract.behavior_version,
        "category": "spelling",
        "operation": contract.operation,
        "provider_profile": "provider-absent",
    }
    for key, expected in expected_identity.items():
        if identity.get(key) != expected:
            if key == "provider_profile":
                raise ContractError(f"{contract.id} must use provider-absent")
            raise ContractError(f"{contract.id}.identity.{key} mismatch")

    if (
        output.get("category") != "spelling"
        or output.get("operation") != contract.operation
        or output.get("suggestion_rule") != contract.minimal_target
        or output.get("source_identity") != contract.source_identity
        or output.get("behavior_version") != contract.behavior_version
        or output.get("severity") != "suggestion"
        or output.get("policy") != "review-only"
        or boolean(
            output.get("automatic_policy_entry"),
            f"{contract.id}.automatic_policy_entry",
        )
        or boolean(
            output.get("explicit_apply_required"),
            f"{contract.id}.explicit_apply_required",
        )
        is not True
    ):
        raise ContractError(f"{contract.id} output contract mismatch")

    positive_ids = _case_ids(candidate, "positive_cases", contract.id)
    negative_ids = _case_ids(candidate, "hard_negative_cases", contract.id)
    selected_positives = tuple(
        string(value, f"{contract.id}.positive_case_ids")
        for value in _array(
            evidence.get("positive_case_ids"), f"{contract.id}.positive_case_ids"
        )
    )
    selected_negatives = tuple(
        string(value, f"{contract.id}.hard_negative_case_ids")
        for value in _array(
            evidence.get("hard_negative_case_ids"),
            f"{contract.id}.hard_negative_case_ids",
        )
    )
    if selected_positives != positive_ids or selected_negatives != negative_ids:
        raise ContractError(f"{contract.id} matrix evidence IDs mismatch")
    actual_positive_finding_count = sum(
        len(
            _array(
                mapping(raw_case, contract.id).get("expected_findings"),
                f"{contract.id}.expected_findings",
            )
        )
        for raw_case in _array(candidate.get("positive_cases"), contract.id)
    )
    if (
        integer(
            evidence.get("positive_expected_finding_count"),
            f"{contract.id}.positive_expected_finding_count",
        )
        != actual_positive_finding_count
        or actual_positive_finding_count < MINIMUM_POSITIVE_FINDINGS
        or len(selected_negatives) != MINIMUM_HARD_NEGATIVES
    ):
        raise ContractError(f"{contract.id} matrix evidence minima mismatch")
    pairs = tuple(
        string(value, f"{contract.id}.controlled_pair_ids")
        for value in _array(
            evidence.get("controlled_pair_ids"), f"{contract.id}.controlled_pair_ids"
        )
    )
    if pairs != controlled_pair_ids:
        raise ContractError(f"{contract.id} matrix controlled pair IDs mismatch")

    declared_strata = mapping(
        evidence.get("shape_strata"), f"{contract.id}.shape_strata"
    )
    positive_counts = _shape_counts(candidate, "positive_cases")
    negative_counts = _shape_counts(candidate, "hard_negative_cases")
    if set(declared_strata) != set(REQUIRED_SHAPE_STRATA):
        raise ContractError(f"{contract.id} matrix shape strata mismatch")
    for stratum in REQUIRED_SHAPE_STRATA:
        counts = mapping(declared_strata.get(stratum), f"{contract.id}.{stratum}")
        exact_fields(
            counts,
            frozenset({"positive_cases", "hard_negative_cases"}),
            f"{contract.id}.{stratum} count fields",
        )
        if (
            integer(
                counts.get("positive_cases"),
                f"{contract.id}.{stratum}.positive_cases",
            )
            != positive_counts[stratum]
            or integer(
                counts.get("hard_negative_cases"),
                f"{contract.id}.{stratum}.hard_negative_cases",
            )
            != negative_counts[stratum]
        ):
            raise ContractError(f"{contract.id} {stratum} counts mismatch")
    if evidence.get("evidence_gaps") != []:
        raise ContractError(f"{contract.id} accepted row has evidence gaps")

    provider_profiles = mapping(
        evidence.get("provider_profiles"), f"{contract.id}.provider_profiles"
    )
    exact_fields(
        provider_profiles,
        frozenset({"provider-absent", "qualified-morphology"}),
        f"{contract.id} provider profile fields",
    )
    for profile_name, expected_status in (
        ("provider-absent", "qualified"),
        ("qualified-morphology", "same-as-provider-absent"),
    ):
        profile = mapping(
            provider_profiles.get(profile_name),
            f"{contract.id}.{profile_name}",
        )
        exact_fields(
            profile,
            frozenset({"positive_cases", "hard_negative_cases", "status"}),
            f"{contract.id}.{profile_name} fields",
        )
        if (
            profile.get("positive_cases") != len(positive_ids)
            or profile.get("hard_negative_cases") != len(negative_ids)
            or profile.get("status") != expected_status
        ):
            raise ContractError(f"{contract.id} {profile_name} summary mismatch")

    if (
        decision.get("disposition") != "accept: deterministic provider-absent"
        or decision.get("child_allowed") is not True
    ):
        raise ContractError(f"{contract.id} is not an approved provider-absent row")
    row_approval = mapping(
        decision.get("maintainer_approval"), f"{contract.id}.maintainer_approval"
    )
    exact_fields(
        row_approval,
        frozenset({"status", "approved_by", "approved_at", "bound_matrix_sha256"}),
        f"{contract.id} row approval fields",
    )
    if (
        row_approval.get("status") != "approved"
        or row_approval.get("approved_by") != "Paweł Cyroń"
        or row_approval.get("bound_matrix_sha256") != digest
    ):
        raise ContractError(f"{contract.id} row approval digest mismatch")
    if row_approval.get("approved_at") != APPROVAL_DATE:
        raise ContractError(f"{contract.id} row approval metadata mismatch")


def _validate_matrix(matrix: dict[str, JsonValue], summary: EvidenceSummary) -> int:
    exact_fields(
        matrix,
        frozenset(
            {
                "schema_id",
                "schema_version",
                "issue",
                "stage",
                "status",
                "candidate_universe",
                "corpus",
                "required_minima",
                "rows",
                "prioritization",
                "child_issue_policy",
                "runtime_change",
                "protected_data_accessed",
                "integrity",
                "approval",
            }
        ),
        "matrix fields",
    )
    if (
        matrix.get("schema_id") != "polis.provider-independent-spelling-qualification"
        or matrix.get("schema_version") != 1
        or matrix.get("issue") != 402
        or matrix.get("stage") != "approved"
        or matrix.get("status") != "approved"
        or matrix.get("runtime_change") != "none"
        or matrix.get("protected_data_accessed") is not False
    ):
        raise ContractError("matrix identity or runtime boundary mismatch")
    universe = mapping(matrix.get("candidate_universe"), "matrix.candidate_universe")
    exact_fields(
        universe,
        frozenset({"definition", "ids"}),
        "matrix.candidate_universe fields",
    )
    string(universe.get("definition"), "matrix.candidate_universe.definition")
    universe_ids = _strings(universe.get("ids"), "matrix.candidate_universe.ids")
    if universe_ids != EXPECTED_CANDIDATE_IDS:
        raise ContractError("matrix candidate universe mismatch")

    corpus = mapping(matrix.get("corpus"), "matrix.corpus")
    exact_fields(
        corpus,
        frozenset({"path", "manifest_path", "dataset_id"}),
        "matrix.corpus fields",
    )
    if corpus != {
        "path": "tests/fixtures/v1/provider_independent_spelling_qualification.json",
        "manifest_path": (
            "tests/fixtures/v1/"
            "provider_independent_spelling_qualification.manifest.json"
        ),
        "dataset_id": DATASET_ID,
    }:
        raise ContractError("matrix corpus contract mismatch")

    minima = mapping(matrix.get("required_minima"), "matrix.required_minima")
    exact_fields(
        minima,
        frozenset(
            {
                "positive_expected_findings",
                "hard_negative_cases",
                "controlled_pairs",
                "shape_strata",
                "provider_profile",
            }
        ),
        "matrix.required_minima fields",
    )
    if (
        minima.get("positive_expected_findings") != MINIMUM_POSITIVE_FINDINGS
        or minima.get("hard_negative_cases") != MINIMUM_HARD_NEGATIVES
        or minima.get("controlled_pairs") != MINIMUM_CONTROLLED_PAIRS
        or _strings(minima.get("shape_strata"), "matrix.required_minima.shape_strata")
        != REQUIRED_SHAPE_STRATA
        or minima.get("provider_profile") != "provider-absent"
    ):
        raise ContractError("matrix required minima mismatch")
    if _candidate_ids(matrix, "rows") != EXPECTED_CANDIDATE_IDS:
        raise ContractError("matrix row universe mismatch")

    integrity = mapping(matrix.get("integrity"), "matrix.integrity")
    exact_fields(
        integrity,
        frozenset({"algorithm", "canonicalization", "matrix_sha256", "digest_status"}),
        "matrix.integrity fields",
    )
    string(integrity.get("canonicalization"), "matrix.integrity.canonicalization")
    digest = matrix_digest(matrix)
    if (
        integrity.get("algorithm") != "SHA-256"
        or integrity.get("matrix_sha256") != digest
        or integrity.get("digest_status") != "approved"
    ):
        raise ContractError("matrix digest mismatch")
    approval = mapping(matrix.get("approval"), "matrix.approval")
    exact_fields(
        approval,
        frozenset(
            {
                "status",
                "decision_owner",
                "approved_by",
                "approved_at",
                "bound_matrix_sha256",
                "child_creation_allowed",
                "note",
            }
        ),
        "matrix.approval fields",
    )
    if (
        approval.get("status") != "approved"
        or approval.get("decision_owner") != "Paweł Cyroń"
        or approval.get("approved_by") != "Paweł Cyroń"
        or approval.get("bound_matrix_sha256") != digest
        or approval.get("child_creation_allowed") is not True
    ):
        raise ContractError("matrix approval digest mismatch")
    if (
        approval.get("approved_at") != APPROVAL_DATE
        or approval.get("note") != APPROVAL_NOTE
    ):
        raise ContractError("matrix approval metadata mismatch")

    rows = _array(matrix.get("rows"), "matrix.rows")
    for contract, raw_row in zip(CANDIDATE_CONTRACTS, rows, strict=True):
        _validate_row(
            mapping(raw_row, f"matrix row {contract.id}"),
            contract,
            summary.candidates[contract.id],
            summary.controlled_pair_ids[contract.id],
            summary.authorities,
            digest,
        )

    prioritization = mapping(matrix.get("prioritization"), "matrix.prioritization")
    exact_fields(
        prioritization,
        frozenset({"method", "accepted_row_ids", "ranked_rows"}),
        "matrix.prioritization fields",
    )
    string(prioritization.get("method"), "matrix.prioritization.method")
    accepted_ids = tuple(
        string(value, "accepted row ID")
        for value in _array(
            prioritization.get("accepted_row_ids"), "prioritization.accepted_row_ids"
        )
    )
    if accepted_ids != EXPECTED_CANDIDATE_IDS:
        raise ContractError("accepted-row prioritization mismatch")
    ranked_rows = _array(
        prioritization.get("ranked_rows"), "prioritization.ranked_rows"
    )
    expected_ranks = list(enumerate(EXPECTED_CANDIDATE_IDS, start=1))
    actual_ranks: list[tuple[int, str]] = []
    for value in ranked_rows:
        ranked_row = mapping(value, "ranked row")
        exact_fields(
            ranked_row,
            frozenset({"candidate_id", "rank"}),
            "ranked row fields",
        )
        actual_ranks.append(
            (
                integer(ranked_row.get("rank"), "ranked row rank"),
                string(ranked_row.get("candidate_id"), "ranked row candidate_id"),
            )
        )
    if actual_ranks != expected_ranks:
        raise ContractError("ranked-row order is not reproducible")

    child_policy = mapping(
        matrix.get("child_issue_policy"), "matrix.child_issue_policy"
    )
    exact_fields(
        child_policy,
        frozenset(
            {
                "creation_rule",
                "serial_delivery",
                "one_branch_one_commit_one_pr",
                "review_only_first",
                "automatic_policy_changes",
                "required_body_markers",
                "out_of_scope",
            }
        ),
        "matrix.child_issue_policy fields",
    )
    if (
        child_policy.get("serial_delivery") is not True
        or child_policy.get("one_branch_one_commit_one_pr") is not True
        or child_policy.get("review_only_first") is not True
        or child_policy.get("automatic_policy_changes") is not False
    ):
        raise ContractError("child issue policy mismatch")
    string(child_policy.get("creation_rule"), "child policy creation_rule")
    string(child_policy.get("out_of_scope"), "child policy out_of_scope")
    if _strings(
        child_policy.get("required_body_markers"),
        "child policy required_body_markers",
    ) != ("Parent #402", "Qualification row ID:", "Qualification matrix SHA-256:"):
        raise ContractError("child issue body markers mismatch")
    if digest != APPROVED_MATRIX_SHA256:
        raise ContractError("matrix does not match the approved matrix digest")
    return len(rows)


def validate_documents(
    evidence: dict[str, JsonValue],
    manifest: dict[str, JsonValue],
    matrix: dict[str, JsonValue],
) -> dict[str, int]:
    """Validate all public #402 artifacts and return their measured summary."""

    summary = _validate_evidence(evidence)
    _validate_manifest(manifest, evidence, summary)
    accepted_count = _validate_matrix(matrix, summary)
    return {
        "accepted_count": accepted_count,
        "candidate_count": len(summary.candidates),
        "case_count": summary.case_count,
        "hard_negative_case_count": summary.hard_negative_case_count,
        "positive_expected_finding_count": summary.positive_expected_finding_count,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the provider-independent spelling qualification."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--evidence", type=Path, required=True)
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--matrix", type=Path, required=True)
    return parser


def main(arguments: list[str] | None = None) -> int:
    """Run the repository-only qualification validator."""

    namespace = _parser().parse_args(arguments)
    if namespace.command != "validate":
        raise ContractError(f"unsupported command: {namespace.command}")
    try:
        summary = validate_documents(
            mapping(_read_json(namespace.evidence), "evidence"),
            mapping(_read_json(namespace.manifest), "manifest"),
            mapping(_read_json(namespace.matrix), "matrix"),
        )
    except ContractError as error:
        print(str(error))
        return 2
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
