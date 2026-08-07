from __future__ import annotations

import hashlib
import json
from types import ModuleType
from typing import Any

import pytest

from polis.evaluation import _quality_rules, _quality_types, quality_dataset
from polis.evaluation.quality_dataset import (
    QUALITY_DATASET_PATH,
    QUALITY_MANIFEST_PATH,
    QualityCaseKind,
    QualityFeature,
    QualityPhenomenon,
    as_evaluation_dataset,
    load_quality_dataset,
    validate_quality_dataset,
)


@pytest.mark.parametrize(
    ("name", "owner"),
    [
        ("QUALITY_DATASET_PATH", _quality_types),
        ("QUALITY_MANIFEST_PATH", _quality_types),
        ("JsonValue", _quality_types),
        ("QualityCase", _quality_types),
        ("QualityCaseKind", _quality_types),
        ("QualityDataset", _quality_types),
        ("QualityDatasetError", _quality_types),
        ("QualityExpectedFinding", _quality_types),
        ("QualityFeature", _quality_types),
        ("QualityPhenomenon", _quality_types),
        ("QualityReview", _quality_types),
        ("load_quality_dataset", _quality_rules),
        ("validate_quality_dataset", _quality_rules),
    ],
)
def test_quality_dataset_facade_preserves_import_identity(
    name: str, owner: ModuleType
) -> None:
    assert getattr(quality_dataset, name) is getattr(owner, name)


