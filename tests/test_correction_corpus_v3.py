from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import experiments.real_llm_benchmark.run_benchmark as benchmark_runner
import pytest
from experiments.real_llm_benchmark.run_benchmark import (
    DEFAULT_CORPUS_PATH,
)
from experiments.real_llm_benchmark.run_benchmark import (
    load_cases as load_benchmark_cases,
)

from polis.evaluation.correction_corpus import (
    CorpusUsageError,
    EntitySpan,
    IsolationRecord,
    assert_no_training_leakage,
    load_correction_corpus_json,
    load_correction_corpus_xml,
    select_cases_for_purpose,
    validate_correction_corpus,
)

ROOT = Path(__file__).resolve().parents[1]
JSON_CORPUS = (
    ROOT / "tests" / "fixtures" / "evaluation" / "polish_correction_corpus_v3.json"
)
XML_CORPUS = (
    ROOT / "tests" / "fixtures" / "evaluation" / "polish_correction_corpus_v3.xml"
)
GUIDE = ROOT / "docs" / "evaluation-dataset.md"
CHECKLIST = ROOT / "docs" / "evaluation-corpus-v3-review-checklist.md"


def _raw_corpus() -> dict[str, Any]:
    value: Any = json.loads(JSON_CORPUS.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def _approve_all(raw: dict[str, Any]) -> None:
    for case in raw["cases"]:
        case["review"] = {
            "status": "human-reviewed",
            "reviewer": "Paweł Cyroń",
            "reviewed_at": "2026-07-21",
            "checklist_version": "corpus-v3-review-v1",
        }


def test_v3_corpus_has_exact_stratum_and_intended_split_balance() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)

    assert corpus.schema_version == 3
    assert corpus.id == "polis_polish_correction_corpus_v3"
    assert corpus.holdout_state == "unfrozen-candidates"
    assert len(corpus.cases) == 240
    for stratum in ("inflection", "syntax", "punctuation", "hard_negative"):
        cases = [case for case in corpus.cases if case.stratum == stratum]
        assert len(cases) == 60
        assert sum(case.split == "development" for case in cases) == 20
        assert sum(case.split == "holdout" for case in cases) == 40


def test_all_candidates_have_cc0_provenance_and_pending_review() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)

    assert corpus.provenance.license == "CC0-1.0"
    assert all(case.provenance.license == "CC0-1.0" for case in corpus.cases)
    assert all(case.review.status == "pending-human-review" for case in corpus.cases)
    assert all(case.review.reviewer is None for case in corpus.cases)
    assert all(case.review.reviewed_at is None for case in corpus.cases)


def test_positive_edits_use_unicode_offsets_and_reconstruct_expected_output() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)

    positives = [case for case in corpus.cases if case.stratum != "hard_negative"]
    assert positives
    for case in positives:
        assert case.edits
        corrected = case.input
        for edit in sorted(case.edits, key=lambda item: item.start, reverse=True):
            assert case.input[edit.start : edit.end] == edit.original
            corrected = (
                corrected[: edit.start] + edit.suggestion + corrected[edit.end :]
            )
        assert corrected == case.expected_output, case.id


def test_hard_negatives_are_named_protected_no_change_cases() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)

    negatives = [case for case in corpus.cases if case.stratum == "hard_negative"]
    assert negatives
    assert all(case.input == case.expected_output for case in negatives)
    assert all(not case.edits for case in negatives)
    assert all(case.protected_phenomenon for case in negatives)
    phenomena = {case.protected_phenomenon for case in negatives}
    assert {
        "correct_name_inflection",
        "correct_surname_inflection",
        "indeclinable_name",
        "marked_word_order",
        "quotation_punctuation",
        "list_punctuation",
        "url_or_number",
        "paragraph_boundary",
    } <= phenomena


def test_inflection_names_are_diverse_and_syntax_protects_marked_order() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)

    inflection = [case for case in corpus.cases if case.stratum == "inflection"]
    named_inflection = [
        case for case in inflection if {"name", "surname"} & set(case.tags)
    ]
    assert len(named_inflection) >= 30
    assert len({case.normalized_template for case in named_inflection}) == len(
        named_inflection
    )
    marked_order = [
        case
        for case in corpus.cases
        if case.protected_phenomenon == "marked_word_order"
    ]
    assert len(marked_order) >= 8
    assert all(case.stratum == "hard_negative" for case in marked_order)


