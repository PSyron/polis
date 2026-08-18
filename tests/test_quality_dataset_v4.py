from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from polis import Analyzer, AnalyzerConfig, Confidence
from polis.core import Category, Finding, Severity, Source
from polis.correction import findings_conflict
from polis.evaluation import quality_dataset
from polis.evaluation._quality_parsing import canonical_hash
from polis.evaluation._quality_types import JsonValue
from polis.evaluation._quality_v4 import (
    _V4_TRACEABILITY_SOURCES,
    validate_v4_dataset,
)

_PREVIOUS_DATASET_BYTE_HASHES = {
    quality_dataset.QualityDatasetVersion.V1: {
        "cases.json": (
            "d594b6e984d019ddce6de6efa54673f298db634c3b54a9139852e218a4fa1de7"
        ),
        "manifest.json": (
            "eeaf54b0ff921748873b3d186afb67dbdccbda21b6e938b788d10d6147f8c606"
        ),
    },
    quality_dataset.QualityDatasetVersion.V2: {
        "cases.json": (
            "e525f050ae7bd16de89896e4e0be3f996c5a85f4f73a0192115c42102debe2e5"
        ),
        "manifest.json": (
            "475efe0f7fd146b898fdee3507996f99aa96a098a3be7d890d9ed565a7373ce2"
        ),
    },
    quality_dataset.QualityDatasetVersion.V3: {
        "cases.json": (
            "9368376c2d53548d7a2409e6d120597b220a83443c8523ab17aa4f295507ffa8"
        ),
        "manifest.json": (
            "956479298747d3be9c9c73e6f7df3a5b72c1e67f8f0fe3b4c62b4139fa451b17"
        ),
    },
}


def _documents() -> tuple[dict[str, JsonValue], dict[str, JsonValue]]:
    cases_path, manifest_path = quality_dataset.quality_dataset_paths(
        quality_dataset.QualityDatasetVersion.V4
    )
    return (
        json.loads(cases_path.read_text(encoding="utf-8")),
        json.loads(manifest_path.read_text(encoding="utf-8")),
    )


def _rebind(raw: dict[str, JsonValue], manifest: dict[str, JsonValue]) -> None:
    digest = canonical_hash(raw)
    manifest["canonical_sha256"] = digest
    manifest["review"]["canonical_sha256"] = digest
    manifest["manifest_sha256"] = "pending"
    manifest["manifest_sha256"] = canonical_hash(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )


def _validate_mutation(
    raw: dict[str, JsonValue], manifest: dict[str, JsonValue]
) -> None:
    validate_v4_dataset(
        raw,
        manifest,
        expected_canonical_sha256=None,
        expected_manifest_sha256=None,
    )


def test_v4_loads_the_reviewed_public_dataset() -> None:
    dataset = quality_dataset.load_quality_dataset(
        version=quality_dataset.QualityDatasetVersion.V4
    )
    _, manifest = _documents()

    assert dataset.schema_version == 4
    assert dataset.id == "polis_v4_quality_development"
    assert len(dataset.cases) == 124
    assert dataset.review.reviewed_case_ids == tuple(case.id for case in dataset.cases)
    assert dataset.review.canonical_sha256 == dataset.canonical_sha256
    assert (
        dataset.canonical_sha256
        == "0a767850af7f5d37ccb8f4b63544dad91a7bd11744fe02b9652ebf33f644af5c"
    )
    assert manifest["canonical_sha256"] == dataset.canonical_sha256
    assert manifest["review"]["canonical_sha256"] == dataset.canonical_sha256
    assert (
        manifest["review"]["reviewed_case_ids_sha256"]
        == "0ca59077aa406d02128147b63a95116eec67f886c569129207a6b872d2ab7703"
    )
    assert (
        manifest["manifest_sha256"]
        == "120247819ff38ec45341b0ad44ea72d3a1015c19d48f7d0b8ab298a9329382bf"
    )


