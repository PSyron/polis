from __future__ import annotations

import hashlib
import json

import pytest

from polis.evaluation import quality_dataset

type JsonValue = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)

PLANNED_SOURCES = (
    "rule:agreement.nominal_group_ta_nowy_ksiazka",
    "rule:agreement.subject_verb_my_czyta",
    "rule:inflection.przygladac_sie_nowy_budynek",
    "rule:inflection.government_szukac_klucz",
    "rule:spelling.wogole",
    "rule:spelling.narazie",
    "rule:spelling.wziasc",
    "rule:syntax.initial_temporal_comma",
)
EVIDENCE_CLASSES = {
    "error",
    "corrected_pair",
    "quotation_mention",
    "code_like_mention",
    "substring_lexeme_negative",
    "multi_sentence_negative",
    "repeated_occurrence",
    "unicode_casing_offset",
}


def test_v2_carries_forward_exact_v1_cases_and_adds_reviewed_source_matrix() -> None:
    # Given
    v1_cases_path, _ = quality_dataset.quality_dataset_paths(
        quality_dataset.QualityDatasetVersion.V1
    )
    v2_cases_path, v2_manifest_path = quality_dataset.quality_dataset_paths(
        quality_dataset.QualityDatasetVersion.V2
    )
    v1_raw = json.loads(v1_cases_path.read_text(encoding="utf-8"))
    v2_raw = json.loads(v2_cases_path.read_text(encoding="utf-8"))
    manifest = json.loads(v2_manifest_path.read_text(encoding="utf-8"))

    # When
    dataset = quality_dataset.load_quality_dataset(
        version=quality_dataset.QualityDatasetVersion.V2
    )

    # Then
    assert dataset.schema_version == 2
    assert dataset.id == "polis_v2_quality_development"
    assert dataset.dataset_version == 2
    assert len(dataset.cases) == 92
    assert v2_raw["cases"][:28] == v1_raw["cases"]
    assert manifest["provenance"] == {
        "carried_forward_case_ids": [case["id"] for case in v1_raw["cases"]],
        "dataset_id": "polis_v1_quality_development",
        "dataset_version": 1,
        "canonical_sha256": (
            "152f7e23e5e56f299fc35e5acbb515515a855ee5925664e6b0a5179380984a2e"
        ),
        "license": "CC0-1.0",
        "source": "project-authored",
    }
    planned = manifest["source_cohort"]["planned_sources"]
    assert tuple(item["source"] for item in planned) == PLANNED_SOURCES
    assert all(set(item["evidence_case_ids"]) == EVIDENCE_CLASSES for item in planned)
    assert all(len(set(item["evidence_case_ids"].values())) == 8 for item in planned)
    new_ids = {case.id for case in dataset.cases[28:]}
    bound_new_ids = {
        case_id for item in planned for case_id in item["evidence_case_ids"].values()
    }
    assert new_ids == bound_new_ids
    assert dataset.review.status == "maintainer-reviewed"
    assert dataset.review.reviewed_case_ids == tuple(case.id for case in dataset.cases)


def test_v2_error_cases_preserve_half_open_offsets_and_exact_corrections() -> None:
    # Given
    dataset = quality_dataset.load_quality_dataset(
        version=quality_dataset.QualityDatasetVersion.V2
    )
    corrected_pairs = {
        case.pair_id: case.text
        for case in dataset.cases
        if case.kind == "correct" and case.pair_id is not None
    }

    # When
    error_cases = tuple(case for case in dataset.cases if case.kind == "error")

    # Then
    assert error_cases
    for case in error_cases:
        assert case.findings
        for finding in case.findings:
            assert case.text[finding.start : finding.end] == finding.original
            corrected = (
                case.text[: finding.start]
                + finding.suggestion
                + case.text[finding.end :]
            )
            assert corrected != case.text
            if case.pair_id is not None:
                assert corrected == corrected_pairs[case.pair_id]


def test_v2_validator_rejects_drift_in_carried_forward_case_content() -> None:
    # Given
    cases_path, manifest_path = quality_dataset.quality_dataset_paths(
        quality_dataset.QualityDatasetVersion.V2
    )
    raw = json.loads(cases_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw["cases"][0]["expected_findings"][0]["rationale"] = (
        "Zmienione uzasadnienie zachowujące poprawny schemat."
    )
    _rebind(raw, manifest)

    # When / Then
    with pytest.raises(ValueError, match="carried-forward v1 case content drift"):
        quality_dataset.validate_quality_dataset(raw, manifest)


def test_v2_validator_rejects_evidence_class_semantic_drift() -> None:
    # Given
    cases_path, manifest_path = quality_dataset.quality_dataset_paths(
        quality_dataset.QualityDatasetVersion.V2
    )
    raw = json.loads(cases_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence = manifest["source_cohort"]["planned_sources"][0]["evidence_case_ids"]
    evidence["error"], evidence["quotation_mention"] = (
        evidence["quotation_mention"],
        evidence["error"],
    )

    # When / Then
    with pytest.raises(ValueError, match="planned source evidence class mismatch"):
        quality_dataset.validate_quality_dataset(raw, manifest)


def _rebind(raw: JsonValue, manifest: dict[str, JsonValue]) -> None:
    encoded = json.dumps(
        raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    manifest["canonical_sha256"] = digest
    review = manifest["review"]
    assert isinstance(review, dict)
    review.update({"canonical_sha256": digest})