def test_corpus_contains_sentences_and_short_paragraphs() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)

    assert {case.unit for case in corpus.cases} == {"sentence", "short_paragraph"}
    assert sum(case.unit == "short_paragraph" for case in corpus.cases) >= 24


def test_inflection_and_syntax_families_span_development_and_holdout() -> None:
    raw = _raw_corpus()
    inflection = [case for case in raw["cases"] if case["stratum"] == "inflection"]
    syntax = [case for case in raw["cases"] if case["stratum"] == "syntax"]
    families: dict[str, tuple[list[dict[str, Any]], Callable[[set[str]], bool]]] = {
        "inflection names": (
            inflection,
            lambda tags: bool({"name", "surname"} & tags),
        ),
        "inflection agreement": (inflection, lambda tags: "agreement" in tags),
        "inflection government": (inflection, lambda tags: "government" in tags),
        "syntax government": (syntax, lambda tags: "government" in tags),
        "syntax reflexivity": (syntax, lambda tags: "reflexivity" in tags),
        "syntax correlative": (syntax, lambda tags: "correlative" in tags),
        "syntax subordinate": (
            syntax,
            lambda tags: bool({"subordinate_clause", "relative_clause"} & tags),
        ),
    }

    for label, (cases, predicate) in families.items():
        splits = {case["split"] for case in cases if predicate(set(case["tags"]))}
        assert splits == {"development", "holdout"}, label


def test_punctuation_and_negative_families_span_both_splits() -> None:
    raw = _raw_corpus()
    punctuation = [case for case in raw["cases"] if case["stratum"] == "punctuation"]
    for tag in (
        "subordinate_clause",
        "interrogative_clause",
        "participial_clause",
        "vocative",
        "enumeration",
        "quotation",
        "discourse_marker",
        "parenthetical",
        "coordination",
    ):
        assert {case["split"] for case in punctuation if tag in case["tags"]} == {
            "development",
            "holdout",
        }, tag

    negatives = [case for case in raw["cases"] if case["stratum"] == "hard_negative"]
    for phenomenon in (
        "correct_name_inflection",
        "correct_surname_inflection",
        "indeclinable_name",
        "marked_word_order",
        "quotation_punctuation",
        "list_punctuation",
        "url_or_number",
        "paragraph_boundary",
    ):
        assert {
            case["split"]
            for case in negatives
            if case["protected_phenomenon"] == phenomenon
        } == {"development", "holdout"}, phenomenon


def test_json_and_xml_have_identical_validated_semantics() -> None:
    json_corpus = load_correction_corpus_json(JSON_CORPUS)
    xml_corpus = load_correction_corpus_xml(XML_CORPUS)

    assert json_corpus == xml_corpus


def test_validator_rejects_duplicate_text_and_cross_split_template_leakage() -> None:
    raw = _raw_corpus()
    first = raw["cases"][0]
    other_split = next(
        case
        for case in raw["cases"]
        if case["stratum"] == first["stratum"] and case["split"] != first["split"]
    )
    other_split["input"] = first["input"]
    other_split["expected_output"] = first["expected_output"]
    other_split["normalized_template"] = first["normalized_template"]
    other_split["entity_ids"] = first["entity_ids"]
    other_split["entity_spans"] = copy.deepcopy(first["entity_spans"])
    other_split["edits"] = copy.deepcopy(first["edits"])

    with pytest.raises(ValueError, match="duplicate input|template leakage"):
        validate_correction_corpus(raw)


def test_validator_rejects_near_identical_cross_split_template_family() -> None:
    raw = _raw_corpus()
    development = max(
        (
            case
            for case in raw["cases"]
            if case["split"] == "development" and not case["entity_spans"]
        ),
        key=lambda case: len(case["input"].split()),
    )
    holdout = next(
        case
        for case in raw["cases"]
        if case["split"] == "holdout"
        and case["stratum"] == development["stratum"]
        and not case["entity_spans"]
    )
    holdout.update(
        {
            "input": development["input"] + " Dziś.",
            "expected_output": development["expected_output"] + " Dziś.",
            "normalized_template": development["normalized_template"] + " dziś.",
            "entity_ids": [],
            "entity_spans": [],
            "tags": copy.deepcopy(development["tags"]),
            "edits": copy.deepcopy(development["edits"]),
        }
    )

    with pytest.raises(ValueError, match="near-identical template"):
        validate_correction_corpus(raw)