def test_v4_meets_the_category_and_shape_contract() -> None:
    dataset = quality_dataset.load_quality_dataset(
        version=quality_dataset.QualityDatasetVersion.V4
    )
    raw, manifest = _documents()

    assert manifest["contract"]["issue"] == 364
    contract_path = (
        Path(__file__).parents[1] / "docs/project/rule-coverage-contract-v1.json"
    )
    assert (
        hashlib.sha256(contract_path.read_bytes()).hexdigest()
        == manifest["contract"]["sha256"]
    )
    assert manifest["contract"]["minimums"] == {
        "positive_findings_per_category": 8,
        "hard_negative_cases_per_category": 16,
        "phenomenon_or_family_count": 3,
        "paired_examples_per_category": 4,
    }
    assert manifest["summary"]["case_count"] == len(raw["cases"]) == len(dataset.cases)
    for summary in manifest["summary"]["category"].values():
        assert summary["positive_findings"] >= 8
        assert summary["hard_negative_cases"] >= 16
        assert len(summary["rule_families"]) >= 3
        assert summary["paired_examples"] >= 4
    assert manifest["summary"]["category"]["agreement"]["phenomena"] == ["agreement"]
    for summary in manifest["summary"]["shape_strata"].values():
        assert summary["positive_cases"] >= 1
        assert summary["hard_negative_cases"] >= 1


def _conflict_candidates(raw: dict[str, JsonValue]) -> tuple[Finding, ...]:
    conflict = next(case for case in raw["cases"] if case["kind"] == "conflict")
    return tuple(
        Finding.create(
            category=Category.PUNCTUATION,
            severity=Severity.SUGGESTION,
            message="conflict candidate",
            explanation="project-authored ambiguity",
            original=finding["original"],
            suggestion=finding["suggestion"],
            start=finding["start"],
            end=finding["end"],
            confidence=Confidence(0.9),
            source=Source.parse("rule:quality-v4-conflict-control"),
        )
        for finding in conflict["expected_findings"]
    )


def test_v4_conflict_uses_distinct_minimal_competing_corrections() -> None:
    raw, manifest = _documents()
    conflict = next(case for case in raw["cases"] if case["kind"] == "conflict")

    assert conflict["id"] == "v4_control_conflict_punctuation"
    assert conflict["text"] == "Pada deszcz Anna wraca."
    candidates = {
        conflict["text"][: finding["start"]]
        + finding["suggestion"]
        + conflict["text"][finding["end"] :]
        for finding in conflict["expected_findings"]
    }
    assert candidates == {
        "Pada deszcz. Anna wraca.",
        "Pada deszcz; Anna wraca.",
    }
    for finding in conflict["expected_findings"]:
        assert finding["start"] == finding["end"] == 11
        assert finding["original"] == ""
        assert finding["allow_zero_width"] is True
        assert finding["suggestion"] in {".", ";"}
        assert finding["overlap_group"] == "controlled-conflict"
        assert finding["rule_family"] == (
            "project-authored:ambiguity.punctuation_boundary"
        )

    first, second = _conflict_candidates(raw)
    assert findings_conflict(first, second)
    assert first.start == first.end == second.start == second.end == 11
    assert first.suggestion != second.suggestion
    assert all("Ten zdanie" not in candidate for candidate in candidates)
    assert conflict["provider_behavior"] == {
        "provider_absent": "execute",
        "qualified_morphology": "execute",
        "provider_requirement": "none",
        "capability": None,
        "denominator_profile": "all-cases",
    }
    _validate_mutation(raw, manifest)


def test_v4_conflict_analyzer_abstains_in_both_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polis.analyzer as analyzer_module

    text = "Pada deszcz Anna wraca."
    qualified_loader = analyzer_module._load_qualified_morfeusz
    monkeypatch.setattr(analyzer_module, "_load_qualified_morfeusz", lambda: None)
    assert Analyzer(AnalyzerConfig()).analyze(text).issues == ()

    monkeypatch.setattr(analyzer_module, "_load_qualified_morfeusz", qualified_loader)
    qualified_provider = analyzer_module._load_qualified_morfeusz()
    assert qualified_provider is not None
    assert qualified_provider.identity.package_version == "1.99.15"
    assert qualified_provider.identity.dictionary_id == "pl.sgjp.sgjp-2026.06.01"
    assert Analyzer(AnalyzerConfig()).analyze(text).issues == ()


