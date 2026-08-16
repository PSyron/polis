"""Validation rules for quality-development-v3 (Umbrella F planned sources)."""

from __future__ import annotations

from polis.evaluation._quality_parsing import (
    canonical_hash,
    require_exact_fields,
    require_literal,
    require_object,
)
from polis.evaluation._quality_types import (
    JsonValue,
    QualityCase,
    QualityCaseKind,
    QualityDatasetError,
    QualityFeature,
)
from polis.evaluation._quality_v3_identities import SOURCE_IDENTITIES

V3_MANIFEST_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "dataset_id",
        "dataset_version",
        "canonical_sha256",
        "provenance",
        "source_cohort",
        "review",
    }
)
_V2_CANONICAL_SHA256 = (
    "f65055ff500146bdd727b78d2838c19ed15e38705ecdf27f4a3d35349552f217"
)
_V2_CASE_COUNT = 92
_EVIDENCE_CLASSES = frozenset(
    {
        "error",
        "corrected_pair",
        "quotation_mention",
        "code_like_mention",
        "substring_lexeme_negative",
        "multi_sentence_negative",
        "repeated_occurrence",
        "unicode_casing_offset",
    }
)
_EXPECTED_NEW_CASES = len(SOURCE_IDENTITIES) * 8
_EXPECTED_TOTAL_CASES = _V2_CASE_COUNT + _EXPECTED_NEW_CASES


def validate_v3_manifest(
    manifest: dict[str, JsonValue],
    cases: tuple[QualityCase, ...],
    raw_cases: list[JsonValue],
) -> None:
    _validate_provenance(manifest, cases, raw_cases)
    cohort = require_object(manifest["source_cohort"], "quality source cohort")
    require_exact_fields(
        cohort,
        frozenset(
            {
                "adr",
                "runtime_source_cohort_id",
                "qualification_cohort_id",
                "additions_policy_state",
                "planned_sources",
            }
        ),
        "quality source cohort",
    )
    require_literal(cohort, "adr", "ADR-0026", "quality source cohort")
    require_literal(
        cohort,
        "runtime_source_cohort_id",
        "polis-runtime-source-cohort-59-v1",
        "quality source cohort",
    )
    require_literal(
        cohort,
        "qualification_cohort_id",
        "polis-a-b-qualification-v2-source-cohort-v1",
        "quality source cohort",
    )
    require_literal(
        cohort, "additions_policy_state", "review-only", "quality source cohort"
    )
    planned = cohort["planned_sources"]
    if not isinstance(planned, list) or len(planned) != len(SOURCE_IDENTITIES):
        raise QualityDatasetError(
            f"quality source cohort must bind {len(SOURCE_IDENTITIES)} sources"
        )
    case_by_id = {case.id: case for case in cases}
    bound_ids: list[str] = []
    for raw, identity in zip(planned, SOURCE_IDENTITIES, strict=True):
        bound_ids.extend(_validate_planned_source(raw, identity, case_by_id))
    new_ids = [case.id for case in cases[_V2_CASE_COUNT:]]
    if (
        len(cases) != _EXPECTED_TOTAL_CASES
        or len(bound_ids) != _EXPECTED_NEW_CASES
        or set(bound_ids) != set(new_ids)
    ):
        raise QualityDatasetError(
            f"quality source evidence must bind all {_EXPECTED_NEW_CASES} new cases"
        )


def _validate_provenance(
    manifest: dict[str, JsonValue],
    cases: tuple[QualityCase, ...],
    raw_cases: list[JsonValue],
) -> None:
    provenance = require_object(manifest["provenance"], "quality provenance")
    require_exact_fields(
        provenance,
        frozenset(
            {
                "dataset_id",
                "dataset_version",
                "canonical_sha256",
                "license",
                "source",
                "carried_forward_case_ids",
            }
        ),
        "quality provenance",
    )
    expected = {
        "dataset_id": "polis_v2_quality_development",
        "dataset_version": 2,
        "canonical_sha256": _V2_CANONICAL_SHA256,
        "license": "CC0-1.0",
        "source": "project-authored",
    }
    for field, value in expected.items():
        require_literal(provenance, field, value, "quality provenance")
    carried_ids = provenance["carried_forward_case_ids"]
    if not isinstance(carried_ids, list) or carried_ids != [
        case.id for case in cases[:_V2_CASE_COUNT]
    ]:
        raise QualityDatasetError(
            f"quality provenance must bind the first {_V2_CASE_COUNT} cases"
        )
    reconstructed_v2: JsonValue = {
        "schema_id": "polis.quality-development-dataset",
        "schema_version": 2,
        "id": "polis_v2_quality_development",
        "dataset_version": 2,
        "license": "CC0-1.0",
        "source": "project-authored",
        "cases": raw_cases[:_V2_CASE_COUNT],
    }
    if canonical_hash(reconstructed_v2) != _V2_CANONICAL_SHA256:
        raise QualityDatasetError("carried-forward v2 case content drift")


def _validate_planned_source(
    raw: JsonValue,
    identity: tuple[str, str, str, str, float],
    case_by_id: dict[str, QualityCase],
) -> tuple[str, ...]:
    item = require_object(raw, "planned source")
    require_exact_fields(
        item,
        frozenset(
            {
                "source",
                "category",
                "operation",
                "behavior_version",
                "confidence",
                "evidence_case_ids",
            }
        ),
        "planned source",
    )
    for field, expected in zip(
        ("source", "category", "operation", "behavior_version", "confidence"),
        identity,
        strict=True,
    ):
        require_literal(item, field, expected, "planned source")
    evidence = require_object(item["evidence_case_ids"], "source evidence")
    if set(evidence) != _EVIDENCE_CLASSES or not all(
        isinstance(case_id, str) for case_id in evidence.values()
    ):
        raise QualityDatasetError("planned source must bind eight evidence classes")
    ids = tuple(str(case_id) for case_id in evidence.values())
    if len(set(ids)) != 8 or any(case_id not in case_by_id for case_id in ids):
        raise QualityDatasetError("planned source evidence class mismatch")
    selected = {name: case_by_id[str(evidence[name])] for name in _EVIDENCE_CLASSES}
    error = selected["error"]
    corrected = selected["corrected_pair"]
    negatives = tuple(
        selected[name]
        for name in (
            "quotation_mention",
            "code_like_mention",
            "substring_lexeme_negative",
            "multi_sentence_negative",
        )
    )
    repeated = selected["repeated_occurrence"]
    unicode_case = selected["unicode_casing_offset"]
    category = identity[1]
    valid = (
        error.kind is QualityCaseKind.ERROR
        and error.pair_id is not None
        and corrected.kind is QualityCaseKind.CORRECT
        and corrected.pair_id == error.pair_id
        and all(
            case.kind is QualityCaseKind.CORRECT
            and case.pair_id is None
            and not case.findings
            for case in negatives
        )
        and QualityFeature.MULTI_SENTENCE
        in selected["multi_sentence_negative"].features
        and repeated.kind is QualityCaseKind.ERROR
        and len(repeated.findings) == 2
        and unicode_case.kind is QualityCaseKind.ERROR
        and QualityFeature.UNICODE in unicode_case.features
        and all(
            finding.category == category
            for case in (error, repeated, unicode_case)
            for finding in case.findings
        )
    )
    if not valid:
        raise QualityDatasetError("planned source evidence class mismatch")
    return ids