def test_validator_rejects_arbitrary_normalized_template_marker() -> None:
    raw = _raw_corpus()
    raw["cases"][0]["normalized_template"] = "unrelated arbitrary marker"

    with pytest.raises(ValueError, match="derived normalized_template"):
        validate_correction_corpus(raw)


def test_validator_rejects_unrelated_entity_identifier() -> None:
    raw = _raw_corpus()
    case = next(case for case in raw["cases"] if case["entity_ids"])
    case["entity_ids"] = ["unrelated_marker"]

    with pytest.raises(ValueError, match="derived entity_ids"):
        validate_correction_corpus(raw)


def test_validator_rejects_duplicate_template_inside_one_split() -> None:
    raw = _raw_corpus()
    duplicate = raw["cases"][1]
    source = "Rozmawiałem z Adamem Lis po długiej przerwie."
    start = source.index("Lis")
    entity_start = source.index("Adamem Lis")
    duplicate.update(
        {
            "input": source,
            "expected_output": "Rozmawiałem z Adamem Lisem po długiej przerwie.",
            "normalized_template": "rozmawiałem z <entity> po długiej przerwie.",
            "entity_ids": ["adamem_lis"],
            "entity_spans": [
                {
                    "start": entity_start,
                    "end": entity_start + len("Adamem Lis"),
                    "surface": "Adamem Lis",
                }
            ],
            "tags": ["inflection", "case", "name", "surname"],
            "edits": [
                {
                    "category": "inflection",
                    "start": start,
                    "end": start + len("Lis"),
                    "original": "Lis",
                    "suggestion": "Lisem",
                    "rationale": "Adversarial duplicate template.",
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="duplicate normalized template"):
        validate_correction_corpus(raw)


def test_validator_rejects_near_template_inside_one_split() -> None:
    raw = _raw_corpus()
    candidates = [
        case
        for case in raw["cases"]
        if case["split"] == "development" and not case["entity_ids"]
    ]
    source = max(candidates, key=lambda case: len(case["input"].split()))
    target = next(
        case
        for case in candidates
        if case["id"] != source["id"] and case["stratum"] == source["stratum"]
    )
    target.update(
        {
            "input": source["input"] + " Dziś.",
            "expected_output": source["expected_output"] + " Dziś.",
            "normalized_template": source["normalized_template"] + " dziś.",
            "entity_ids": [],
            "tags": copy.deepcopy(source["tags"]),
            "edits": copy.deepcopy(source["edits"]),
        }
    )

    with pytest.raises(ValueError, match="near-identical template"):
        validate_correction_corpus(raw)


def test_validator_rejects_short_sibling_template_family() -> None:
    raw = _raw_corpus()
    sibling = next(case for case in raw["cases"] if case["id"] == "punctuation_002")
    source = "Sądzę że jutro wrócisz."
    comma = source.index(" że")
    sibling.update(
        {
            "input": source,
            "expected_output": "Sądzę, że jutro wrócisz.",
            "normalized_template": source.casefold(),
            "entity_ids": [],
            "entity_spans": [],
            "tags": ["punctuation", "subordinate_clause"],
            "edits": [
                {
                    "category": "punctuation",
                    "start": comma,
                    "end": comma,
                    "original": "",
                    "suggestion": ",",
                    "rationale": "Adversarial short sibling template.",
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="near-identical template"):
        validate_correction_corpus(raw)


def test_validator_rejects_sentence_initial_common_noun_as_entity() -> None:
    raw = _raw_corpus()
    case = next(case for case in raw["cases"] if case["id"] == "inflection_037")
    surface = "Dzieci"
    case["entity_ids"] = ["dzieci"]
    case["entity_spans"] = [{"start": 0, "end": len(surface), "surface": surface}]
    case["normalized_template"] = "<entity> była spokojne."

    with pytest.raises(ValueError, match="controlled entity policy"):
        validate_correction_corpus(raw)


def test_validator_rejects_entity_combination_shared_between_splits() -> None:
    raw = _raw_corpus()
    development = next(
        case
        for case in raw["cases"]
        if case["split"] == "development"
        and case["stratum"] == "hard_negative"
        and len(case["entity_spans"]) == 1
    )
    holdout = next(
        case
        for case in raw["cases"]
        if case["split"] == "holdout"
        and case["stratum"] == "hard_negative"
        and len(case["entity_spans"]) == 1
    )
    source_span = development["entity_spans"][0]
    target_span = holdout["entity_spans"][0]
    new_input = (
        holdout["input"][: target_span["start"]]
        + source_span["surface"]
        + holdout["input"][target_span["end"] :]
    )
    holdout["input"] = new_input
    holdout["expected_output"] = new_input
    holdout["entity_ids"] = copy.deepcopy(development["entity_ids"])
    holdout["entity_spans"] = [
        {
            "start": target_span["start"],
            "end": target_span["start"] + len(source_span["surface"]),
            "surface": source_span["surface"],
        }
    ]

    with pytest.raises(ValueError, match="entity combination leakage"):
        validate_correction_corpus(raw)


def test_inflected_surfaces_of_same_person_share_one_leakage_identity() -> None:
    raw = _raw_corpus()
    holdout = next(case for case in raw["cases"] if case["id"] == "hard_negative_004")
    source = "W bibliotece spotkałem Annę Kowalską."
    surface = "Annę Kowalską"
    start = source.index(surface)
    holdout.update(
        {
            "input": source,
            "expected_output": source,
            "normalized_template": "w bibliotece spotkałem <entity>.",
            "entity_ids": ["anna_kowalska"],
            "entity_spans": [
                {
                    "start": start,
                    "end": start + len(surface),
                    "surface": surface,
                }
            ],
        }
    )

    with pytest.raises(ValueError, match="entity combination leakage"):
        validate_correction_corpus(raw)


def test_validator_rejects_overlapping_or_wrong_unicode_edits() -> None:
    raw = _raw_corpus()
    positive = next(case for case in raw["cases"] if case["edits"])
    positive["edits"].append(copy.deepcopy(positive["edits"][0]))

    with pytest.raises(ValueError, match="overlapping|duplicate insertion"):
        validate_correction_corpus(raw)

    raw = _raw_corpus()
    positive = next(case for case in raw["cases"] if case["edits"])
    positive["edits"][0]["original"] = "wrong fragment"
    with pytest.raises(ValueError, match="does not match input range"):
        validate_correction_corpus(raw)


def test_unapproved_candidates_cannot_be_selected_for_any_protected_use() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)

    for purpose in ("benchmark", "quality_gate", "training"):
        with pytest.raises(CorpusUsageError, match="pending-human-review|training"):
            select_cases_for_purpose(corpus, purpose=purpose)


def test_human_review_date_must_be_iso_8601() -> None:
    raw = _raw_corpus()
    raw["cases"][0]["review"] = {
        "status": "human-reviewed",
        "reviewer": "Paweł Cyroń",
        "reviewed_at": "21-07-2026",
        "checklist_version": "corpus-v3-review-v1",
    }

    with pytest.raises(ValueError, match="ISO-8601"):
        validate_correction_corpus(raw)


def test_unfrozen_benchmark_exposes_only_approved_development_cases() -> None:
    raw = _raw_corpus()
    _approve_all(raw)
    corpus = validate_correction_corpus(raw)

    selected = select_cases_for_purpose(corpus, purpose="benchmark")

    assert len(selected) == 80
    assert {case.split for case in selected} == {"development"}


def test_holdout_is_exposed_only_by_explicit_frozen_quality_gate() -> None:
    raw = _raw_corpus()
    _approve_all(raw)
    raw["holdout_state"] = "frozen"
    corpus = validate_correction_corpus(raw)

    benchmark = select_cases_for_purpose(corpus, purpose="benchmark")
    quality_gate = select_cases_for_purpose(corpus, purpose="quality_gate")

    assert len(benchmark) == 80
    assert {case.split for case in benchmark} == {"development"}
    assert len(quality_gate) == 160
    assert {case.split for case in quality_gate} == {"holdout"}


def test_real_model_benchmark_defaults_to_v3_and_rejects_pending_candidates() -> None:
    assert DEFAULT_CORPUS_PATH == Path(
        "tests/fixtures/evaluation/polish_correction_corpus_v3.json"
    )
    with pytest.raises(CorpusUsageError, match="pending-human-review"):
        load_benchmark_cases(JSON_CORPUS)


def test_benchmark_rejects_pending_corpus_before_runtime_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_client(**_kwargs: object) -> object:
        raise AssertionError("runtime client must not be constructed")

    monkeypatch.setattr(benchmark_runner, "_build_client", unexpected_client)

    with pytest.raises(CorpusUsageError, match="pending-human-review"):
        benchmark_runner.main(["--model", "local-test", "--corpus", str(JSON_CORPUS)])


def test_training_isolation_rejects_text_template_and_entity_leakage() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)
    holdout = next(
        case
        for case in corpus.cases
        if case.split == "holdout" and len(case.entity_spans) == 1
    )
    span = holdout.entity_spans[0]
    replacement = "Adam Lis"
    template_input = (
        holdout.input[: span.start] + replacement + holdout.input[span.end :]
    )
    template_span = EntitySpan(
        start=span.start,
        end=span.start + len(replacement),
        surface=replacement,
    )
    entity_input = f"W osobnym dokumencie wymieniono {span.surface}."
    entity_start = entity_input.index(span.surface)
    entity_span = EntitySpan(
        start=entity_start,
        end=entity_start + len(span.surface),
        surface=span.surface,
    )

    leaks = (
        IsolationRecord("training_text", holdout.input, holdout.entity_spans),
        IsolationRecord("training_template", template_input, (template_span,)),
        IsolationRecord("training_entities", entity_input, (entity_span,)),
    )
    for record in leaks:
        with pytest.raises(CorpusUsageError, match="training leakage"):
            assert_no_training_leakage(corpus, (record,))


def test_training_isolation_rejects_detectable_entity_when_spans_are_omitted() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)
    record = IsolationRecord(
        "training_omitted_span",
        "W osobnym dokumencie wymieniono Annę Kowalską.",
        (),
    )

    with pytest.raises(CorpusUsageError, match="complete entity span evidence"):
        assert_no_training_leakage(corpus, (record,))


def test_training_isolation_rejects_case_variant_of_holdout_entity() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)
    source = "W osobnym dokumencie wymieniono PAWŁA WIŚNIEWSKIEGO."
    surface = "PAWŁA WIŚNIEWSKIEGO"
    start = source.index(surface)
    record = IsolationRecord(
        "training_case_variant",
        source,
        (EntitySpan(start, start + len(surface), surface),),
    )

    with pytest.raises(CorpusUsageError, match="entity combination"):
        assert_no_training_leakage(corpus, (record,))


@pytest.mark.parametrize(
    ("source", "surface"),
    (
        ("W osobnym dokumencie wspomniano Agnieszkę.", "Agnieszkę"),
        ("Rozmawiałem z Janem Nowakiem.", "Janem Nowakiem"),
        ("W raporcie wymieniono Łukasza Kaczmarka.", "Łukasza Kaczmarka"),
    ),
)
def test_training_isolation_rejects_corrected_inflection_of_evaluation_name(
    source: str, surface: str
) -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)
    start = source.index(surface)
    record = IsolationRecord(
        "training_corrected_inflection",
        source,
        (EntitySpan(start, start + len(surface), surface),),
    )

    with pytest.raises(CorpusUsageError, match="entity combination"):
        assert_no_training_leakage(corpus, (record,))


@pytest.mark.parametrize(
    ("source", "surface"),
    (
        ("W notatce wspomniano Alicji Dudek.", "Alicji Dudek"),
        ("Do protokołu wpisano Natalię Zając.", "Natalię Zając"),
        ("Na spotkanie zaproszono Katarzynę Wróbel.", "Katarzynę Wróbel"),
    ),
)
def test_training_isolation_uses_expected_holdout_entity_aliases(
    source: str, surface: str
) -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)
    start = source.index(surface)
    record = IsolationRecord(
        "training_expected_alias",
        source,
        (EntitySpan(start, start + len(surface), surface),),
    )

    with pytest.raises(CorpusUsageError, match="entity combination"):
        assert_no_training_leakage(corpus, (record,))


