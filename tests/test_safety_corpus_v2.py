from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tarfile
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest

import polis.evaluation.safety_corpus as safety_corpus
from polis.evaluation import (
    SAFETY_CORPUS_ID,
    SAFETY_CORPUS_V2_ID,
    SAFETY_REVIEW_CHECKLIST_V2_VERSION,
    load_safety_corpus_json,
    load_safety_corpus_xml,
    safety_corpus_digest,
    safety_entity_catalog_ids,
    select_safety_cases_for_purpose,
    validate_safety_corpus,
)
from polis.evaluation.correction_corpus import (
    _CONTROLLED_ENTITY_SURFACES,
    CorpusUsageError,
    CorrectionCorpus,
    EntitySpan,
    IsolationRecord,
)
from polis.evaluation.correction_corpus import _entity_id as corpus_v3_entity_id

pytestmark = pytest.mark.research

ROOT = Path(__file__).resolve().parents[1]
V2_JSON = (
    ROOT
    / "tests"
    / "fixtures"
    / "evaluation"
    / "polish_correction_safety_corpus_v2.json"
)
V2_XML = (
    ROOT
    / "tests"
    / "fixtures"
    / "evaluation"
    / "polish_correction_safety_corpus_v2.xml"
)
V2_APPROVAL = (
    ROOT
    / "tests"
    / "fixtures"
    / "evaluation"
    / "polish_correction_safety_corpus_v2.approval.json"
)
RETAINED_EVIDENCE_HASHES = {
    "tests/fixtures/evaluation/polish_correction_safety_corpus_v1.json": (
        "921ce0accd120e443a9131f192b8669484d4dd24bf18898fbd2ebcafbe1a87d9"
    ),
    "tests/fixtures/evaluation/polish_correction_safety_corpus_v1.xml": (
        "f2fcefef2172efcf3e27338bacc106230cde48b37c3c6989a4803bddc8dcc908"
    ),
    "tests/fixtures/evaluation/polish_correction_safety_corpus_v1.approval.json": (
        "8f0bb298c32f3b1c58dcfe008ad5e21da6eed851237839cde14c433cfa2c8559"
    ),
    "tests/fixtures/evaluation/polish_correction_corpus_v3.json": (
        "bd2c186bb22e32f948ed6592c24bc2267c6a2a77b185bd9424310068e680a1f2"
    ),
    "tests/fixtures/evaluation/polish_correction_corpus_v3.xml": (
        "32d99cf82609ff43c034f008c64dbb1b3c19f04fb77ef89c834ff433ccf59e3c"
    ),
    "experiments/sentence_safety_gate/frozen_gate.json": (
        "9fe74303924707df59d44a654877cec074219ea6f3314d2a60c993052d8ab736"
    ),
    "experiments/sentence_safety_gate/holdout.started": (
        "198371e64acb4fe04c8b2ae962e172b37e61ef3149b2d832c97175bde10f4d82"
    ),
    "experiments/sentence_safety_gate/report.json": (
        "69c88ac8370ff9d604a4669b674dc242954c6b28cc7c6e7d60ade6764f8a1c99"
    ),
    "experiments/sentence_safety_gate/evaluated_source.json": (
        "b1bd4fda10301c06dbe5fd6c0397f88c1acf44016652299de854a4001acd5ab9"
    ),
}
V2_CHECKLIST = ROOT / "docs" / "evaluation-safety-corpus-v2-review-checklist.md"
_V2_REQUIRED_REVIEWER = "Polis architecture owner"
_V2_CANDIDATE_DIGEST = safety_corpus.V2_APPROVED_CANDIDATE_DIGEST
_V2_FROZEN_DIGEST = safety_corpus.V2_APPROVED_FROZEN_DIGEST


