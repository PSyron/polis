from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence

import pytest

from polis.analysis.hybrid import (
    HybridSuggestionEngine,
    InflectionTask,
    SyntaxTask,
)
from polis.core import (
    AnalysisTimeoutError,
    BackendUnavailableError,
    Category,
    Confidence,
    Severity,
    SourceKind,
)
from polis.llm import FiniteCandidate, PromptRequest


class StaticRouter:
    def __init__(self, tasks_by_sentence: dict[str, tuple[object, ...]]) -> None:
        self.tasks_by_sentence = tasks_by_sentence

    def tasks(
        self,
        sentence: str,
        *,
        deterministic_findings: tuple[object, ...],
    ) -> tuple[object, ...]:
        del deterministic_findings
        return self.tasks_by_sentence.get(sentence, ())


class ScriptedBackend:
    name = "fake-specialist"

    def __init__(self, responses: Sequence[str | Exception]) -> None:
        self.responses = iter(responses)
        self.requests: list[PromptRequest] = []

    async def generate(self, request: PromptRequest) -> str:
        self.requests.append(request)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def _candidate_task() -> InflectionTask:
    return InflectionTask(
        candidates=(
            FiniteCandidate("ltpl:changed", 12, 17, "Kasi", "Kasia", ("gen",)),
            FiniteCandidate("ltpl:unchanged", 12, 17, "Kasią", "Kasia", ("inst",)),
        )
    )


def test_unchanged_candidate_stops_after_one_call() -> None:
    text = "Rozmawiam z Kasią."
    backend = ScriptedBackend(('{"unchanged":true}',))
    engine = HybridSuggestionEngine(
        backend=backend,
        router=StaticRouter({text: (_candidate_task(),)}),
    )

    run = asyncio.run(engine.suggest(text, deterministic_findings=()))

    assert run.status == "complete"
    assert run.suggestions == ()
    assert run.model_calls == 1
    assert [request.protocol_id for request in backend.requests] == [
        "specialist-candidate-selection"
    ]


def test_changed_candidate_requires_verifier_and_stays_a_suggestion() -> None:
    text = "Rozmawiam z Kasią."
    backend = ScriptedBackend(
        ('{"candidate_id":"ltpl:changed"}', '{"decision":"accept"}')
    )
    engine = HybridSuggestionEngine(
        backend=backend,
        router=StaticRouter({text: (_candidate_task(),)}),
        calibrated_confidence=Confidence(0.61),
    )

    run = asyncio.run(engine.suggest(text, deterministic_findings=()))

    assert run.status == "complete"
    assert run.model_calls == 2
    assert len(run.suggestions) == 1
    finding = run.suggestions[0]
    assert (finding.start, finding.end) == (12, 17)
    assert finding.original == "Kasią"
    assert finding.suggestion == "Kasi"
    assert finding.category is Category.INFLECTION
    assert finding.severity is Severity.SUGGESTION
    assert finding.source.kind is SourceKind.LLM
    assert finding.confidence == Confidence(0.61)
    assert [request.protocol_id for request in backend.requests] == [
        "specialist-candidate-selection",
        "specialist-proposal-verifier",
    ]


def test_syntax_proposal_uses_original_paragraph_offsets() -> None:
    sentence = " Wiem że wróci."
    text = "Dobrze." + sentence
    backend = ScriptedBackend(
        ('{"corrected_text":" Wiem, że wróci."}', '{"decision":"accept"}')
    )
    engine = HybridSuggestionEngine(
        backend=backend,
        router=StaticRouter({sentence: (SyntaxTask(),)}),
    )

    run = asyncio.run(engine.suggest(text, deterministic_findings=()))

    assert run.status == "complete"
    assert run.model_calls == 2
    assert len(run.suggestions) == 1
    finding = run.suggestions[0]
    expected_offset = text.index(" że")
    assert (finding.start, finding.end) == (expected_offset, expected_offset)
    assert finding.original == ""
    assert finding.suggestion == ","