def test_training_isolation_rejects_unseen_name_in_holdout_template() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)
    source = "Powiedz Marii prawdę."
    surface = "Marii"
    start = source.index(surface)
    record = IsolationRecord(
        "training_unseen_name_template",
        source,
        (EntitySpan(start, start + len(surface), surface),),
    )

    with pytest.raises(CorpusUsageError, match="template"):
        assert_no_training_leakage(corpus, (record,))


def test_training_entity_identity_is_independent_of_span_grouping() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)
    source = "Trasa obejmuje Gdańsk Toruń oraz Poznań."
    first_surface = "Gdańsk Toruń"
    second_surface = "Poznań"
    first_start = source.index(first_surface)
    second_start = source.index(second_surface)
    record = IsolationRecord(
        "training_grouped_entities",
        source,
        (
            EntitySpan(
                first_start,
                first_start + len(first_surface),
                first_surface,
            ),
            EntitySpan(
                second_start,
                second_start + len(second_surface),
                second_surface,
            ),
        ),
    )

    with pytest.raises(CorpusUsageError, match="entity combination"):
        assert_no_training_leakage(corpus, (record,))


@pytest.mark.parametrize(
    "source",
    (
        "Wymieniono ANNĘ KOWALSKĄ.",
        "Rozmawiałem z Janem Nowakiem.",
        "Rozmawiałem z Adamem Lisem.",
    ),
)
def test_training_isolation_rejects_omitted_name_shaped_span(source: str) -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)
    record = IsolationRecord(
        "training_omitted_unlisted_name",
        source,
        (),
    )

    with pytest.raises(CorpusUsageError, match="complete entity span evidence"):
        assert_no_training_leakage(corpus, (record,))


