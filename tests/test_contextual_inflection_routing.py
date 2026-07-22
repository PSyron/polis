from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest
from experiments.contextual_inflection_routing.experiment import (
    ContextCandidate,
    ContextSpanResult,
    ContextualProposal,
    EvidenceKind,
    RoutingInput,
    detect_evidence,
    rank_evidence,
    stable_context_candidate_id,
    validate_context_response,
)
from experiments.contextual_inflection_routing.run_benchmark import (
    CaseObservation,
    GoldEdit,
    freeze_router,
    reserve_holdout_once,
    score_observations,
    validate_privacy_safe_report,
)

from polis.llm import TextEdit


def _result(
    source: str,
    start: int,
    end: int,
    forms: tuple[tuple[str, tuple[str, ...]], ...],
) -> ContextSpanResult:
    candidates = tuple(
        ContextCandidate(
            candidate_id=f"ltpl:{index:064x}",
            start=start,
            end=end,
            lemma=None,
            form=form,
            features=features,
            tags=(":".join(features),),
        )
        for index, (form, features) in enumerate(forms, start=1)
    )
    return ContextSpanResult(
        start=start,
        end=end,
        surface=source[start:end],
        unsupported_reason=None,
        candidates=candidates,
    )


def test_routing_input_contains_source_text_only() -> None:
    assert {field.name for field in fields(RoutingInput)} == {"source"}


def test_detector_finds_adjacent_name_and_closed_government_patterns() -> None:
    name_source = "Rozmawiałem z Janem Nowak po przerwie."
    name_evidence = detect_evidence(RoutingInput(name_source))
    government_source = "Wróciła bez ciepła kurtka."
    government_evidence = detect_evidence(RoutingInput(government_source))

    surname = next(item for item in name_evidence if item.kind == "surname_agreement")
    assert surname.spans == ((14, 19), (20, 25))
    assert surname.target_class == "surname"
    assert surname.desired_case is None
    government = next(
        item for item in government_evidence if item.kind == "bez_government"
    )
    assert government.spans == ((12, 18), (19, 25))
    assert government.target_class == "ordinary"
    assert government.desired_case == "gen"


def test_ranker_selects_unique_surname_form_from_reference_features() -> None:
    source = "Rozmawiałem z Janem Nowak."
    evidence = next(
        item
        for item in detect_evidence(RoutingInput(source))
        if item.kind == "surname_agreement"
    )
    results = (
        _result(
            source,
            14,
            19,
            (
                ("Jan", ("m1", "nom", "sg", "subst")),
                ("Janem", ("inst", "m1", "sg", "subst")),
            ),
        ),
        _result(
            source,
            20,
            25,
            (
                ("Nowak", ("m1", "nom", "sg", "subst")),
                ("Nowakiem", ("inst", "m1", "sg", "subst")),
                ("Nowakowi", ("dat", "m1", "sg", "subst")),
            ),
        ),
    )

    proposals = rank_evidence(source, evidence, results)

    assert len(proposals) == 1
    assert (proposals[0].start, proposals[0].end) == (20, 25)
    assert proposals[0].original == "Nowak"
    assert proposals[0].suggestion == "Nowakiem"
    assert proposals[0].candidate_id.startswith("ltpl:")


def test_ranker_inflects_adjective_and_noun_but_abstains_when_already_correct() -> None:
    source = "Wróciła bez ciepła kurtka."
    evidence = next(
        item
        for item in detect_evidence(RoutingInput(source))
        if item.kind == "bez_government"
    )
    results = (
        _result(
            source,
            12,
            18,
            (
                ("ciepła", ("adj", "f", "nom.voc", "pos", "sg")),
                ("ciepłej", ("adj", "f", "gen", "pos", "sg")),
                ("ciepłą", ("acc", "adj", "f", "pos", "sg")),
            ),
        ),
        _result(
            source,
            19,
            25,
            (
                ("kurtka", ("f", "nom", "sg", "subst")),
                ("kurtki", ("f", "gen", "sg", "subst")),
                ("kurtką", ("f", "inst", "sg", "subst")),
            ),
        ),
    )

    proposals = rank_evidence(source, evidence, results)

    assert [(item.original, item.suggestion) for item in proposals] == [
        ("ciepła", "ciepłej"),
        ("kurtka", "kurtki"),
    ]

    correct = "Wróciła bez ciepłej kurtki."
    correct_evidence = next(
        item
        for item in detect_evidence(RoutingInput(correct))
        if item.kind == "bez_government"
    )
    correct_results = (
        _result(
            correct,
            12,
            19,
            (("ciepłej", ("adj", "f", "gen", "pos", "sg")),),
        ),
        _result(
            correct,
            20,
            26,
            (("kurtki", ("f", "gen", "sg", "subst")),),
        ),
    )
    assert rank_evidence(correct, correct_evidence, correct_results) == ()