def test_verifier_rejection_cannot_replace_the_proposal() -> None:
    text = "Wiem że wróci."
    backend = ScriptedBackend(
        ('{"corrected_text":"Wiem, że wróci."}', '{"decision":"reject"}')
    )
    engine = HybridSuggestionEngine(
        backend=backend,
        router=StaticRouter({text: (SyntaxTask(),)}),
    )

    run = asyncio.run(engine.suggest(text, deterministic_findings=()))

    assert run.suggestions == ()
    assert run.model_calls == 2


def test_syntax_task_rejects_changes_to_explicit_protected_names() -> None:
    text = "Anna Kowalska wróciła."
    protected = ((0, len("Anna Kowalska")),)
    backend = ScriptedBackend(('{"corrected_text":"Ania Kowalska wróciła."}',))
    engine = HybridSuggestionEngine(
        backend=backend,
        router=StaticRouter({text: (SyntaxTask(protected_spans=protected),)}),
    )

    run = asyncio.run(engine.suggest(text, deterministic_findings=()))

    assert run.status == "invalid_response"
    assert run.suggestions == ()
    assert run.model_calls == 1
    assert "Anna" not in run.safe_error


@pytest.mark.parametrize(
    ("source", "proposal"),
    [
        ("Otwórz https://example.pl teraz.", "Otwórz https://example.com teraz."),
        ("Wpisz 12 pozycji.", "Wpisz 13 pozycji."),
        ('Powiedział: "wrócę jutro".', 'Powiedział: "wrócę dziś".'),
    ],
)
def test_syntax_task_automatically_protects_urls_numbers_and_quotations(
    source: str,
    proposal: str,
) -> None:
    backend = ScriptedBackend((json.dumps({"corrected_text": proposal}),))
    engine = HybridSuggestionEngine(
        backend=backend,
        router=StaticRouter({source: (SyntaxTask(),)}),
    )

    run = asyncio.run(engine.suggest(source, deterministic_findings=()))

    assert run.status == "invalid_response"
    assert run.suggestions == ()
    assert run.model_calls == 1


def test_invalid_verifier_response_counts_both_model_calls() -> None:
    text = "Wiem że wróci."
    backend = ScriptedBackend(
        ('{"corrected_text":"Wiem, że wróci."}', '{"replacement":"inny"}')
    )
    engine = HybridSuggestionEngine(
        backend=backend,
        router=StaticRouter({text: (SyntaxTask(),)}),
    )

    run = asyncio.run(engine.suggest(text, deterministic_findings=()))

    assert run.status == "invalid_response"
    assert run.model_calls == 2
    assert len(backend.requests) == 2
    assert run.operation_versions == (
        "specialist-corrected-text/1.0",
        "specialist-proposal-verifier/1.0",
    )


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (
            BackendUnavailableError(
                "unavailable",
                code="backend.unavailable",
                retryable=True,
                context={"backend": "fake-specialist"},
            ),
            "unavailable",
        ),
        (
            AnalysisTimeoutError(
                "timeout",
                code="analysis.timeout",
                retryable=True,
                context={"backend": "fake-specialist"},
            ),
            "timed_out",
        ),
        (ValueError("raw response contained private text"), "invalid_response"),
    ],
)
def test_optional_failure_is_visible_and_privacy_safe(
    error: Exception,
    status: str,
) -> None:
    text = "Wiem że wróci."
    backend = ScriptedBackend((error,))
    engine = HybridSuggestionEngine(
        backend=backend,
        router=StaticRouter({text: (SyntaxTask(),)}),
    )

    run = asyncio.run(engine.suggest(text, deterministic_findings=()))

    assert run.status == status
    assert run.suggestions == ()
    assert run.model_calls == 1
    assert run.safe_error == "specialist suggestion operation failed"
    assert "private text" not in run.safe_error
