from __future__ import annotations

from dataclasses import dataclass

from polis.evaluation._quality_parsing import (
    DATASET_FIELDS,
    canonical_hash,
    parse_case,
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
    QualityFeature,
    QualityPhenomenon,
    QualityReview,
)

V4_DATASET_FIELDS = frozenset({*DATASET_FIELDS, "gold_label_source"})
V4_MANIFEST_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "dataset_id",
        "dataset_version",
        "canonical_sha256",
        "manifest_sha256",
        "contract",
        "provenance",
        "profiles",
        "summary",
        "v3_byte_identity",
        "review",
    }
)
_V4_CASE_FIELDS = frozenset(
    {
        "id",
        "kind",
        "phenomenon",
        "pair_id",
        "features",
        "text",
        "category",
        "shape_strata",
        "expected_findings",
        "rationale",
        "provenance",
        "traceability",
        "provider_behavior",
        "boundary_rationale",
        "pair",
    }
)
_V4_FINDING_FIELDS = frozenset(
    {
        "category",
        "start",
        "end",
        "original",
        "suggestion",
        "rationale",
        "rule_family",
        "ambiguity_notes",
        "overlap_group",
        "allow_zero_width",
    }
)
_V4_PROVENANCE_FIELDS = frozenset({"source", "license", "reference"})
_V4_TRACEABILITY_FIELDS = frozenset(
    {"source_identity", "rule_family", "audit_row", "behavior_version"}
)
_V4_PROVIDER_FIELDS = frozenset(
    {
        "provider_absent",
        "qualified_morphology",
        "provider_requirement",
        "capability",
        "denominator_profile",
    }
)
_V4_PAIR_FIELDS = frozenset({"counterpart_id", "differentiating_feature"})
_V4_SHAPES = frozenset(
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
_V4_MORPHOLOGY_BEHAVIOR_MARKER = "+morfeusz2-"
_V4_CATEGORIES = frozenset(
    {"agreement", "inflection", "punctuation", "spelling", "syntax"}
)
_V4_TRACEABILITY_SOURCES: dict[str, tuple[str, str]] = {
    "rule:agreement.te_zdanie": (
        "agreement",
        "agreement-te-zdanie/1.0",
    ),
    "rule:agreement.te_neuter_noun": (
        "agreement",
        "agreement-te-neuter-noun/2.0",
    ),
    "rule:agreement.nominal_group_te_duze_okno": (
        "agreement",
        "agreement-nominal-group-te-duze-okno/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
    ),
    "rule:agreement.nominal_group_ta_nowy_ksiazka": (
        "agreement",
        "agreement-nominal-group-ta-nowy-ksiazka/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
    ),
    "rule:agreement.subject_verb_oni_czyta": (
        "agreement",
        "agreement-subject-verb-oni-czyta/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
    ),
    "rule:inflection.negated_widziec": (
        "inflection",
        "inflection-negated-widziec/2.0",
    ),
    "rule:inflection.negated_miec_czas": (
        "inflection",
        "inflection-negated-miec-czas/1.0",
    ),
    "rule:inflection.negated_lubic_kawe": (
        "inflection",
        "inflection-negated-lubic-kawe/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
    ),
    "rule:inflection.przygladac_sie_nowy_budynek": (
        "inflection",
        "inflection-przygladac-sie-nowy-budynek/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
    ),
    "rule:inflection.government_szukac_klucz": (
        "inflection",
        "inflection-government-szukac-klucz/1.0+morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
    ),
    "rule:spelling.napewno": ("spelling", "spelling-napewno/1.0"),
    "rule:spelling.wogole_diacritic": (
        "spelling",
        "spelling-wogole-diacritic/1.0",
    ),
    "rule:spelling.wziasc": ("spelling", "spelling-wziasc/1.0"),
    "rule:spelling.wziasc_diacritic": (
        "spelling",
        "spelling-wziasc-diacritic/1.0",
    ),
    "rule:syntax.comma_space": ("punctuation", "syntax-comma-space/1.0"),
    "rule:syntax.duplicate_comma": (
        "punctuation",
        "syntax-duplicate-comma/1.0",
    ),
    "rule:syntax.sentence_space": (
        "punctuation",
        "syntax-sentence-space/1.0",
    ),
    "rule:syntax.quote_space": ("punctuation", "syntax-quote-space/1.0"),
    "rule:punctuation.abbreviation_dot": (
        "punctuation",
        "punctuation-abbreviation-dot/1.0",
    ),
    "rule:syntax.initial_conditional_comma": (
        "syntax",
        "syntax-initial-conditional-comma/1.0",
    ),
    "rule:syntax.initial_temporal_comma": (
        "syntax",
        "syntax-initial-temporal-comma/1.0",
    ),
    "rule:syntax.comma_before_ze_reporting": (
        "syntax",
        "syntax-comma-before-ze-reporting/1.0",
    ),
    "rule:syntax.comma_before_zeby_purpose": (
        "syntax",
        "syntax-comma-before-zeby-purpose/1.0",
    ),
    "rule:syntax.comma_before_bo": (
        "syntax",
        "syntax-comma-before-bo/3.0",
    ),
    "rule:syntax.missing_reflexive": (
        "syntax",
        "syntax-missing-reflexive/1.0",
    ),
    "rule:syntax.missing_destination_preposition": (
        "syntax",
        "syntax-missing-destination-preposition/1.0",
    ),
}
_V3_CASES_BYTES_SHA256 = (
    "9368376c2d53548d7a2409e6d120597b220a83443c8523ab17aa4f295507ffa8"
)
_V3_MANIFEST_BYTES_SHA256 = (
    "956479298747d3be9c9c73e6f7df3a5b72c1e67f8f0fe3b4c62b4139fa451b17"
)
_V4_CANONICAL_SHA256 = (
    "e87ad62b54d5d77c00b32c43cc5ee74d7347cdaa5501bc72080eddd79e12fba4"
)
_V4_MANIFEST_SHA256 = "0561200bd16319737e4c484ba220ff588ae964dddd680f0285d88e35140cc07b"
_CONTRACT = {
    "path": "docs/project/rule-coverage-contract-v1.json",
    "sha256": "c98068a895919b22a916f9ecd2fafb1cb15ee698cb891e66c8d55ffb9194e629",
    "issue": 364,
    "schema_id": "polis.rule-coverage-contract",
    "schema_version": 1,
    "categories": sorted(_V4_CATEGORIES),
    "shape_strata": sorted(_V4_SHAPES),
    "minimums": {
        "positive_findings_per_category": 8,
        "hard_negative_cases_per_category": 16,
        "phenomenon_or_family_count": 3,
        "paired_examples_per_category": 4,
    },
    "provider_distinction": {
        "provider_absent_minimum_cases": 2,
        "provider_present_minimum_cases": 2,
    },
}


@dataclass(frozen=True, slots=True)
class _V4Record:
    case: QualityCase
    raw: dict[str, JsonValue]
    raw_findings: tuple[dict[str, JsonValue], ...]


def validate_v4_dataset(
    dataset: dict[str, JsonValue],
    manifest: dict[str, JsonValue],
    *,
    expected_canonical_sha256: str | None = _V4_CANONICAL_SHA256,
    expected_manifest_sha256: str | None = _V4_MANIFEST_SHA256,
) -> QualityDataset:
    require_exact_fields(dataset, V4_DATASET_FIELDS, "quality v4 dataset")
    require_exact_fields(manifest, V4_MANIFEST_FIELDS, "quality v4 manifest")
    for field, expected in (
        ("schema_id", "polis.quality-development-dataset"),
        ("schema_version", 4),
        ("id", "polis_v4_quality_development"),
        ("dataset_version", 4),
        ("license", "CC0-1.0"),
        ("source", "project-authored"),
        ("gold_label_source", "project-authored-manual"),
    ):
        require_literal(dataset, field, expected, "quality v4 dataset")
    for field, expected in (
        ("schema_id", "polis.quality-development-manifest"),
        ("schema_version", 4),
        ("dataset_id", dataset["id"]),
        ("dataset_version", 4),
    ):
        require_literal(manifest, field, expected, "quality v4 manifest")

    raw_cases = dataset["cases"]
    if not isinstance(raw_cases, list):
        raise QualityDatasetError("quality v4 dataset cases must be a list")
    seen_ids: set[str] = set()
    records = tuple(_parse_record(raw, seen_ids) for raw in raw_cases)
    cases = tuple(record.case for record in records)
    canonical_sha256 = canonical_hash(dataset)
    if (
        require_sha256(
            manifest["canonical_sha256"], "quality v4 manifest canonical_sha256"
        )
        != canonical_sha256
    ):
        raise QualityDatasetError("quality v4 dataset canonical_sha256 mismatch")
    if (
        expected_canonical_sha256 is not None
        and canonical_sha256 != expected_canonical_sha256
    ):
        raise QualityDatasetError("quality v4 published canonical identity mismatch")
    manifest_without_hash = {
        key: value for key, value in manifest.items() if key != "manifest_sha256"
    }
    manifest_sha256 = require_sha256(
        manifest["manifest_sha256"], "quality v4 manifest manifest_sha256"
    )
    if manifest_sha256 != canonical_hash(manifest_without_hash):
        raise QualityDatasetError("quality v4 manifest manifest_sha256 mismatch")
    if (
        expected_manifest_sha256 is not None
        and manifest_sha256 != expected_manifest_sha256
    ):
        raise QualityDatasetError("quality v4 published manifest identity mismatch")
    review = _parse_review(manifest["review"], canonical_sha256, cases)
    _validate_cases(records)
    _validate_manifest_metadata(manifest, records, canonical_sha256)
    return QualityDataset(
        schema_id="polis.quality-development-dataset",
        schema_version=4,
        id="polis_v4_quality_development",
        dataset_version=4,
        license="CC0-1.0",
        source="project-authored",
        cases=cases,
        canonical_sha256=canonical_sha256,
        review=review,
        manifest_canonical_sha256=canonical_sha256,
    )


def _parse_record(raw: JsonValue, seen_ids: set[str]) -> _V4Record:
    case = require_object(raw, "quality v4 case")
    require_exact_fields(case, _V4_CASE_FIELDS, "quality v4 case")
    raw_findings = case["expected_findings"]
    if not isinstance(raw_findings, list):
        raise QualityDatasetError("quality v4 expected_findings must be a list")
    findings = tuple(
        require_object(item, "quality v4 expected finding") for item in raw_findings
    )
    if any(set(item) != _V4_FINDING_FIELDS for item in findings):
        raise QualityDatasetError("quality v4 finding has invalid fields")
    core_findings = [
        {key: item[key] for key in DATASET_FINDING_FIELDS} for item in findings
    ]
    core_case = {key: case[key] for key in DATASET_CASE_FIELDS}
    core_case["expected_findings"] = core_findings
    parsed = parse_case(core_case, seen_ids)
    _validate_case_metadata(case, parsed, findings)
    return _V4Record(parsed, case, findings)


DATASET_CASE_FIELDS = frozenset(
    {
        "id",
        "kind",
        "phenomenon",
        "pair_id",
        "features",
        "text",
        "expected_findings",
        "rationale",
    }
)
DATASET_FINDING_FIELDS = frozenset(
    {"category", "start", "end", "original", "suggestion", "rationale"}
)


def _validate_case_metadata(
    raw: dict[str, JsonValue],
    case: QualityCase,
    findings: tuple[dict[str, JsonValue], ...],
) -> None:
    category = raw["category"]
    if category is not None and (
        not isinstance(category, str) or category not in _V4_CATEGORIES
    ):
        raise QualityDatasetError("quality v4 case category is unknown")
    if case.kind in {QualityCaseKind.ERROR, QualityCaseKind.CORRECT} and not isinstance(
        category, str
    ):
        raise QualityDatasetError("quality v4 finding case requires a category")
    if case.kind in {QualityCaseKind.CONFLICT, QualityCaseKind.ABSTAIN} and category:
        raise QualityDatasetError("quality v4 control case must not have a category")
    shapes = _require_string_list(raw["shape_strata"], "quality v4 shape_strata")
    if not shapes or not set(shapes) <= _V4_SHAPES:
        raise QualityDatasetError("quality v4 shape_strata is invalid")
    _validate_provenance(raw["provenance"])
    traceability = require_object(raw["traceability"], "quality v4 traceability")
    require_exact_fields(
        traceability, _V4_TRACEABILITY_FIELDS, "quality v4 traceability"
    )
    for field in _V4_TRACEABILITY_FIELDS:
        _require_non_blank(traceability[field], f"quality v4 traceability {field}")
    _validate_traceability(traceability, category)
    traceability_family = traceability["rule_family"]
    finding_families = {finding["rule_family"] for finding in findings}
    if case.kind is QualityCaseKind.ERROR and finding_families != {traceability_family}:
        raise QualityDatasetError(
            "quality v4 traceability rule_family must match expected findings"
        )
    provider = require_object(raw["provider_behavior"], "quality v4 provider_behavior")
    require_exact_fields(provider, _V4_PROVIDER_FIELDS, "quality v4 provider_behavior")
    _validate_provider(provider)
    morphology_bound = (
        _V4_MORPHOLOGY_BEHAVIOR_MARKER in traceability["behavior_version"]
    )
    provider_bound = provider["provider_requirement"] == "qualified_morphology"
    if morphology_bound != provider_bound:
        raise QualityDatasetError(
            "quality v4 provider profile does not match behavior identity"
        )
    boundary_rationale = raw["boundary_rationale"]
    if case.kind is QualityCaseKind.CORRECT:
        _require_non_blank(
            boundary_rationale, "quality v4 hard-negative boundary_rationale"
        )
        if case.findings:
            raise QualityDatasetError("quality v4 hard negative must have no findings")
    elif case.kind is QualityCaseKind.ERROR and not case.findings:
        raise QualityDatasetError("quality v4 positive case must have findings")
    elif boundary_rationale is not None:
        _require_non_blank(boundary_rationale, "quality v4 boundary_rationale")
    pair = raw["pair"]
    if case.pair_id is None and pair is not None:
        raise QualityDatasetError(
            "unpaired quality v4 case must not have pair metadata"
        )
    if case.pair_id is not None:
        pair_object = require_object(pair, "quality v4 pair")
        require_exact_fields(pair_object, _V4_PAIR_FIELDS, "quality v4 pair")
        _require_non_blank(pair_object["counterpart_id"], "quality v4 counterpart_id")
        _require_non_blank(
            pair_object["differentiating_feature"],
            "quality v4 differentiating_feature",
        )
    for index, finding in enumerate(findings):
        _validate_finding(finding, case, category, index)


def _validate_finding(
    finding: dict[str, JsonValue],
    case: QualityCase,
    category: JsonValue,
    index: int,
) -> None:
    finding_category = finding["category"]
    if category is not None and category != finding_category:
        raise QualityDatasetError(
            "quality v4 finding category differs from case category"
        )
    if category is None and case.kind is not QualityCaseKind.CONFLICT:
        raise QualityDatasetError("only conflict controls may omit a finding category")
    rule_family = _require_non_blank(
        finding["rule_family"], f"quality v4 finding {index} rule_family"
    )
    source_metadata = _V4_TRACEABILITY_SOURCES.get(rule_family)
    if source_metadata is None:
        raise QualityDatasetError(
            f"quality v4 finding {index} rule_family is not an audited source"
        )
    if finding_category != source_metadata[0]:
        raise QualityDatasetError(
            f"quality v4 finding {index} rule_family category mismatch"
        )
    notes = _require_string_list(
        finding["ambiguity_notes"], f"quality v4 finding {index} ambiguity_notes"
    )
    del notes
    overlap_group = finding["overlap_group"]
    if overlap_group is not None:
        _require_non_blank(overlap_group, f"quality v4 finding {index} overlap_group")
    allow_zero_width = finding["allow_zero_width"]
    if not isinstance(allow_zero_width, bool):
        raise QualityDatasetError("quality v4 allow_zero_width must be boolean")
    if finding["start"] == finding["end"] and not allow_zero_width:
        raise QualityDatasetError(
            "quality v4 zero-width finding must be explicitly allowed"
        )
    if case.kind is QualityCaseKind.CORRECT:
        raise QualityDatasetError("quality v4 correct case must not contain findings")


def _validate_traceability(
    traceability: dict[str, JsonValue], category: JsonValue
) -> None:
    source = traceability["source_identity"]
    family = traceability["rule_family"]
    audit_row = traceability["audit_row"]
    behavior_version = traceability["behavior_version"]
    if source != family:
        raise QualityDatasetError(
            "quality v4 traceability rule_family must equal source_identity"
        )
    if audit_row != source:
        raise QualityDatasetError(
            "quality v4 traceability audit_row must equal source_identity"
        )
    if not isinstance(source, str):
        raise QualityDatasetError("quality v4 traceability source_identity is invalid")
    source_metadata = _V4_TRACEABILITY_SOURCES.get(source)
    if source_metadata is None:
        raise QualityDatasetError(
            "quality v4 traceability source_identity is not an audited source"
        )
    if category is not None and category != source_metadata[0]:
        raise QualityDatasetError("quality v4 traceability category mismatch")
    if behavior_version != source_metadata[1]:
        raise QualityDatasetError("quality v4 traceability behavior_version mismatch")


def _validate_provenance(raw: JsonValue) -> None:
    provenance = require_object(raw, "quality v4 provenance")
    require_exact_fields(provenance, _V4_PROVENANCE_FIELDS, "quality v4 provenance")
    require_literal(provenance, "source", "project-authored", "quality v4 provenance")
    require_literal(provenance, "license", "CC0-1.0", "quality v4 provenance")
    _require_non_blank(provenance["reference"], "quality v4 provenance reference")


def _validate_provider(provider: dict[str, JsonValue]) -> None:
    for field in ("provider_absent", "qualified_morphology"):
        if provider[field] not in {"execute", "abstain"}:
            raise QualityDatasetError("quality v4 provider behavior is invalid")
    if provider["provider_requirement"] not in {"none", "qualified_morphology"}:
        raise QualityDatasetError("quality v4 provider requirement is invalid")
    capability = provider["capability"]
    if capability is not None:
        _require_non_blank(capability, "quality v4 provider capability")
    _require_non_blank(
        provider["denominator_profile"], "quality v4 denominator_profile"
    )
    dependent = provider["provider_requirement"] == "qualified_morphology"
    if dependent != (provider["capability"] == "morphological-analysis"):
        raise QualityDatasetError(
            "quality v4 provider capability does not match requirement"
        )
    if dependent and (
        provider["provider_absent"] != "abstain"
        or provider["qualified_morphology"] != "execute"
    ):
        raise QualityDatasetError(
            "provider-dependent case must abstain without capability"
        )


def _validate_cases(records: tuple[_V4Record, ...]) -> None:
    cases = tuple(record.case for record in records)
    if len(cases) != 124:
        raise QualityDatasetError("quality v4 dataset must contain 124 cases")
    _validate_pairs(records)
    _validate_category_minimums(records)
    _validate_shape_minimums(records)
    _validate_provider_minimums(records)
    _validate_control_cases(records)
    _validate_overlap_marks(records)
    _validate_core_matrix(cases)


def _validate_pairs(records: tuple[_V4Record, ...]) -> None:
    by_id = {record.case.id: record for record in records}
    pair_ids = {record.case.pair_id for record in records if record.case.pair_id}
    pair_groups = {
        pair_id: [record for record in records if record.case.pair_id == pair_id]
        for pair_id in pair_ids
    }
    for category in _V4_CATEGORIES:
        category_pairs = {
            pair_id
            for pair_id in pair_ids
            if pair_id
            and any(item.raw["category"] == category for item in pair_groups[pair_id])
        }
        if len(category_pairs) < 4:
            raise QualityDatasetError("each v4 category requires four paired examples")
        for shape in _V4_SHAPES:
            if not any(
                shape in item.raw["shape_strata"]
                for pair_id in category_pairs
                for item in pair_groups[pair_id]
            ):
                raise QualityDatasetError(
                    "each v4 category requires a pair in every shape stratum"
                )
    pair_features: dict[str, str] = {}
    for pair_id in pair_ids:
        if pair_id is None:
            continue
        group = pair_groups[pair_id]
        if len(group) != 2 or {item.case.kind for item in group} != {
            QualityCaseKind.ERROR,
            QualityCaseKind.CORRECT,
        }:
            raise QualityDatasetError(
                "v4 pair must contain one error and one correct case"
            )
        if len({item.raw["category"] for item in group}) != 1:
            raise QualityDatasetError("v4 pair category must be stable")
        for item in group:
            pair = require_object(item.raw["pair"], "quality v4 pair")
            counterpart = pair["counterpart_id"]
            counterpart_record = (
                by_id.get(counterpart) if isinstance(counterpart, str) else None
            )
            if counterpart_record is None or counterpart_record.case.pair_id != pair_id:
                raise QualityDatasetError("v4 pair counterpart is not reciprocal")
            counterpart_pair = require_object(
                counterpart_record.raw["pair"], "quality v4 pair"
            )
            if counterpart_pair["counterpart_id"] != item.case.id:
                raise QualityDatasetError("v4 pair counterpart is not reciprocal")
            pair_features[pair_id] = _require_non_blank(
                pair["differentiating_feature"], "quality v4 differentiating_feature"
            )
        if (
            len(
                {
                    _require_non_blank(
                        require_object(item.raw["pair"], "quality v4 pair")[
                            "differentiating_feature"
                        ],
                        "quality v4 differentiating_feature",
                    )
                    for item in group
                }
            )
            != 1
        ):
            raise QualityDatasetError("v4 pair differentiating feature must be stable")
    if len(pair_features) != len(set(pair_features.values())):
        raise QualityDatasetError("v4 pair differentiating features must be specific")


def _validate_category_minimums(records: tuple[_V4Record, ...]) -> None:
    for category in _V4_CATEGORIES:
        positives = [
            record
            for record in records
            if record.case.kind is QualityCaseKind.ERROR
            and record.raw["category"] == category
        ]
        negatives = [
            record
            for record in records
            if record.case.kind is QualityCaseKind.CORRECT
            and record.raw["category"] == category
        ]
        positive_findings = sum(len(record.case.findings) for record in positives)
        families = {
            finding["rule_family"]
            for record in positives
            for finding in record.raw_findings
        }
        if positive_findings < 8 or len(negatives) < 16 or len(families) < 3:
            raise QualityDatasetError("v4 category coverage minimum is not met")
        rationales = [
            _require_non_blank(
                record.raw["boundary_rationale"],
                "quality v4 hard-negative boundary_rationale",
            )
            for record in negatives
        ]
        if len(rationales) != len(set(rationales)):
            raise QualityDatasetError(
                "v4 hard-negative rationales must be case-specific"
            )
        phenomena = {record.case.phenomenon for record in positives}
        if len(phenomena) < 3 and len(families) < 3:
            raise QualityDatasetError(
                "v4 category phenomenon/family diversity minimum is not met"
            )


def _validate_shape_minimums(records: tuple[_V4Record, ...]) -> None:
    for category in _V4_CATEGORIES:
        for shape in _V4_SHAPES:
            positives = sum(
                record.case.kind is QualityCaseKind.ERROR
                and record.raw["category"] == category
                and shape in record.raw["shape_strata"]
                for record in records
            )
            negatives = sum(
                record.case.kind is QualityCaseKind.CORRECT
                and record.raw["category"] == category
                and shape in record.raw["shape_strata"]
                for record in records
            )
            if not positives or not negatives:
                raise QualityDatasetError(
                    "v4 category shape-stratum minimum is not met"
                )


def _validate_provider_minimums(records: tuple[_V4Record, ...]) -> None:
    dependent = [
        record
        for record in records
        if require_object(record.raw["provider_behavior"], "provider")[
            "provider_requirement"
        ]
        == "qualified_morphology"
    ]
    absent = sum(
        require_object(record.raw["provider_behavior"], "provider")["provider_absent"]
        == "abstain"
        for record in dependent
    )
    present = sum(
        require_object(record.raw["provider_behavior"], "provider")[
            "qualified_morphology"
        ]
        == "execute"
        for record in dependent
    )
    if absent < 2 or present < 2:
        raise QualityDatasetError("v4 provider distinction minimum is not met")


def _validate_control_cases(records: tuple[_V4Record, ...]) -> None:
    conflicts = [
        record for record in records if record.case.kind is QualityCaseKind.CONFLICT
    ]
    abstentions = [
        record for record in records if record.case.kind is QualityCaseKind.ABSTAIN
    ]
    if len(conflicts) != 1 or len(abstentions) != 3:
        raise QualityDatasetError("v4 must contain one conflict and three abstentions")
    if any(
        record.case.findings
        or record.case.rationale is None
        or QualityFeature.ABSTENTION not in record.case.features
        for record in abstentions
    ):
        raise QualityDatasetError("v4 abstention controls are invalid")

    conflict = conflicts[0]
    if conflict.case.id != "v4_control_conflict_agreement":
        raise QualityDatasetError("v4 conflict control identity is invalid")
    expected_candidates = (
        (0, 2, "Te", "To", "rule:agreement.te_neuter_noun"),
        (0, 10, "Te dziecko", "To dziecko", "rule:agreement.te_neuter_noun"),
    )
    actual_candidates = tuple(
        (
            finding.start,
            finding.end,
            finding.original,
            finding.suggestion,
            raw["rule_family"],
        )
        for finding, raw in zip(
            conflict.case.findings, conflict.raw_findings, strict=True
        )
    )
    if (
        conflict.case.text != "Te dziecko śpi."
        or actual_candidates != expected_candidates
    ):
        raise QualityDatasetError("invalid conflict correction")


def _validate_overlap_marks(records: tuple[_V4Record, ...]) -> None:
    for record in records:
        spans = [
            (finding.start, finding.end, raw["overlap_group"])
            for finding, raw in zip(
                record.case.findings, record.raw_findings, strict=True
            )
        ]
        for index, (start, end, group) in enumerate(spans):
            for other_start, other_end, other_group in spans[index + 1 :]:
                overlaps = start < other_end and other_start < end
                if overlaps and (
                    record.case.kind is not QualityCaseKind.CONFLICT
                    or not group
                    or not other_group
                ):
                    raise QualityDatasetError("overlapping v4 findings must be marked")


def _validate_core_matrix(cases: tuple[QualityCase, ...]) -> None:
    text_kinds: dict[str, QualityCaseKind] = {}
    for case in cases:
        previous_kind = text_kinds.setdefault(case.text, case.kind)
        if previous_kind is not case.kind:
            raise QualityDatasetError(
                "v4 identical text must not have contradictory case kinds"
            )
    paired = tuple(case for case in cases if case.pair_id is not None)
    for pair_id in {case.pair_id for case in paired}:
        if len({case.phenomenon for case in paired if case.pair_id == pair_id}) != 1:
            raise QualityDatasetError("v4 pair phenomenon must be stable")
    features = {feature for case in cases for feature in case.features}
    if features != set(QualityFeature):
        raise QualityDatasetError("v4 must cover every quality feature")


def _parse_review(
    raw: JsonValue, canonical_sha256: str, cases: tuple[QualityCase, ...]
) -> QualityReview:
    review = require_object(raw, "quality v4 review")
    expected_fields = frozenset(
        {
            "status",
            "reviewer_role",
            "checklist_version",
            "reviewed_case_ids",
            "reviewed_case_ids_sha256",
            "canonical_sha256",
        }
    )
    require_exact_fields(review, expected_fields, "quality v4 review")
    require_literal(review, "status", "maintainer-reviewed", "quality v4 review")
    require_literal(review, "reviewer_role", "Polis maintainer", "quality v4 review")
    require_literal(
        review,
        "checklist_version",
        "quality-development-review-v4",
        "quality v4 review",
    )
    raw_ids = review["reviewed_case_ids"]
    if not isinstance(raw_ids, list) or not all(
        isinstance(item, str) for item in raw_ids
    ):
        raise QualityDatasetError("quality v4 reviewed_case_ids must be strings")
    expected_ids = {case.id for case in cases}
    if len(raw_ids) != len(expected_ids) or set(raw_ids) != expected_ids:
        raise QualityDatasetError(
            "quality v4 reviewed_case_ids must equal all case ids"
        )
    if canonical_hash(raw_ids) != review["reviewed_case_ids_sha256"]:
        raise QualityDatasetError("quality v4 reviewed_case_ids_sha256 mismatch")
    if review["canonical_sha256"] != canonical_sha256:
        raise QualityDatasetError("quality v4 review canonical_sha256 mismatch")
    return QualityReview(
        "maintainer-reviewed",
        "Polis maintainer",
        "quality-development-review-v4",
        tuple(raw_ids),
        canonical_sha256,
    )


def _validate_manifest_metadata(
    manifest: dict[str, JsonValue],
    records: tuple[_V4Record, ...],
    canonical_sha256: str,
) -> None:
    if manifest["contract"] != _CONTRACT:
        raise QualityDatasetError(
            "v4 manifest is not bound to the accepted #364 contract"
        )
    provenance = require_object(
        manifest["provenance"], "quality v4 manifest provenance"
    )
    require_exact_fields(
        provenance,
        frozenset({"relationship", "author", "license", "source"}),
        "quality v4 manifest provenance",
    )
    require_literal(
        provenance, "author", "Paweł Cyroń", "quality v4 manifest provenance"
    )
    require_literal(provenance, "license", "CC0-1.0", "quality v4 manifest provenance")
    require_literal(
        provenance, "source", "project-authored", "quality v4 manifest provenance"
    )
    relationship = require_object(provenance["relationship"], "quality v4 relationship")
    require_exact_fields(
        relationship,
        frozenset(
            {"prior_versions", "carried_forward_case_ids", "excluded_case_rationale"}
        ),
        "quality v4 relationship",
    )
    if (
        relationship["prior_versions"] != ["v1", "v2", "v3"]
        or relationship["carried_forward_case_ids"] != []
    ):
        raise QualityDatasetError("v4 relationship must explicitly exclude prior cases")
    _require_non_blank(
        relationship["excluded_case_rationale"], "v4 exclusion rationale"
    )
    byte_identity = require_object(manifest["v3_byte_identity"], "v3 byte identity")
    require_exact_fields(
        byte_identity,
        frozenset({"cases_sha256", "manifest_sha256"}),
        "v3 byte identity",
    )
    require_literal(
        byte_identity, "cases_sha256", _V3_CASES_BYTES_SHA256, "v3 byte identity"
    )
    require_literal(
        byte_identity, "manifest_sha256", _V3_MANIFEST_BYTES_SHA256, "v3 byte identity"
    )
    expected_summary = _summary(records)
    if manifest["summary"] != expected_summary:
        raise QualityDatasetError("v4 manifest summary does not match the dataset")
    if canonical_sha256 != manifest["canonical_sha256"]:
        raise QualityDatasetError("v4 manifest metadata canonical hash drift")
    profiles = require_object(manifest["profiles"], "quality v4 profiles")
    require_exact_fields(
        profiles,
        frozenset({"provider_absent", "qualified_morphology"}),
        "quality v4 profiles",
    )
    for name, behavior, denominator in (
        ("provider_absent", "abstain", "provider-absent"),
        ("qualified_morphology", "execute", "qualified-provider"),
    ):
        profile = require_object(profiles[name], f"quality v4 profile {name}")
        require_exact_fields(
            profile,
            frozenset({"capability", "behavior", "denominator_profile"}),
            f"quality v4 profile {name}",
        )
        require_literal(
            profile,
            "capability",
            "morphological-analysis",
            f"quality v4 profile {name}",
        )
        require_literal(profile, "behavior", behavior, f"quality v4 profile {name}")
        require_literal(
            profile, "denominator_profile", denominator, f"quality v4 profile {name}"
        )


def _summary(records: tuple[_V4Record, ...]) -> dict[str, JsonValue]:
    category_summary: dict[str, JsonValue] = {}
    for category in sorted(_V4_CATEGORIES):
        positive = [
            record
            for record in records
            if record.case.kind is QualityCaseKind.ERROR
            and record.raw["category"] == category
        ]
        negative = [
            record
            for record in records
            if record.case.kind is QualityCaseKind.CORRECT
            and record.raw["category"] == category
        ]
        category_summary[category] = {
            "positive_findings": sum(len(record.case.findings) for record in positive),
            "hard_negative_cases": len(negative),
            "phenomena": sorted(
                {
                    case.case.phenomenon.value
                    for case in positive
                    if case.case.phenomenon is not None
                }
            ),
            "rule_families": sorted(
                {
                    finding["rule_family"]
                    for case in positive
                    for finding in case.raw_findings
                    if isinstance(finding["rule_family"], str)
                }
            ),
            "paired_examples": len(
                {
                    case.case.pair_id
                    for case in records
                    if case.case.pair_id and case.raw["category"] == category
                }
            ),
        }
    shape_summary: dict[str, JsonValue] = {}
    for shape in sorted(_V4_SHAPES):
        shape_summary[shape] = {
            "positive_cases": sum(
                record.case.kind is QualityCaseKind.ERROR
                and shape in record.raw["shape_strata"]
                for record in records
            ),
            "hard_negative_cases": sum(
                record.case.kind is QualityCaseKind.CORRECT
                and shape in record.raw["shape_strata"]
                for record in records
            ),
        }
    kind_summary = {
        kind.value: sum(record.case.kind is kind for record in records)
        for kind in QualityCaseKind
    }
    phenomenon_summary = {
        phenomenon.value: sum(
            record.case.phenomenon is phenomenon for record in records
        )
        for phenomenon in QualityPhenomenon
    }
    return {
        "case_count": len(records),
        "category": category_summary,
        "shape_strata": shape_summary,
        "kind": kind_summary,
        "phenomenon": phenomenon_summary,
        "provider_dependent_cases": sum(
            require_object(record.raw["provider_behavior"], "provider")[
                "provider_requirement"
            ]
            == "qualified_morphology"
            for record in records
        ),
    }


def _require_non_blank(value: JsonValue, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QualityDatasetError(f"{label} must be a non-blank string")
    return value


def _require_string_list(value: JsonValue, label: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise QualityDatasetError(f"{label} must be a list of non-blank strings")
    if len(set(value)) != len(value):
        raise QualityDatasetError(f"{label} must not contain duplicates")
    return value
