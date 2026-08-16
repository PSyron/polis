"""Validation rules for the active quality-development dataset."""

from __future__ import annotations

import json
from pathlib import Path

from polis.evaluation._quality_parsing import (
    DATASET_FIELDS,
    MANIFEST_FIELDS,
    canonical_hash,
    parse_case,
    parse_review,
    require_exact_fields,
    require_literal,
    require_object,
    require_sha256,
)
from polis.evaluation._quality_types import (
    JsonValue,
    QualityCase,
    QualityCaseKind,
    QualityDataset,
    QualityDatasetError,
    QualityDatasetVersion,
    QualityFeature,
    QualityPhenomenon,
    quality_dataset_paths,
)
from polis.evaluation._quality_v2 import V2_MANIFEST_FIELDS, validate_v2_manifest
from polis.evaluation._quality_v3 import V3_MANIFEST_FIELDS, validate_v3_manifest


def load_quality_dataset(
    dataset_path: Path | None = None,
    manifest_path: Path | None = None,
    *,
    version: QualityDatasetVersion = QualityDatasetVersion.V1,
) -> QualityDataset:
    """Load and strictly validate the active UTF-8 dataset and manifest."""

    selected_dataset_path, selected_manifest_path = quality_dataset_paths(version)
    dataset_path = dataset_path or selected_dataset_path
    manifest_path = manifest_path or selected_manifest_path
    try:
        dataset_raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise QualityDatasetError("invalid quality dataset JSON") from error
    try:
        manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise QualityDatasetError("invalid quality manifest JSON") from error
    return validate_quality_dataset(dataset_raw, manifest_raw)


def validate_quality_dataset(
    dataset_raw: JsonValue, manifest_raw: JsonValue
) -> QualityDataset:
    """Parse exact schema-version-1 documents and fail closed on any drift."""

    dataset = require_object(dataset_raw, "quality dataset")
    manifest = require_object(manifest_raw, "quality manifest")
    require_exact_fields(dataset, DATASET_FIELDS, "quality dataset")
    raw_schema_version = dataset.get("schema_version")
    if (
        isinstance(raw_schema_version, bool)
        or not isinstance(raw_schema_version, int)
        or raw_schema_version not in {1, 2, 3}
    ):
        raise QualityDatasetError("quality dataset schema_version must be 1, 2, or 3")
    schema_version = raw_schema_version
    if schema_version == 1:
        expected_manifest_fields = MANIFEST_FIELDS
    elif schema_version == 2:
        expected_manifest_fields = V2_MANIFEST_FIELDS
    else:
        expected_manifest_fields = V3_MANIFEST_FIELDS
    require_exact_fields(manifest, expected_manifest_fields, "quality manifest")
    require_literal(
        dataset, "schema_id", "polis.quality-development-dataset", "quality dataset"
    )
    expected_id = f"polis_v{schema_version}_quality_development"
    require_literal(dataset, "id", expected_id, "quality dataset")
    require_literal(dataset, "dataset_version", schema_version, "quality dataset")
    require_literal(dataset, "license", "CC0-1.0", "quality dataset")
    require_literal(dataset, "source", "project-authored", "quality dataset")
    require_literal(
        manifest, "schema_id", "polis.quality-development-manifest", "quality manifest"
    )
    require_literal(manifest, "schema_version", schema_version, "quality manifest")
    require_literal(manifest, "dataset_id", dataset["id"], "quality manifest")
    require_literal(
        manifest, "dataset_version", dataset["dataset_version"], "quality manifest"
    )

    raw_cases = dataset["cases"]
    if not isinstance(raw_cases, list):
        raise QualityDatasetError("quality dataset cases must be a list")
    seen_ids: set[str] = set()
    cases = tuple(parse_case(raw, seen_ids) for raw in raw_cases)
    canonical_sha256 = canonical_hash(dataset_raw)
    manifest_hash = require_sha256(
        manifest["canonical_sha256"], "quality manifest canonical_sha256"
    )
    if manifest_hash != canonical_sha256:
        raise QualityDatasetError("quality dataset canonical_sha256 mismatch")

    review = parse_review(
        manifest["review"],
        checklist_version=f"quality-development-review-v{schema_version}",
    )
    if review.canonical_sha256 != canonical_sha256:
        raise QualityDatasetError("quality review canonical_sha256 mismatch")
    if review.status == "maintainer-reviewed" and (
        set(review.reviewed_case_ids) != {case.id for case in cases}
        or len(review.reviewed_case_ids) != len(cases)
    ):
        raise QualityDatasetError("reviewed_case_ids must equal all case ids")
    if schema_version == 2:
        validate_v2_manifest(manifest, cases, raw_cases)
    if schema_version == 3:
        validate_v3_manifest(manifest, cases, raw_cases)
    _validate_matrix(cases)
    return QualityDataset(
        schema_id="polis.quality-development-dataset",
        schema_version=schema_version,
        id=expected_id,
        dataset_version=schema_version,
        license="CC0-1.0",
        source="project-authored",
        cases=cases,
        canonical_sha256=canonical_sha256,
        review=review,
        manifest_canonical_sha256=manifest_hash,
    )


def _validate_matrix(cases: tuple[QualityCase, ...]) -> None:
    paired = [case for case in cases if case.pair_id is not None]
    pair_ids = {case.pair_id for case in paired}
    if any(
        {case.kind for case in paired if case.pair_id == pair_id}
        != {QualityCaseKind.ERROR, QualityCaseKind.CORRECT}
        or len([case for case in paired if case.pair_id == pair_id]) != 2
        for pair_id in pair_ids
    ):
        raise QualityDatasetError(
            "each pair_id must bind one error and one correct case"
        )
    if {case.phenomenon for case in paired} != set(QualityPhenomenon) or any(
        len({case.phenomenon for case in paired if case.pair_id == pair_id}) != 1
        for pair_id in pair_ids
    ):
        raise QualityDatasetError("quality dataset must pair every phenomenon")
    features = {feature for case in cases for feature in case.features}
    if features != set(QualityFeature):
        raise QualityDatasetError("quality dataset must cover every required feature")
    conflicts = [case for case in cases if case.kind is QualityCaseKind.CONFLICT]
    if len(conflicts) != 1 or QualityFeature.CONFLICT not in conflicts[0].features:
        raise QualityDatasetError(
            "quality dataset must contain one tagged conflict case"
        )
    spans = [(item.start, item.end) for item in conflicts[0].findings]
    if len(spans) < 2 or not any(
        first_start < second_end and second_start < first_end
        for index, (first_start, first_end) in enumerate(spans)
        for second_start, second_end in spans[index + 1 :]
    ):
        raise QualityDatasetError(
            "conflict case must contain overlapping expected findings"
        )
    abstentions = [case for case in cases if case.kind is QualityCaseKind.ABSTAIN]
    if len(abstentions) != 3 or any(
        case.findings
        or case.rationale is None
        or QualityFeature.ABSTENTION not in case.features
        for case in abstentions
    ):
        raise QualityDatasetError(
            "abstain case requires no findings and a Polish rationale"
        )
    if any(
        case.kind is QualityCaseKind.ERROR
        and (not case.findings or case.rationale is not None)
        or case.kind is QualityCaseKind.CORRECT
        and (case.findings or case.rationale is not None)
        for case in paired
    ):
        raise QualityDatasetError("paired case findings do not match the case kind")
