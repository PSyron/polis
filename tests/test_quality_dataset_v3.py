from __future__ import annotations

import hashlib
import json

import pytest

from polis.evaluation import quality_dataset
from polis.evaluation._quality_v3_identities import SOURCE_IDENTITIES

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
PLANNED_SOURCES = tuple(source for source, *_rest in SOURCE_IDENTITIES)
V2_CANONICAL = "f65055ff500146bdd727b78d2838c19ed15e38705ecdf27f4a3d35349552f217"


def test_v3_carries_forward_exact_v2_cases_and_adds_reviewed_source_matrix() -> None:
    v2_cases_path, _ = quality_dataset.quality_dataset_paths(
        quality_dataset.QualityDatasetVersion.V2
    )
    v3_cases_path, v3_manifest_path = quality_dataset.quality_dataset_paths(
        quality_dataset.QualityDatasetVersion.V3
    )
    v2_raw = json.loads(v2_cases_path.read_text(encoding="utf-8"))
    v3_raw = json.loads(v3_cases_path.read_text(encoding="utf-8"))
    manifest = json.loads(v3_manifest_path.read_text(encoding="utf-8"))

    dataset = quality_dataset.load_quality_dataset(
        version=quality_dataset.QualityDatasetVersion.V3
    )

    assert dataset.schema_version == 3
    assert dataset.id == "polis_v3_quality_development"
    assert dataset.dataset_version == 3
    assert len(dataset.cases) == 340
    assert v3_raw["cases"][:92] == v2_raw["cases"]
    assert manifest["provenance"] == {
        "carried_forward_case_ids": [case["id"] for case in v2_raw["cases"]],
        "dataset_id": "polis_v2_quality_development",
        "dataset_version": 2,
        "canonical_sha256": V2_CANONICAL,
        "license": "CC0-1.0",
        "source": "project-authored",
    }
    planned = manifest["source_cohort"]["planned_sources"]
    assert tuple(item["source"] for item in planned) == PLANNED_SOURCES
    assert len(planned) == 31
    assert all(set(item["evidence_case_ids"]) == EVIDENCE_CLASSES for item in planned)
    assert all(len(set(item["evidence_case_ids"].values())) == 8 for item in planned)
    new_ids = {case.id for case in dataset.cases[92:]}
    bound_new_ids = {
        case_id for item in planned for case_id in item["evidence_case_ids"].values()
    }
    assert new_ids == bound_new_ids
    assert dataset.review.status == "maintainer-reviewed"
    assert dataset.review.reviewed_case_ids == tuple(case.id for case in dataset.cases)
    assert manifest["source_cohort"]["adr"] == "ADR-0026"
    assert (
        manifest["source_cohort"]["runtime_source_cohort_id"]
        == "polis-runtime-source-cohort-59-v1"
    )


def test_v3_error_cases_preserve_half_open_offsets() -> None:
    dataset = quality_dataset.load_quality_dataset(
        version=quality_dataset.QualityDatasetVersion.V3
    )
    error_cases = tuple(case for case in dataset.cases[92:] if case.kind == "error")
    assert error_cases
    for case in error_cases:
        assert case.findings
        for finding in case.findings:
            assert case.text[finding.start : finding.end] == finding.original


def test_v3_validator_rejects_drift_in_carried_forward_case_content() -> None:
    cases_path, manifest_path = quality_dataset.quality_dataset_paths(
        quality_dataset.QualityDatasetVersion.V3
    )
    raw = json.loads(cases_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw["cases"][0]["expected_findings"][0]["rationale"] = (
        "Zmienione uzasadnienie zachowujące poprawny schemat."
    )
    _rebind(raw, manifest)
    with pytest.raises(ValueError, match="carried-forward v2 case content drift"):
        quality_dataset.validate_quality_dataset(raw, manifest)


def test_v2_dataset_remains_byte_identical() -> None:
    cases_path, manifest_path = quality_dataset.quality_dataset_paths(
        quality_dataset.QualityDatasetVersion.V2
    )
    dataset = quality_dataset.load_quality_dataset(
        version=quality_dataset.QualityDatasetVersion.V2
    )
    assert dataset.canonical_sha256 == V2_CANONICAL
    assert hashlib.sha256(cases_path.read_bytes()).hexdigest()
    assert manifest_path.exists()


def _rebind(raw: object, manifest: dict[str, object]) -> None:
    encoded = json.dumps(
        raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    manifest["canonical_sha256"] = digest
    review = manifest["review"]
    assert isinstance(review, dict)
    review.update({"canonical_sha256": digest})
