from __future__ import annotations

import copy
from collections.abc import Mapping

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