def _raw_documents() -> tuple[dict[str, Any], dict[str, Any]]:
    dataset = json.loads(QUALITY_DATASET_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(QUALITY_MANIFEST_PATH.read_text(encoding="utf-8"))
    return dataset, manifest


def _case(raw: dict[str, Any], kind: str) -> dict[str, Any]:
    return next(case for case in raw["cases"] if case["kind"] == kind)


def _rebind_manifest(raw: dict[str, Any], manifest: dict[str, Any]) -> None:
    encoded = json.dumps(
        raw, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    manifest["canonical_sha256"] = digest
    manifest["review"]["canonical_sha256"] = digest


def test_committed_quality_dataset_covers_the_v1_protocol() -> None:
    dataset = load_quality_dataset()

    assert dataset.schema_id == "polis.quality-development-dataset"
    assert dataset.schema_version == 1
    assert dataset.id == "polis_v1_quality_development"
    assert dataset.dataset_version == 1
    assert dataset.license == "CC0-1.0"
    assert dataset.source == "project-authored"
    assert len(dataset.cases) >= 16
    assert len(dataset.canonical_sha256) == 64
    assert dataset.review.canonical_sha256 == dataset.canonical_sha256
    assert dataset.manifest_canonical_sha256 == dataset.canonical_sha256
    assert dataset.review.status == "maintainer-reviewed"
    assert dataset.review.reviewer_role == "Polis maintainer"
    assert dataset.review.reviewed_case_ids == (
        "quality_inflection_error",
        "quality_inflection_correct",
        "quality_rection_error",
        "quality_rection_correct",
        "quality_agreement_error",
        "quality_agreement_correct",
        "quality_spelling_error",
        "quality_spelling_correct",
        "quality_syntax_error",
        "quality_syntax_correct",
        "quality_punctuation_error",
        "quality_punctuation_correct",
        "quality_overlapping_conflict",
        "quality_abstain_temporal",
        "quality_abstain_style",
        "quality_abstain_intent",
        "quality_inflection_negated_government_error",
        "quality_inflection_negated_government_correct",
        "quality_syntax_destination_preposition_error",
        "quality_syntax_destination_preposition_correct",
        "quality_syntax_initial_conditional_comma_error",
        "quality_syntax_initial_conditional_comma_correct",
    )

    paired_cases = tuple(case for case in dataset.cases if case.pair_id is not None)
    pairs = {
        pair_id: [case for case in paired_cases if case.pair_id == pair_id]
        for pair_id in {case.pair_id for case in paired_cases}
    }
    assert all(
        len(cases) == 2
        and {case.kind for case in cases}
        == {QualityCaseKind.ERROR, QualityCaseKind.CORRECT}
        and len({case.phenomenon for case in cases}) == 1
        for cases in pairs.values()
    )
    assert {case.phenomenon for case in paired_cases} == set(QualityPhenomenon)

    features = {feature for case in dataset.cases for feature in case.features}
    assert set(QualityFeature) <= features
    assert sum(case.kind is QualityCaseKind.CONFLICT for case in dataset.cases) == 1
    assert sum(case.kind is QualityCaseKind.ABSTAIN for case in dataset.cases) == 3
    for case in dataset.cases:
        for finding in case.findings:
            assert case.text[finding.start : finding.end] == finding.original


def test_manifest_rejects_dataset_hash_drift() -> None:
    raw, manifest = _raw_documents()
    raw["cases"][0]["text"] += "x"

    with pytest.raises(ValueError, match="^quality dataset canonical_sha256 mismatch$"):
        validate_quality_dataset(raw, manifest)


@pytest.mark.parametrize(
    ("document", "mutation", "message"),
    [
        (
            "dataset",
            lambda raw: raw.update({"unexpected": True}),
            "quality dataset must contain exactly the required fields",
        ),
        (
            "dataset",
            lambda raw: raw.pop("schema_id"),
            "quality dataset must contain exactly the required fields",
        ),
        (
            "manifest",
            lambda raw: raw.update({"unexpected": True}),
            "quality manifest must contain exactly the required fields",
        ),
        (
            "manifest",
            lambda raw: raw.pop("review"),
            "quality manifest must contain exactly the required fields",
        ),
    ],
)
def test_schema_rejects_unknown_and_missing_fields(
    document: str,
    mutation: Any,
    message: str,
) -> None:
    raw, manifest = _raw_documents()
    target = raw if document == "dataset" else manifest
    mutation(target)

    with pytest.raises(ValueError, match=message):
        validate_quality_dataset(raw, manifest)


def test_schema_rejects_boolean_version_as_an_integer() -> None:
    raw, manifest = _raw_documents()
    raw["schema_version"] = True
    _rebind_manifest(raw, manifest)

    with pytest.raises(ValueError, match="quality dataset schema_version must be 1"):
        validate_quality_dataset(raw, manifest)


def test_manifest_review_must_cover_every_case_exactly() -> None:
    raw, manifest = _raw_documents()
    manifest["review"]["status"] = "maintainer-reviewed"
    manifest["review"]["reviewed_case_ids"] = [case["id"] for case in raw["cases"]]
    manifest["review"]["reviewed_case_ids"].pop()

    with pytest.raises(ValueError, match="reviewed_case_ids must equal all case ids"):
        validate_quality_dataset(raw, manifest)


def test_pending_review_rejects_claimed_reviewed_case_ids() -> None:
    raw, manifest = _raw_documents()
    manifest["review"]["status"] = "pending_maintainer_review"
    manifest["review"]["reviewed_case_ids"] = [raw["cases"][0]["id"]]

    with pytest.raises(
        ValueError, match="pending review must not contain reviewed_case_ids"
    ):
        validate_quality_dataset(raw, manifest)


def test_review_rejects_unsupported_status() -> None:
    raw, manifest = _raw_documents()
    manifest["review"]["status"] = "automatically-approved"

    with pytest.raises(ValueError, match="quality review status is unsupported"):
        validate_quality_dataset(raw, manifest)


def test_future_maintainer_review_requires_and_accepts_every_case_id() -> None:
    raw, manifest = _raw_documents()
    manifest["review"]["status"] = "maintainer-reviewed"
    manifest["review"]["reviewed_case_ids"] = [case["id"] for case in raw["cases"]]

    dataset = validate_quality_dataset(raw, manifest)

    assert dataset.review.status == "maintainer-reviewed"
    assert set(dataset.review.reviewed_case_ids) == {case.id for case in dataset.cases}


def test_pair_must_bind_one_error_and_one_correct_case() -> None:
    raw, manifest = _raw_documents()
    paired_correct = next(
        case
        for case in raw["cases"]
        if case["kind"] == "correct" and case["pair_id"] is not None
    )
    paired_correct["kind"] = "error"
    _rebind_manifest(raw, manifest)

    with pytest.raises(
        ValueError, match="each pair_id must bind one error and one correct case"
    ):
        validate_quality_dataset(raw, manifest)


def test_dataset_requires_every_phenomenon_pair() -> None:
    raw, manifest = _raw_documents()
    for case in raw["cases"]:
        if case["phenomenon"] == "rection":
            case["phenomenon"] = "syntax"
    _rebind_manifest(raw, manifest)

    with pytest.raises(ValueError, match="quality dataset must pair every phenomenon"):
        validate_quality_dataset(raw, manifest)


def test_finding_offsets_must_select_the_original_unicode_text() -> None:
    raw, manifest = _raw_documents()
    finding = _case(raw, "error")["expected_findings"][0]
    finding["start"] += 1

    with pytest.raises(ValueError, match="finding original does not match text range"):
        validate_quality_dataset(raw, manifest)


def test_conflict_case_requires_overlapping_half_open_spans() -> None:
    raw, manifest = _raw_documents()
    conflict = _case(raw, "conflict")
    conflict["expected_findings"][1]["start"] = conflict["expected_findings"][0]["end"]
    conflict["expected_findings"][1]["original"] = conflict["text"][
        conflict["expected_findings"][1]["start"] : conflict["expected_findings"][1][
            "end"
        ]
    ]
    _rebind_manifest(raw, manifest)

    with pytest.raises(
        ValueError, match="conflict case must contain overlapping expected findings"
    ):
        validate_quality_dataset(raw, manifest)


@pytest.mark.parametrize("mutation", ["finding", "rationale"])
def test_abstention_requires_no_findings_and_a_polish_rationale(mutation: str) -> None:
    raw, manifest = _raw_documents()
    abstention = _case(raw, "abstain")
    if mutation == "finding":
        abstention["expected_findings"] = [
            {
                "category": "punctuation",
                "start": 0,
                "end": 0,
                "original": "",
                "suggestion": ",",
                "rationale": "Testowa poprawka.",
            }
        ]
    else:
        abstention["rationale"] = " "
    _rebind_manifest(raw, manifest)

    with pytest.raises(ValueError, match="abstain case"):
        validate_quality_dataset(raw, manifest)


def test_quality_dataset_converts_to_legacy_metric_values() -> None:
    quality = load_quality_dataset()

    converted = as_evaluation_dataset(quality)

    assert converted.id == quality.id
    assert converted.schema_version == quality.schema_version
    assert converted.canonical_hash == quality.canonical_sha256
    assert tuple(case.id for case in converted.cases) == tuple(
        case.id for case in quality.cases
    )
