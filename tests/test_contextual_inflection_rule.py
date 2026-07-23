from __future__ import annotations

import copy
from collections.abc import Mapping
from pathlib import Path

import pytest
from experiments.sentence_safety_gate.gate import load_development_sentences

from polis import Analyzer, AnalyzerConfig, Category
from polis.rules.contextual_inflection import (
    stable_context_candidate_id,
)


class FakeContextTransport:
    def __init__(self, responses: list[Mapping[str, object] | Exception]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, tuple[tuple[int, int], ...], float]] = []

    def synthesize_context(
        self,
        text: str,
        *,
        spans: tuple[tuple[int, int], ...],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        self.calls.append((text, spans, timeout_seconds))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _candidate(
    *,
    start: int,
    end: int,
    lemma: str,
    form: str,
    features: tuple[str, ...],
    tags: tuple[str, ...],
) -> dict[str, object]:
    return {
        "candidate_id": stable_context_candidate_id(
            start, end, lemma, form, features, tags
        ),
        "start": start,
        "end": end,
        "lemma": lemma,
        "form": form,
        "features": list(features),
        "tags": list(tags),
    }


def _name_response() -> dict[str, object]:
    return {
        "operation": "synthesize_context",
        "language": "pl-PL",
        "results": [
            {
                "start": 14,
                "end": 19,
                "surface": "Janem",
                "unsupported_reason": None,
                "candidates": [
                    _candidate(
                        start=14,
                        end=19,
                        lemma="Jan",
                        form="Jan",
                        features=("m1", "nom", "sg", "subst"),
                        tags=("subst:sg:nom:m1",),
                    ),
                    _candidate(
                        start=14,
                        end=19,
                        lemma="Jan",
                        form="Janem",
                        features=("inst", "m1", "sg", "subst"),
                        tags=("subst:sg:inst:m1",),
                    ),
                ],
            },
            {
                "start": 20,
                "end": 25,
                "surface": "Nowak",
                "unsupported_reason": None,
                "candidates": [
                    _candidate(
                        start=20,
                        end=25,
                        lemma="Nowak",
                        form="Nowak",
                        features=("m1", "nom", "sg", "subst"),
                        tags=("subst:sg:nom:m1",),
                    ),
                    _candidate(
                        start=20,
                        end=25,
                        lemma="Nowak",
                        form="Nowakiem",
                        features=("inst", "m1", "sg", "subst"),
                        tags=("subst:sg:inst:m1",),
                    ),
                ],
            },
        ],
    }


def _nominal_agreement_response(
    *,
    target_start: int,
    target_end: int,
    target_lemma: str,
    target_surface: str,
    target_features: tuple[str, ...],
    target_tag: str,
    suggestion: str,
    suggestion_tag: str,
    noun_start: int,
    noun_end: int,
    noun_lemma: str,
    noun_surface: str,
) -> dict[str, object]:
    return {
        "operation": "synthesize_context",
        "language": "pl-PL",
        "results": [
            {
                "start": target_start,
                "end": target_end,
                "surface": target_surface,
                "unsupported_reason": None,
                "candidates": [
                    _candidate(
                        start=target_start,
                        end=target_end,
                        lemma=target_lemma,
                        form=target_surface,
                        features=target_features,
                        tags=(target_tag,),
                    ),
                    _candidate(
                        start=target_start,
                        end=target_end,
                        lemma=target_lemma,
                        form=suggestion,
                        features=("acc", "adj", "f", "pos", "sg"),
                        tags=(suggestion_tag,),
                    ),
                ],
            },
            {
                "start": noun_start,
                "end": noun_end,
                "surface": noun_surface,
                "unsupported_reason": None,
                "candidates": [
                    _candidate(
                        start=noun_start,
                        end=noun_end,
                        lemma=noun_lemma,
                        form=noun_surface,
                        features=("acc", "f", "sg", "subst"),
                        tags=("subst:sg:acc:f",),
                    ),
                ],
            },
        ],
    }


@pytest.mark.parametrize(
    (
        "source",
        "response",
        "expected_span",
        "expected_original",
        "expected_suggestion",
        "expected_text",
    ),
    [
        (
            "Widzę ten książkę.",
            _nominal_agreement_response(
                target_start=6,
                target_end=9,
                target_lemma="ten",
                target_surface="ten",
                target_features=("acc", "adj", "m3", "pos", "sg"),
                target_tag="adj:sg:acc:m3:pos",
                suggestion="tę",
                suggestion_tag="adj:sg:acc:f:pos",
                noun_start=10,
                noun_end=17,
                noun_lemma="książka",
                noun_surface="książkę",
            ),
            (7, 9),
            "en",
            "ę",
            "Widzę tę książkę.",
        ),
        (
            "Widzę ciężki skrzynię.",
            _nominal_agreement_response(
                target_start=6,
                target_end=12,
                target_lemma="ciężki",
                target_surface="ciężki",
                target_features=("adj", "m1", "nom", "pos", "sg"),
                target_tag="adj:sg:nom:m1:pos",
                suggestion="ciężką",
                suggestion_tag="adj:sg:acc:f:pos",
                noun_start=13,
                noun_end=21,
                noun_lemma="skrzynia",
                noun_surface="skrzynię",
            ),
            (11, 12),
            "i",
            "ą",
            "Widzę ciężką skrzynię.",
        ),
    ],
)
def test_analyzer_emits_reviewable_feminine_accusative_agreement(
    source: str,
    response: dict[str, object],
    expected_span: tuple[int, int],
    expected_original: str,
    expected_suggestion: str,
    expected_text: str,
) -> None:
    transport = FakeContextTransport([response, copy.deepcopy(response)])
    analyzer = Analyzer(AnalyzerConfig(), contextual_inflection_transport=transport)

    analysis = analyzer.analyze(source)
    correction = analyzer.correct(source)

    finding = next(
        item
        for item in analysis.issues
        if str(item.source) == "rule:languagetool.contextual_inflection"
    )
    assert (finding.start, finding.end) == expected_span
    assert (finding.original, finding.suggestion) == (
        expected_original,
        expected_suggestion,
    )
    assert correction.corrected_text == source
    assert correction.applied_findings == ()
    reviewable = tuple(
        item
        for item in correction.skipped_findings
        if str(item.source) == "rule:languagetool.contextual_inflection"
    )
    assert len(reviewable) == 1
    assert correction.apply_suggestions((reviewable[0].id,)) == expected_text


def test_analyzer_emits_reviewable_contextual_inflection_suggestion() -> None:
    transport = FakeContextTransport([_name_response(), _name_response()])
    analyzer = Analyzer(AnalyzerConfig(), contextual_inflection_transport=transport)
    source = "Rozmawiałem z Janem Nowak po przerwie."

    analysis = analyzer.analyze(source)
    correction = analyzer.correct(source)

    finding = next(
        item for item in analysis.issues if item.category is Category.INFLECTION
    )
    assert (finding.start, finding.end, finding.original, finding.suggestion) == (
        20,
        25,
        "Nowak",
        "Nowakiem",
    )
    assert str(finding.source) == "rule:languagetool.contextual_inflection"
    assert transport.calls[0] == (source, ((14, 19), (20, 25)), 1.0)
    assert correction.corrected_text == source
    assert correction.applied_findings == ()
    assert len(correction.skipped_findings) == 1
    assert correction.apply_suggestions((correction.skipped_findings[0].id,)) == (
        "Rozmawiałem z Janem Nowakiem po przerwie."
    )


def test_contextual_inflection_transport_failure_is_fail_closed() -> None:
    transport = FakeContextTransport([OSError("unavailable")])
    analyzer = Analyzer(AnalyzerConfig(), contextual_inflection_transport=transport)

    result = analyzer.analyze("Rozmawiałem z Janem Nowak po przerwie.")

    assert all(item.category is not Category.INFLECTION for item in result.issues)


def test_contextual_inflection_rejects_tampered_candidate_identity() -> None:
    response = copy.deepcopy(_name_response())
    results = response["results"]
    assert isinstance(results, list)
    first_result = results[0]
    assert isinstance(first_result, dict)
    candidates = first_result["candidates"]
    assert isinstance(candidates, list)
    first_candidate = candidates[0]
    assert isinstance(first_candidate, dict)
    first_candidate["candidate_id"] = "ltpl:tampered"
    transport = FakeContextTransport([response])
    analyzer = Analyzer(AnalyzerConfig(), contextual_inflection_transport=transport)

    result = analyzer.analyze("Rozmawiałem z Janem Nowak po przerwie.")

    assert all(item.category is not Category.INFLECTION for item in result.issues)


def test_contextual_inflection_is_not_called_without_source_evidence() -> None:
    transport = FakeContextTransport([])
    analyzer = Analyzer(AnalyzerConfig(), contextual_inflection_transport=transport)

    sources = (
        "To zdanie jest poprawne.",
        "Wersja 2.0 działa poprawnie.",
        "Opis jest na https://example.org.",
        "Powiedziała: „To jest poprawne”.",
    )
    results = tuple(analyzer.analyze(source) for source in sources)

    assert all(
        item.category is not Category.INFLECTION
        for result in results
        for item in result.issues
    )
    assert transport.calls == []


def test_contextual_inflection_is_not_called_for_multiple_sentences() -> None:
    transport = FakeContextTransport([])
    analyzer = Analyzer(AnalyzerConfig(), contextual_inflection_transport=transport)

    result = analyzer.analyze(
        "Rozmawiałem z Janem Nowak po przerwie. Potem wróciliśmy do domu."
    )

    assert all(item.category is not Category.INFLECTION for item in result.issues)
    assert transport.calls == []


@pytest.mark.parametrize(
    "source",
    [
        "Widzę tę książkę.",
        "Widzę ten raport.",
    ],
)
def test_nominal_agreement_requires_mismatch_surface_evidence(source: str) -> None:
    transport = FakeContextTransport([])
    analyzer = Analyzer(AnalyzerConfig(), contextual_inflection_transport=transport)

    result = analyzer.analyze(source)

    assert all(item.category is not Category.INFLECTION for item in result.issues)
    assert transport.calls == []


def test_nominal_agreement_abstains_when_morphology_is_ambiguous() -> None:
    response = _nominal_agreement_response(
        target_start=6,
        target_end=12,
        target_lemma="ciężki",
        target_surface="ciężki",
        target_features=("adj", "m1", "nom", "pos", "sg"),
        target_tag="adj:sg:nom:m1:pos",
        suggestion="ciężką",
        suggestion_tag="adj:sg:acc:f:pos",
        noun_start=13,
        noun_end=21,
        noun_lemma="skrzynia",
        noun_surface="skrzynię",
    )
    results = response["results"]
    assert isinstance(results, list)
    target = results[0]
    assert isinstance(target, dict)
    candidates = target["candidates"]
    assert isinstance(candidates, list)
    candidates.append(
        _candidate(
            start=6,
            end=12,
            lemma="ciężki",
            form="ciężkę",
            features=("acc", "adj", "f", "pos", "sg"),
            tags=("adj:sg:acc:f:pos",),
        )
    )
    transport = FakeContextTransport([response])
    analyzer = Analyzer(AnalyzerConfig(), contextual_inflection_transport=transport)

    result = analyzer.analyze("Widzę ciężki skrzynię.")

    assert all(item.category is not Category.INFLECTION for item in result.issues)
    assert len(transport.calls) == 1


def test_contextual_inflection_abstains_on_protected_development_cases() -> None:
    cases = load_development_sentences(
        Path("tests/fixtures/evaluation/polish_correction_safety_corpus_v1.xml")
    )
    protected = tuple(case for case in cases if case.protected_negative)
    transport = FakeContextTransport([])
    analyzer = Analyzer(AnalyzerConfig(), contextual_inflection_transport=transport)

    results = tuple(analyzer.analyze(case.source) for case in protected)

    assert len(protected) == 20
    assert all(
        str(finding.source) != "rule:languagetool.contextual_inflection"
        for result in results
        for finding in result.issues
    )
    assert transport.calls == []