def test_ranker_abstains_when_two_distinct_forms_satisfy_constraints() -> None:
    source = "Jutro podziękuję Paweł."
    evidence = next(
        item
        for item in detect_evidence(RoutingInput(source))
        if item.kind == "gratitude_dative"
    )
    result = _result(
        source,
        17,
        22,
        (
            ("Paweł", ("m1", "nom", "sg", "subst")),
            ("Pawłowi", ("dat", "m1", "sg", "subst")),
            ("Pawłu", ("dat", "m1", "sg", "subst")),
        ),
    )

    assert rank_evidence(source, evidence, (result,)) == ()


def test_context_response_preserves_complete_tags_in_candidate_identity() -> None:
    source = "Paweł"
    features = ("dat", "m1", "sg", "subst")
    tags = ("subst:sg:dat:m1",)
    candidate_id = stable_context_candidate_id(0, 5, "Paweł", "Pawłowi", features, tags)
    unchanged_features = ("m1", "nom", "sg", "subst")
    unchanged_tags = ("subst:sg:nom:m1",)
    unchanged_id = stable_context_candidate_id(
        0, 5, "Paweł", "Paweł", unchanged_features, unchanged_tags
    )
    payload = {
        "operation": "synthesize_context",
        "language": "pl-PL",
        "results": [
            {
                "start": 0,
                "end": 5,
                "surface": "Paweł",
                "unsupported_reason": None,
                "candidates": [
                    {
                        "candidate_id": candidate_id,
                        "start": 0,
                        "end": 5,
                        "lemma": "Paweł",
                        "form": "Pawłowi",
                        "features": list(features),
                        "tags": list(tags),
                    },
                    {
                        "candidate_id": unchanged_id,
                        "start": 0,
                        "end": 5,
                        "lemma": "Paweł",
                        "form": "Paweł",
                        "features": list(unchanged_features),
                        "tags": list(unchanged_tags),
                    },
                ],
            }
        ],
    }

    result = validate_context_response(
        json.dumps(payload), source_text=source, requested_spans=((0, 5),)
    )

    assert result[0].candidates[0].tags == tags


def test_scorer_counts_exact_supported_word_edits_independent_of_gold_category() -> (
    None
):
    source = "Przyglądamy się nowy projekt."
    proposals = (
        _proposal(16, 20, "nowy", "nowemu", "reflexive_dative"),
        _proposal(21, 28, "projekt", "projektowi", "reflexive_dative"),
    )
    observation = CaseObservation(
        case_id="syntax_case",
        protected_negative=False,
        expected_output="Przyglądamy się nowemu projektowi.",
        source=source,
        gold_edits=(
            GoldEdit(TextEdit(16, 20, "nowy", "nowemu"), "ordinary", False),
            GoldEdit(TextEdit(21, 28, "projekt", "projektowi"), "ordinary", False),
        ),
        proposals=proposals,
        evidence_count=1,
        supported_spans=((16, 20), (21, 28)),
        elapsed_ms=2.0,
    )

    summary = score_observations((observation,), peak_rss_bytes=123)

    assert summary["true_positive_edits"] == 2
    assert summary["false_positive_edits"] == 0
    assert summary["precision"] == 1.0
    assert summary["exact_output_matches"] == 1


def test_report_privacy_and_holdout_reservation_are_fail_closed(
    tmp_path: Path,
) -> None:
    safe = {"decision": {"qualified": True}, "case_evidence": []}
    validate_privacy_safe_report(safe)
    with pytest.raises(ValueError, match="raw analyzed text"):
        validate_privacy_safe_report(
            {"decision": {"qualified": True}, "case_evidence": [{"source": "x"}]}
        )

    config = tmp_path / "config.json"
    experiment = tmp_path / "experiment.py"
    bridge = tmp_path / "Bridge.java"
    frozen = tmp_path / "frozen.json"
    marker = tmp_path / "holdout.started"
    for path, content in (
        (config, "{}\n"),
        (experiment, "# router\n"),
        (bridge, "final class Bridge {}\n"),
    ):
        path.write_text(content, encoding="utf-8")
    freeze_router(config, experiment, bridge, frozen)
    reserve_holdout_once(frozen, config, experiment, bridge, marker)
    with pytest.raises(FileExistsError, match="already reserved"):
        reserve_holdout_once(frozen, config, experiment, bridge, marker)


def _proposal(
    start: int, end: int, original: str, suggestion: str, kind: EvidenceKind
) -> ContextualProposal:
    return ContextualProposal(
        start=start,
        end=end,
        original=original,
        suggestion=suggestion,
        candidate_id=f"ltpl:{start:064x}",
        evidence_kind=kind,
        target_class="ordinary",
    )