def test_v4_rejects_the_old_invalid_conflict_candidate() -> None:
    raw, manifest = _documents()
    conflict = next(case for case in raw["cases"] if case["kind"] == "conflict")
    conflict["text"] = "Te zdanie."
    conflict["traceability"] = {
        "source_identity": "rule:agreement.te_zdanie",
        "rule_family": "rule:agreement.te_zdanie",
        "audit_row": "rule:agreement.te_zdanie",
        "behavior_version": "agreement-te-zdanie/1.0",
    }
    conflict["expected_findings"] = [
        {
            **conflict["expected_findings"][0],
            "category": "agreement",
            "start": 0,
            "end": 2,
            "original": "Te",
            "suggestion": "To",
            "rule_family": "rule:agreement.te_zdanie",
            "overlap_group": "controlled-conflict",
            "allow_zero_width": False,
        },
        {
            **conflict["expected_findings"][1],
            "category": "agreement",
            "start": 0,
            "end": 2,
            "original": "Te",
            "suggestion": "Ten",
            "rule_family": "rule:agreement.te_zdanie",
            "overlap_group": "controlled-conflict",
            "allow_zero_width": False,
        },
    ]
    _rebind(raw, manifest)
    with pytest.raises(ValueError, match="invalid conflict correction"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_the_prior_te_dziecko_replacement() -> None:
    raw, manifest = _documents()
    conflict = next(case for case in raw["cases"] if case["kind"] == "conflict")
    conflict["text"] = "Te dziecko śpi."
    conflict["expected_findings"][0]["start"] = 0
    conflict["expected_findings"][0]["end"] = 2
    conflict["expected_findings"][0]["original"] = "Te"
    conflict["expected_findings"][0]["suggestion"] = "To"
    conflict["expected_findings"][1]["start"] = 0
    conflict["expected_findings"][1]["end"] = 10
    conflict["expected_findings"][1]["original"] = "Te dziecko"
    conflict["expected_findings"][1]["suggestion"] = "To dziecko"
    conflict["expected_findings"][0]["category"] = "agreement"
    conflict["expected_findings"][1]["category"] = "agreement"
    conflict["expected_findings"][0]["rule_family"] = "rule:agreement.te_neuter_noun"
    conflict["expected_findings"][1]["rule_family"] = "rule:agreement.te_neuter_noun"
    conflict["traceability"] = {
        "source_identity": "rule:agreement.te_neuter_noun",
        "rule_family": "rule:agreement.te_neuter_noun",
        "audit_row": "rule:agreement.te_neuter_noun",
        "behavior_version": "agreement-te-neuter-noun/2.0",
    }
    _rebind(raw, manifest)
    with pytest.raises(ValueError, match="invalid conflict correction"):
        _validate_mutation(raw, manifest)


def test_v4_preserves_exact_half_open_spans_and_minimal_suggestions() -> None:
    dataset = quality_dataset.load_quality_dataset(
        version=quality_dataset.QualityDatasetVersion.V4
    )

    for case in dataset.cases:
        for finding in case.findings:
            assert case.text[finding.start : finding.end] == finding.original
            assert finding.suggestion != finding.original
            assert finding.rationale.strip()


def test_v4_traceability_map_matches_public_audit_rows() -> None:
    audit = json.loads(
        (
            Path(__file__).parents[1] / "docs/project/rule-coverage-rjp-2026.json"
        ).read_text(encoding="utf-8")
    )
    rows = {
        row["source"]: (row["category"], row["behavior_version"])
        for row in audit["source_rows"]
    }

    assert _V4_TRACEABILITY_SOURCES == {
        source: rows[source] for source in _V4_TRACEABILITY_SOURCES
    }


def test_v4_public_validator_cli_reports_machine_readable_summary() -> None:
    result = subprocess.run(
        [
            "uv",
            "run",
            "--locked",
            "--extra",
            "dev",
            "python",
            "scripts/validate_quality_dataset_v4.py",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    summary = json.loads(result.stdout)

    assert summary["dataset_id"] == "polis_v4_quality_development"
    assert summary["dataset_version"] == 4
    assert summary["case_count"] == 124
    assert set(summary["category_counts"]) == {
        "agreement",
        "inflection",
        "punctuation",
        "spelling",
        "syntax",
    }


def test_quality_dataset_loader_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    dataset_path = tmp_path / "cases.json"
    manifest_path = tmp_path / "manifest.json"
    dataset_path.write_text(
        '{"schema_version": 4, "schema_version": 4}', encoding="utf-8"
    )
    manifest_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate JSON object key"):
        quality_dataset.load_quality_dataset(
            dataset_path=dataset_path,
            manifest_path=manifest_path,
            version=quality_dataset.QualityDatasetVersion.V4,
        )


def test_v4_rejects_duplicate_case_ids() -> None:
    raw, manifest = _documents()
    raw["cases"][1]["id"] = raw["cases"][0]["id"]

    with pytest.raises(ValueError, match="duplicate quality case id"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_missing_reviewed_case_id() -> None:
    raw, manifest = _documents()
    manifest["review"]["reviewed_case_ids"].pop()
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="reviewed_case_ids must equal all case ids"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_unknown_reviewed_case_id() -> None:
    raw, manifest = _documents()
    manifest["review"]["reviewed_case_ids"][-1] = "unknown_reviewed_case"
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="reviewed_case_ids must equal all case ids"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_canonical_digest_drift() -> None:
    raw, manifest = _documents()
    manifest["canonical_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="canonical_sha256 mismatch"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_manifest_digest_drift() -> None:
    raw, manifest = _documents()
    manifest["manifest_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="manifest_sha256 mismatch"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_rebound_published_identity() -> None:
    raw, manifest = _documents()
    raw["cases"][0]["rationale"] = "Changed after maintainer review."
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="published canonical identity"):
        quality_dataset.validate_quality_dataset(raw, manifest)


def test_v4_rejects_original_span_drift() -> None:
    raw, manifest = _documents()
    raw["cases"][0]["expected_findings"][0]["original"] = "inne"

    with pytest.raises(ValueError, match="finding original does not match"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_unapproved_zero_width_finding() -> None:
    raw, manifest = _documents()
    finding = raw["cases"][0]["expected_findings"][0]
    finding.update({"start": 0, "end": 0, "original": "", "suggestion": "x"})
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="zero-width finding"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_wrong_case_category() -> None:
    raw, manifest = _documents()
    raw["cases"][0]["category"] = "syntax"
    _rebind(raw, manifest)

    with pytest.raises(
        ValueError, match="finding category differs|traceability category mismatch"
    ):
        _validate_mutation(raw, manifest)


def test_v4_rejects_conflict_finding_category_mismatch() -> None:
    raw, manifest = _documents()
    conflict = next(case for case in raw["cases"] if case["kind"] == "conflict")
    conflict["expected_findings"][0]["category"] = "syntax"
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="rule_family category mismatch"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_traceability_family_drift_from_expected_finding() -> None:
    raw, manifest = _documents()
    case = raw["cases"][0]
    _, behavior = _V4_TRACEABILITY_SOURCES["rule:agreement.te_neuter_noun"]
    case["traceability"] = {
        "source_identity": "rule:agreement.te_neuter_noun",
        "rule_family": "rule:agreement.te_neuter_noun",
        "audit_row": "rule:agreement.te_neuter_noun",
        "behavior_version": behavior,
    }
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="must match expected findings"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_missing_pair_counterpart() -> None:
    raw, manifest = _documents()
    raw["cases"][0]["pair"]["counterpart_id"] = "unknown_pair_case"
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="pair counterpart"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_one_way_pair_counterpart() -> None:
    raw, manifest = _documents()
    raw["cases"][0]["pair"]["counterpart_id"] = raw["cases"][0]["id"]
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="pair counterpart is not reciprocal"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_reused_pair_discriminator() -> None:
    raw, manifest = _documents()
    first = next(case for case in raw["cases"] if case["pair"] is not None)
    target = next(
        case
        for case in raw["cases"]
        if case["pair"] is not None and case["pair_id"] != first["pair_id"]
    )
    feature = first["pair"]["differentiating_feature"]
    target["pair"]["differentiating_feature"] = feature
    counterpart = next(
        case for case in raw["cases"] if case["id"] == target["pair"]["counterpart_id"]
    )
    counterpart["pair"]["differentiating_feature"] = feature
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="differentiating features must be specific"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_reused_hard_negative_rationale() -> None:
    raw, manifest = _documents()
    rationale = next(
        case["boundary_rationale"] for case in raw["cases"] if case["kind"] == "correct"
    )
    target = next(
        case
        for case in raw["cases"]
        if case["kind"] == "correct" and case["boundary_rationale"] != rationale
    )
    target["boundary_rationale"] = rationale
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="hard-negative rationales"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_contradictory_labels_for_identical_text() -> None:
    raw, manifest = _documents()
    error_case = next(case for case in raw["cases"] if case["kind"] == "error")
    correct_case = next(case for case in raw["cases"] if case["kind"] == "correct")
    correct_case["text"] = error_case["text"]
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="contradictory case kinds"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_unmarked_overlapping_findings() -> None:
    raw, manifest = _documents()
    case = raw["cases"][3]
    first = case["expected_findings"][0]
    second = case["expected_findings"][1]
    second.update(
        {"start": first["start"], "end": first["end"], "original": first["original"]}
    )
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="overlapping v4 findings"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_incomplete_traceability() -> None:
    raw, manifest = _documents()
    raw["cases"][0]["traceability"]["rule_family"] = ""
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="traceability rule_family"):
        _validate_mutation(raw, manifest)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("source_identity", "rule:agreement.te_zdanie_substitute"),
        ("rule_family", "rule:agreement.te_zdanie_substitute"),
        ("audit_row", "rule:agreement.te_zdanie_substitute"),
        ("behavior_version", "agreement-te-zdanie/999.0"),
    ),
)
def test_v4_rejects_substituted_traceability_identity(field: str, value: str) -> None:
    raw, manifest = _documents()
    raw["cases"][0]["traceability"][field] = value
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="traceability"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_hard_negative_without_boundary_rationale() -> None:
    raw, manifest = _documents()
    raw["cases"][8]["boundary_rationale"] = None
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="boundary_rationale"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_provider_dependent_case_without_profile() -> None:
    raw, manifest = _documents()
    case = next(
        case
        for case in raw["cases"]
        if case["provider_behavior"]["provider_requirement"] == "qualified_morphology"
    )
    case["provider_behavior"]["provider_absent"] = "execute"
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="provider-dependent case"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_morphology_behavior_without_provider_profile() -> None:
    raw, manifest = _documents()
    case = next(
        case
        for case in raw["cases"]
        if case["traceability"]["source_identity"]
        == "rule:agreement.nominal_group_ta_nowy_ksiazka"
    )
    case["provider_behavior"]["provider_requirement"] = "none"
    case["provider_behavior"]["capability"] = None
    case["provider_behavior"]["denominator_profile"] = "all-cases"
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="provider profile does not match"):
        _validate_mutation(raw, manifest)


def test_v4_rejects_category_below_hard_negative_minimum() -> None:
    raw, manifest = _documents()
    case = raw["cases"][12]
    case["kind"] = "error"
    case["expected_findings"] = [
        {
            "category": "agreement",
            "start": 0,
            "end": 2,
            "original": "Te",
            "suggestion": "To",
            "rationale": "The mutation creates a controlled positive finding.",
            "rule_family": "rule:agreement.te_zdanie",
            "ambiguity_notes": [],
            "overlap_group": None,
            "allow_zero_width": False,
        }
    ]
    manifest["summary"]["category"]["agreement"]["positive_findings"] = 10
    manifest["summary"]["category"]["agreement"]["hard_negative_cases"] = 15
    manifest["summary"]["shape_strata"]["multi-sentence"]["positive_cases"] = 6
    manifest["summary"]["shape_strata"]["multi-sentence"]["hard_negative_cases"] = 9
    manifest["summary"]["kind"]["error"] = 41
    manifest["summary"]["kind"]["correct"] = 79
    _rebind(raw, manifest)

    with pytest.raises(ValueError, match="category coverage minimum"):
        _validate_mutation(raw, manifest)


def test_v4_keeps_previous_dataset_bytes_unchanged() -> None:
    _, manifest = _documents()

    for version, expected_hashes in _PREVIOUS_DATASET_BYTE_HASHES.items():
        cases_path, manifest_path = quality_dataset.quality_dataset_paths(version)
        assert (
            hashlib.sha256(cases_path.read_bytes()).hexdigest()
            == expected_hashes["cases.json"]
        )
        assert (
            hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            == expected_hashes["manifest.json"]
        )

    v3_hashes = _PREVIOUS_DATASET_BYTE_HASHES[quality_dataset.QualityDatasetVersion.V3]
    assert manifest["v3_byte_identity"] == {
        "cases_sha256": v3_hashes["cases.json"],
        "manifest_sha256": v3_hashes["manifest.json"],
    }