def test_training_isolation_accepts_ordinary_sentence_without_names() -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)
    record = IsolationRecord(
        "training_ordinary_sentence",
        "Dzieci spokojnie bawiły się na podwórku.",
        (),
    )

    assert_no_training_leakage(corpus, (record,))


@pytest.mark.parametrize(
    "source",
    (
        "Maria przyszła punktualnie.",
        "MARIA przyszła punktualnie.",
        "maria przyszła punktualnie.",
    ),
)
def test_training_isolation_requires_sentence_initial_known_holdout_name(
    source: str,
) -> None:
    corpus = load_correction_corpus_json(JSON_CORPUS)
    record = IsolationRecord(
        "training_omitted_initial_known_name",
        source,
        (),
    )

    with pytest.raises(CorpusUsageError, match="complete entity span evidence"):
        assert_no_training_leakage(corpus, (record,))


def test_v2_rule_e2e_fixture_remains_separate_from_v3_candidates() -> None:
    legacy = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.json"
    raw = json.loads(legacy.read_text(encoding="utf-8"))

    assert raw["schema_version"] == 2
    assert any(case["verification"] == "rules" for case in raw["cases"])
    assert JSON_CORPUS.parent != legacy.parent


def test_xml_loader_rejects_unknown_attributes_and_nodes(tmp_path: Path) -> None:
    tree = ET.parse(XML_CORPUS)
    tree.getroot().set("unexpected", "value")
    invalid_attribute = tmp_path / "unknown-attribute.xml"
    tree.write(invalid_attribute, encoding="utf-8", xml_declaration=True)

    with pytest.raises(ValueError, match="unknown XML attribute"):
        load_correction_corpus_xml(invalid_attribute)

    tree = ET.parse(XML_CORPUS)
    ET.SubElement(tree.getroot(), "unexpected")
    invalid_node = tmp_path / "unknown-node.xml"
    tree.write(invalid_node, encoding="utf-8", xml_declaration=True)

    with pytest.raises(ValueError, match="unknown XML node"):
        load_correction_corpus_xml(invalid_node)


def test_xml_loader_rejects_non_whitespace_container_text(tmp_path: Path) -> None:
    tree = ET.parse(XML_CORPUS)
    review = tree.getroot().find("./cases/case/review")
    assert review is not None
    review.text = "unexpected text"
    invalid_text = tmp_path / "unexpected-text.xml"
    tree.write(invalid_text, encoding="utf-8", xml_declaration=True)

    with pytest.raises(ValueError, match="unexpected XML text"):
        load_correction_corpus_xml(invalid_text)


def test_review_and_change_control_documentation_is_complete() -> None:
    guide = GUIDE.read_text(encoding="utf-8")
    checklist = CHECKLIST.read_text(encoding="utf-8")

    for required in (
        "pending-human-review",
        "development",
        "holdout",
        "unfrozen",
        "training",
        "leakage",
        "CC0-1.0",
        "change control",
    ):
        assert required.casefold() in guide.casefold()
    for required in (
        "correctness",
        "category",
        "minimality",
        "offsets",
        "proper-name",
        "provenance",
        "licensing",
        "Paweł Cyroń",
    ):
        assert required.casefold() in checklist.casefold()