def _markdown_section(document: str, heading: str) -> str:
    match = re.search(
        rf"^{re.escape(heading)}\n(.*?)(?=^## |\Z)",
        document,
        flags=re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"missing section: {heading}"
    return match.group(1)


def _markdown_region(document: str, start: str, end: str | None = None) -> str:
    start_index = document.index(start)
    end_index = document.index(end, start_index) if end is not None else len(document)
    return document[start_index:end_index]


def _normalized_prose(markdown: str) -> str:
    return " ".join(markdown.split())


def _expected_prose(*phrases: str) -> str:
    return " ".join(phrases)


def _synthetic_word(index: int) -> str:
    letters = []
    value = index
    for _ in range(6):
        letters.append(chr(ord("a") + value % 26))
        value //= 26
    return "".join(letters)


def _minimal_v1_raw_corpus() -> dict[str, Any]:
    review = {
        "status": "pending-human-review",
        "reviewer": None,
        "reviewed_at": None,
        "checklist_version": "safety-corpus-review-v1",
    }
    provenance = {
        "source": "synthetic test corpus",
        "license": "CC0-1.0",
        "created": "2026-07-23",
        "method": "test fixture",
        "notes": "test-only synthetic data",
    }
    cases: list[dict[str, Any]] = []
    index = 0
    for stratum in ("inflection", "syntax", "punctuation", "hard_negative"):
        for ordinal in range(60):
            token = f"{_synthetic_word(index)} {_synthetic_word(index + 500)}"
            split = "development" if ordinal < 20 else "holdout"
            is_hard_negative = stratum == "hard_negative"
            cases.append(
                {
                    "id": f"synthetic_{stratum}_{ordinal:03d}",
                    "stratum": stratum,
                    "split": split,
                    "unit": "sentence",
                    "input": token,
                    "expected_output": token if is_hard_negative else f"x{token}",
                    "description": "synthetic test case",
                    "tags": ["synthetic"],
                    "normalized_template": token,
                    "entity_ids": [],
                    "entity_spans": [],
                    "protected_phenomenon": (
                        "synthetic_negative" if is_hard_negative else None
                    ),
                    "provenance": provenance,
                    "review": review,
                    "edits": (
                        []
                        if is_hard_negative
                        else [
                            {
                                "category": "inflection",
                                "start": 0,
                                "end": 0,
                                "original": "",
                                "suggestion": "x",
                                "rationale": "synthetic test edit",
                            }
                        ]
                    ),
                }
            )
            index += 1
    return {
        "schema_version": 3,
        "id": SAFETY_CORPUS_ID,
        "language": "pl-PL",
        "holdout_state": "unfrozen-candidates",
        "provenance": provenance,
        "review_policy": {
            "candidate_status": "pending-human-review",
            "approval_status": "human-reviewed",
            "required_reviewer": "Paweł Cyroń",
            "checklist_version": "safety-corpus-review-v1",
            "training_use": "prohibited",
        },
        "cases": cases,
    }


def _v2_raw_from_v1(raw: dict[str, Any]) -> dict[str, Any]:
    mutated = deepcopy(raw)
    mutated["id"] = SAFETY_CORPUS_V2_ID
    mutated["review_policy"]["required_reviewer"] = _V2_REQUIRED_REVIEWER
    mutated["review_policy"]["checklist_version"] = SAFETY_REVIEW_CHECKLIST_V2_VERSION
    for case in mutated["cases"]:
        case["review"]["checklist_version"] = SAFETY_REVIEW_CHECKLIST_V2_VERSION

    surface = "Alicja Kurek"
    token = f"{_synthetic_word(999)} {_synthetic_word(1499)}"
    case = mutated["cases"][0]
    case["input"] = f"{surface} {token}"
    case["expected_output"] = f"x{surface} {token}"
    case["normalized_template"] = f"<entity> {token}"
    case["entity_ids"] = ["alicja_kurek"]
    case["entity_spans"] = [{"start": 0, "end": len(surface), "surface": surface}]
    return mutated


def _synthetic_v2_isolation_corpus() -> CorrectionCorpus:
    return validate_safety_corpus(_v2_raw_from_v1(_minimal_v1_raw_corpus()))


def test_v2_policy_routes_a_mutated_v1_raw_corpus_without_changing_v1() -> None:
    assert SAFETY_CORPUS_V2_ID == "polis_polish_correction_safety_corpus_v2"
    assert SAFETY_REVIEW_CHECKLIST_V2_VERSION == "safety-corpus-review-v2"

    v1 = validate_safety_corpus(_minimal_v1_raw_corpus())
    v2 = validate_safety_corpus(_v2_raw_from_v1(_minimal_v1_raw_corpus()))

    assert v1.id == SAFETY_CORPUS_ID
    assert v1.required_reviewer == "Paweł Cyroń"
    assert v1.checklist_version == "safety-corpus-review-v1"
    assert v2.id == SAFETY_CORPUS_V2_ID
    assert v2.required_reviewer == _V2_REQUIRED_REVIEWER
    assert v2.checklist_version == SAFETY_REVIEW_CHECKLIST_V2_VERSION
    assert v2.cases[0].entity_ids == ("alicja_kurek",)


def test_v1_policy_rejects_a_v2_only_entity_surface() -> None:
    raw = _v2_raw_from_v1(_minimal_v1_raw_corpus())
    raw["id"] = SAFETY_CORPUS_ID
    raw["review_policy"]["required_reviewer"] = "Paweł Cyroń"
    raw["review_policy"]["checklist_version"] = "safety-corpus-review-v1"
    for case in raw["cases"]:
        case["review"]["checklist_version"] = "safety-corpus-review-v1"

    with pytest.raises(ValueError, match="controlled entity policy"):
        validate_safety_corpus(raw)


def test_v2_entity_catalog_is_nonempty_and_disjoint_from_v1() -> None:
    v1_ids = safety_entity_catalog_ids()
    v2_ids = safety_entity_catalog_ids(SAFETY_CORPUS_V2_ID)

    assert v2_ids
    assert v2_ids.isdisjoint(v1_ids)


def test_unknown_safety_corpus_catalog_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported safety corpus id"):
        safety_entity_catalog_ids("unknown_safety_corpus")


def test_unknown_safety_corpus_id_is_rejected_by_validation_and_selection() -> None:
    raw = _minimal_v1_raw_corpus()
    raw["id"] = "unknown_safety_corpus"

    with pytest.raises(ValueError, match="unsupported safety corpus id"):
        validate_safety_corpus(raw)

    known_corpus = validate_safety_corpus(_minimal_v1_raw_corpus())
    with pytest.raises(CorpusUsageError, match="requires the safety corpus"):
        select_safety_cases_for_purpose(
            replace(known_corpus, id="unknown_safety_corpus"), purpose="benchmark"
        )


def test_safety_corpus_policy_registry_cannot_be_extended_at_runtime() -> None:
    with pytest.raises(TypeError):
        cast(dict[str, object], safety_corpus._SAFETY_CORPUS_POLICIES)["unknown"] = (
            object()
        )


def test_v2_candidate_has_exact_balance_and_pending_review() -> None:
    from scripts.generate_safety_corpus_v2_candidates import build_candidate_corpus

    corpus = validate_safety_corpus(build_candidate_corpus())

    assert corpus.id == SAFETY_CORPUS_V2_ID
    assert corpus.holdout_state == "unfrozen-candidates"
    assert len(corpus.cases) == 240
    assert all(case.review.status == "pending-human-review" for case in corpus.cases)
    for stratum in ("inflection", "syntax", "punctuation", "hard_negative"):
        cases = [case for case in corpus.cases if case.stratum == stratum]
        assert len(cases) == 60
        assert sum(case.split == "development" for case in cases) == 20
        assert sum(case.split == "holdout" for case in cases) == 40


def test_v2_candidate_json_and_xml_are_equivalent() -> None:
    assert load_safety_corpus_json(V2_JSON) == load_safety_corpus_xml(V2_XML)


def test_v2_pending_candidate_cannot_expose_development_or_holdout() -> None:
    from scripts.generate_safety_corpus_v2_candidates import build_candidate_corpus

    corpus = validate_safety_corpus(build_candidate_corpus())

    with pytest.raises(CorpusUsageError, match="pending-human-review"):
        select_safety_cases_for_purpose(corpus, purpose="benchmark")
    with pytest.raises(CorpusUsageError, match="pending-human-review|frozen"):
        select_safety_cases_for_purpose(corpus, purpose="quality_gate")
    with pytest.raises(CorpusUsageError, match="training is prohibited"):
        select_safety_cases_for_purpose(corpus, purpose="training")


def test_v2_catalog_is_disjoint_from_v1_and_corpus_v3() -> None:
    corpus_v3_ids = frozenset(
        corpus_v3_entity_id(surface) for surface in _CONTROLLED_ENTITY_SURFACES
    )
    v2_ids = safety_entity_catalog_ids(SAFETY_CORPUS_V2_ID)

    assert v2_ids.isdisjoint(safety_entity_catalog_ids())
    assert v2_ids.isdisjoint(corpus_v3_ids)


def test_v2_generator_validates_every_reserved_asset() -> None:
    from scripts.generate_safety_corpus_v2_candidates import (
        build_candidate_corpus,
        validate_reserved_asset_isolation,
    )

    validate_reserved_asset_isolation(build_candidate_corpus())


def test_cross_corpus_isolation_rejects_normalized_input_collision() -> None:
    corpus = _synthetic_v2_isolation_corpus()
    record = IsolationRecord(
        id="normalized-input",
        input=f" \t{corpus.cases[0].input.swapcase()}\n",
    )

    with pytest.raises(CorpusUsageError, match="cross-corpus leakage by input"):
        safety_corpus.assert_no_cross_corpus_leakage(
            corpus, (record,), source="synthetic"
        )


def test_cross_corpus_isolation_rejects_normalized_template_collision() -> None:
    corpus = _synthetic_v2_isolation_corpus()
    case = corpus.cases[0]
    suffix = case.input[case.entity_spans[0].end :]
    surface = "Mira Ptak"
    record = IsolationRecord(
        id="normalized-template",
        input=f"{surface}{suffix}",
        entity_spans=(EntitySpan(0, len(surface), surface),),
    )

    with pytest.raises(CorpusUsageError, match="cross-corpus leakage by template"):
        safety_corpus.assert_no_cross_corpus_leakage(
            corpus, (record,), source="synthetic"
        )


def test_cross_corpus_isolation_rejects_canonical_entity_combination() -> None:
    corpus = _synthetic_v2_isolation_corpus()
    surface = "Alicją Kurek"
    record = IsolationRecord(
        id="canonical-entity-combination",
        input=f"{surface} isolatedmarker",
        entity_spans=(EntitySpan(0, len(surface), surface),),
    )

    with pytest.raises(
        CorpusUsageError, match="cross-corpus leakage by entity combination"
    ):
        safety_corpus.assert_no_cross_corpus_leakage(
            corpus, (record,), source="synthetic"
        )


def test_cross_corpus_isolation_rejects_near_template_family() -> None:
    corpus = _synthetic_v2_isolation_corpus()
    case = corpus.cases[0]
    suffix = case.input[case.entity_spans[0].end :]
    surface = "Mira Ptak"
    record = IsolationRecord(
        id="near-template-family",
        input=f"{surface}{suffix} extratoken",
        entity_spans=(EntitySpan(0, len(surface), surface),),
    )

    with pytest.raises(CorpusUsageError, match="near-identical cross-corpus"):
        safety_corpus.assert_no_cross_corpus_leakage(
            corpus, (record,), source="synthetic"
        )


def test_v2_validation_rejects_entity_combination_leakage_across_splits() -> None:
    raw = _v2_raw_from_v1(_minimal_v1_raw_corpus())
    holdout_case = raw["cases"][20]
    surface = "Alicja Kurek"
    input_text = f"{surface} unconnectedtokenalpha unconnectedtokenbeta"
    holdout_case["input"] = input_text
    holdout_case["expected_output"] = f"x{input_text}"
    holdout_case["normalized_template"] = (
        "<entity> unconnectedtokenalpha unconnectedtokenbeta"
    )
    holdout_case["entity_ids"] = ["alicja_kurek"]
    holdout_case["entity_spans"] = [
        {"start": 0, "end": len(surface), "surface": surface}
    ]

    with pytest.raises(ValueError, match="entity combination leakage across splits"):
        validate_safety_corpus(raw)


def test_retained_evidence_bytes_are_immutable() -> None:
    for relative_path, expected in RETAINED_EVIDENCE_HASHES.items():
        actual = hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest()
        assert actual == expected, relative_path


def test_v2_documentation_scopes_review_and_runtime_boundaries() -> None:
    checklist = _normalized_prose(V2_CHECKLIST.read_text(encoding="utf-8"))
    dataset_v2 = _normalized_prose(
        _markdown_section(
            (ROOT / "docs" / "evaluation-dataset.md").read_text(encoding="utf-8"),
            "## Independent sentence safety corpus v2 candidates",
        )
    )
    quality_gates_v2 = _normalized_prose(
        _markdown_region(
            (ROOT / "docs" / "llm-quality-gates.md").read_text(encoding="utf-8"),
            "Issue #119 creates `polis_polish_correction_safety_corpus_v2`",
        )
    )
    limitations_v2 = _normalized_prose(
        _markdown_region(
            (ROOT / "docs" / "limitations.md").read_text(encoding="utf-8"),
            "- Issue #119 prepares `polis_polish_correction_safety_corpus_v2`",
            "- No DOCX/ODT/RTF document adapters",
        )
    )
    roadmap_v2 = _normalized_prose(
        _markdown_region(
            (ROOT / "docs" / "project" / "ROADMAP.md").read_text(encoding="utf-8"),
            "After the valid but non-qualifying #115 run consumed the #114 holdout",
            "Rule implementations M1-03",
        )
    )
    adr = (
        ROOT
        / "docs"
        / "architecture"
        / "decisions"
        / "0020-runtime-first-product-charter.md"
    ).read_text(encoding="utf-8")
    adr_runtime = _normalized_prose(
        _markdown_section(adr, "## Product release authority")
    )
    adr_optional_research = _normalized_prose(
        _markdown_section(adr, "## Optional model extension")
    )
    optional_research_boundary = _expected_prose(
        "A local model may be researched, benchmarked, and integrated behind",
        "that boundary",
    )

    for required in (
        "all 240 records",
        _V2_REQUIRED_REVIEWER,
        "project-authored synthetic Polish",
        "CC0-1.0",
        "corpus v3",
        "safety corpus v1",
        "prompt examples",
        "fine-tuning assets",
        "E2E fixtures",
        _expected_prose(
            "Case-level safety-corpus-v1 holdout content or outcomes did not inform",
            "the candidate.",
        ),
        "does not authorize holdout access",
        _V2_CANDIDATE_DIGEST,
        _V2_FROZEN_DIGEST,
    ):
        assert required in checklist
    assert "all-case review" in checklist
    assert (
        f"candidate canonical JSON SHA-256 `{_V2_CANDIDATE_DIGEST}` to frozen "
        f"canonical JSON SHA-256 `{_V2_FROZEN_DIGEST}`"
    ) in checklist

    for required in (
        SAFETY_CORPUS_V2_ID,
        "240 newly project-authored synthetic Polish CC0-1.0 cases",
        _V2_REQUIRED_REVIEWER,
        _V2_CANDIDATE_DIGEST,
        _V2_FROZEN_DIGEST,
        "no development or holdout quality score",
        "does not change the thresholds",
        "failed #115 verdict",
        "separate follow-up issue may run a one-shot installed-package gate for #76",
        "does not authorize or execute that gate",
        "#85 and #90",
    ):
        assert required in dataset_v2

    for required in (
        _V2_FROZEN_DIGEST,
        "no development or holdout quality score",
        "does not itself qualify #76",
        _expected_prose(
            "A separate follow-up issue must first pass development and may then",
            "reserve the new holdout once",
        ),
        "unchanged automatic and reviewable gates",
        "separate from corpus v4 in #85",
        "gate in #90",
    ):
        assert required in quality_gates_v2

    for required in (
        _V2_FROZEN_DIGEST,
        "does not reverse the failed #115 verdict",
        "does not qualify #76",
        "A separate one-shot gate is still required",
        "separate from #85 and #90",
    ):
        assert required in limitations_v2

    for required in (
        _V2_FROZEN_DIGEST,
        "without producing a development or holdout quality score",
        "A separately tracked one-shot execution may unblock #76",
        "#119 itself does not authorize or run it",
        "#85 and #90 remain distinct majority-coverage work",
    ):
        assert required in roadmap_v2

    assert "runtime release path is authoritative" in adr_runtime
    assert "Optional research outcomes may inform later decisions" in adr_runtime
    assert optional_research_boundary in adr_optional_research
    assert "stays disabled by default" in adr_optional_research


def test_v2_fixture_matches_v2_only_generator() -> None:
    from scripts.generate_safety_corpus_v2_candidates import build_frozen_corpus

    raw: Any = json.loads(V2_JSON.read_text(encoding="utf-8"))
    source = (ROOT / "scripts" / "generate_safety_corpus_v2_candidates.py").read_text(
        encoding="utf-8"
    )

    assert cast(dict[str, Any], raw) == build_frozen_corpus()
    assert "generate_safety_corpus_candidates" not in source


def test_v2_protected_names_have_complete_unique_entity_evidence() -> None:
    corpus = load_safety_corpus_json(V2_JSON)
    protected_names = [
        case
        for case in corpus.cases
        if case.protected_phenomenon in {"proper_name", "place_name"}
    ]

    assert len(protected_names) == 20
    assert len({case.entity_ids for case in protected_names}) == 20
    assert all(len(case.entity_ids) == 1 for case in protected_names)
    assert all(len(case.entity_spans) == 1 for case in protected_names)


def test_v2_research_fixtures_are_excluded_from_source_distribution(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    build = subprocess.run(
        [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(dist)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr

    sdist = next(dist.glob("*.tar.gz"))
    with tarfile.open(sdist) as archive:
        members = archive.getnames()

    for name in (
        "polish_correction_safety_corpus_v2.json",
        "polish_correction_safety_corpus_v2.xml",
        "polish_correction_safety_corpus_v2.approval.json",
    ):
        assert not any(member.endswith(name) for member in members)


def test_v2_neuter_demonstrative_cases_keep_neuter_predicates() -> None:
    corpus = load_safety_corpus_json(V2_JSON)
    cases = {case.id: case for case in corpus.cases}
    expected = {
        "safety_v2_inflection_011": (
            "Na pulpicie przez cały ranek leżało to radio awaryjne."
        ),
        "safety_v2_inflection_012": (
            "W zestawie demonstracyjnym znajdowało się to lustro sygnałowe."
        ),
        "safety_v2_inflection_013": "Obok wejścia wisiało to godło zakładowe.",
        "safety_v2_inflection_014": "W magazynie pozostało to pudło montażowe.",
        "safety_v2_inflection_015": (
            "Na końcu korytarza działało to światło ostrzegawcze."
        ),
        "safety_v2_inflection_016": "Pod osłoną pracowało to sprzęgło pomocnicze.",
        "safety_v2_inflection_017": ("W gablocie było widoczne to zdjęcie archiwalne."),
        "safety_v2_inflection_018": (
            "W skrzyni transportowej spoczywało to krzesło składane."
        ),
        "safety_v2_inflection_019": (
            "Na stanowisku testowym stało to ogniwo pomiarowe."
        ),
        "safety_v2_inflection_020": "W dokumentacji widniało to hasło kontrolne.",
    }

    for case_id, expected_output in expected.items():
        assert cases[case_id].expected_output == expected_output


def test_v2_abbreviation_hard_negatives_do_not_bypass_entity_catalog() -> None:
    corpus = load_safety_corpus_json(V2_JSON)
    case = next(
        item for item in corpus.cases if item.id == "safety_v2_hard_negative_034"
    )

    assert case.input == "Przesyłkę nadano w woj. pomorskim."
    assert not case.entity_ids
    assert not case.entity_spans


def test_v2_architecture_owner_role_can_record_complete_review() -> None:
    from scripts.generate_safety_corpus_v2_candidates import build_candidate_corpus

    raw = build_candidate_corpus()
    raw["holdout_state"] = "frozen"
    raw["review_policy"]["required_reviewer"] = _V2_REQUIRED_REVIEWER
    for case in raw["cases"]:
        case["review"] = {
            "status": "human-reviewed",
            "reviewer": _V2_REQUIRED_REVIEWER,
            "reviewed_at": "2026-07-23",
            "checklist_version": SAFETY_REVIEW_CHECKLIST_V2_VERSION,
        }

    corpus = validate_safety_corpus(raw)

    assert corpus.required_reviewer == _V2_REQUIRED_REVIEWER
    assert all(case.review.reviewer == _V2_REQUIRED_REVIEWER for case in corpus.cases)
    development = select_safety_cases_for_purpose(corpus, purpose="benchmark")
    assert len(development) == 80
    assert all(case.split == "development" for case in development)


def test_v1_benchmark_selection_remains_compatible_without_gate_evidence() -> None:
    raw = _minimal_v1_raw_corpus()
    raw["holdout_state"] = "frozen"
    for case in raw["cases"]:
        case["review"] = {
            "status": "human-reviewed",
            "reviewer": "Paweł Cyroń",
            "reviewed_at": "2026-07-23",
            "checklist_version": "safety-corpus-review-v1",
        }

    development = select_safety_cases_for_purpose(
        validate_safety_corpus(raw), purpose="benchmark"
    )

    assert len(development) == 80
    assert all(case.split == "development" for case in development)


def test_v2_quality_gate_rejects_unapproved_content_and_review_date_drift() -> None:
    raw: Any = json.loads(V2_JSON.read_text(encoding="utf-8"))
    raw["provenance"]["notes"] += " Unapproved digest drift."
    for case in raw["cases"]:
        case["review"]["reviewed_at"] = "2026-08-03"

    corpus = validate_safety_corpus(raw)

    assert safety_corpus_digest(raw) != _V2_FROZEN_DIGEST
    with pytest.raises(CorpusUsageError, match="approved"):
        cases = select_safety_cases_for_purpose(corpus, purpose="quality_gate")
        pytest.fail(f"quality gate returned {len(cases)} drifted holdout cases")


def test_v2_quality_gate_rejects_digest_drift_with_original_manifest() -> None:
    raw: Any = json.loads(V2_JSON.read_text(encoding="utf-8"))
    approval: Any = json.loads(V2_APPROVAL.read_text(encoding="utf-8"))
    raw["provenance"]["notes"] += " Still-valid digest drift."
    corpus = validate_safety_corpus(raw)

    with pytest.raises(CorpusUsageError, match="approved frozen corpus digest"):
        select_safety_cases_for_purpose(
            corpus,
            purpose="quality_gate",
            raw=raw,
            approval_manifest=approval,
        )


def test_v2_quality_gate_rejects_wrong_approved_review_date_binding() -> None:
    raw: Any = json.loads(V2_JSON.read_text(encoding="utf-8"))
    approval: Any = json.loads(V2_APPROVAL.read_text(encoding="utf-8"))
    for case in raw["cases"]:
        case["review"]["reviewed_at"] = "2026-08-03"
    approval["reviewed_at"] = "2026-08-03"
    approval["frozen_digest"] = safety_corpus_digest(raw)
    corpus = validate_safety_corpus(raw)

    with pytest.raises(CorpusUsageError, match="approval manifest"):
        select_safety_cases_for_purpose(
            corpus,
            purpose="quality_gate",
            raw=raw,
            approval_manifest=approval,
        )


def test_v2_quality_gate_rejects_wrong_manifest_binding() -> None:
    raw: Any = json.loads(V2_JSON.read_text(encoding="utf-8"))
    approval: Any = json.loads(V2_APPROVAL.read_text(encoding="utf-8"))
    approval["approval_scope"] = "holdout-only"
    corpus = validate_safety_corpus(raw)

    with pytest.raises(CorpusUsageError, match="approval manifest"):
        select_safety_cases_for_purpose(
            corpus,
            purpose="quality_gate",
            raw=raw,
            approval_manifest=approval,
        )


def test_committed_v2_approval_evidence_is_admissible_without_holdout_selection() -> (
    None
):
    raw: Any = json.loads(V2_JSON.read_text(encoding="utf-8"))
    approval: Any = json.loads(V2_APPROVAL.read_text(encoding="utf-8"))
    corpus = validate_safety_corpus(raw)

    safety_corpus._validate_quality_gate_admission(
        corpus, raw=raw, approval_manifest=approval
    )


def test_v2_role_approval_manifest_binds_candidate_and_frozen_digests() -> None:
    from scripts.generate_safety_corpus_v2_candidates import (
        build_candidate_corpus,
        build_frozen_corpus,
    )

    approval: Any = json.loads(V2_APPROVAL.read_text(encoding="utf-8"))
    candidate = build_candidate_corpus()
    frozen = build_frozen_corpus()

    assert approval["corpus_id"] == SAFETY_CORPUS_V2_ID
    assert approval["approval_scope"] == "all-cases"
    assert approval["approved_case_count"] == 240
    assert approval["reviewer"] == "Polis architecture owner"
    assert approval["reviewed_at"] == "2026-08-02"
    assert approval["checklist_version"] == SAFETY_REVIEW_CHECKLIST_V2_VERSION
    assert approval["candidate_digest"] == (
        "c64f009f14f0cde8390a46acc24660305534576bc897f70e281ffebbbbca6f53"
    )
    assert approval["candidate_digest"] == safety_corpus_digest(candidate)
    assert approval["frozen_digest"] == safety_corpus_digest(frozen)
    assert approval["frozen_digest"] == safety_corpus.V2_APPROVED_FROZEN_DIGEST


def test_committed_v2_corpus_is_frozen_after_role_review() -> None:
    corpus = load_safety_corpus_json(V2_JSON)

    assert corpus.holdout_state == "frozen"
    assert corpus.required_reviewer == "Polis architecture owner"
    assert all(case.review.status == "human-reviewed" for case in corpus.cases)
    assert all(
        case.review.reviewer == "Polis architecture owner" for case in corpus.cases
    )
    assert all(case.review.reviewed_at == "2026-08-02" for case in corpus.cases)
