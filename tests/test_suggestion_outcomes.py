import asyncio
from collections.abc import Callable

import pytest

from polis import Analyzer, AnalyzerConfig
from polis.analysis.hybrid import HybridSuggestionEngine, SyntaxTask
from polis.core import (
    AnalysisTimeoutError,
    BackendUnavailableError,
    Confidence,
    CorrectionConflictError,
    InvalidBackendResponseError,
)
from polis.llm import PromptRequest


class UnavailableBackend:
    """Backend fixture that always reports an unavailable service."""

    name = "unavailable-test-backend"

    async def generate_findings(
        self,
        text: str,
        *,
        policy: object | None = None,
        clock: object | None = None,
        sleep: Callable[[float], object] | None = None,
        operation: str = "analysis.llm.generate",
    ) -> tuple[tuple[object, ...], ...]:
        raise BackendUnavailableError(
            "backend is unavailable",
            code="backend_unavailable",
            retryable=True,
            context={"backend": self.name},
        )


class TimeoutBackend:
    """Backend fixture that always times out."""

    name = "timeout-test-backend"

    async def generate_findings(
        self,
        text: str,
        *,
        policy: object | None = None,
        clock: object | None = None,
        sleep: Callable[[float], object] | None = None,
        operation: str = "analysis.llm.generate",
    ) -> tuple[tuple[object, ...], ...]:
        raise AnalysisTimeoutError(
            "backend timed out",
            code="analysis.timeout",
            retryable=True,
            context={"backend": self.name},
        )


class InvalidResponseBackend:
    """Backend fixture that returns an invalid response."""

    name = "invalid-response-test-backend"

    async def generate_findings(
        self,
        text: str,
        *,
        policy: object | None = None,
        clock: object | None = None,
        sleep: Callable[[float], object] | None = None,
        operation: str = "analysis.llm.generate",
    ) -> tuple[tuple[object, ...], ...]:
        raise InvalidBackendResponseError(
            "invalid backend response",
            code="backend.invalid_response",
            retryable=False,
            context={"backend": self.name},
        )


class StaticSyntaxRouter:
    def tasks(
        self,
        sentence: str,
        *,
        deterministic_findings: tuple[object, ...],
    ) -> tuple[SyntaxTask, ...]:
        del deterministic_findings
        return (SyntaxTask(),) if sentence else ()


class SpecialistBackend:
    name = "fake-specialist"

    def __init__(self, responses: tuple[str | Exception, ...]) -> None:
        self.responses = iter(responses)
        self.calls: list[PromptRequest] = []

    async def generate(self, request: PromptRequest) -> str:
        self.calls.append(request)
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def _specialist_engine(
    responses: tuple[str | Exception, ...],
    *,
    calibrated_confidence: Confidence | None = None,
) -> tuple[HybridSuggestionEngine, SpecialistBackend]:
    backend = SpecialistBackend(responses)
    return (
        HybridSuggestionEngine(
            backend=backend,
            router=StaticSyntaxRouter(),
            calibrated_confidence=calibrated_confidence or Confidence(0.0),
        ),
        backend,
    )


def test_suggestion_outcomes_present_when_backend_is_enabled_and_complete() -> None:
    analyzer = Analyzer(AnalyzerConfig(use_local_heuristic_backend=True))

    result = analyzer.correct("zeby")

    assert result.suggestion_outcomes
    assert len(result.suggestion_outcomes) == 1
    outcome = result.suggestion_outcomes[0]
    assert outcome.status == "complete"
    assert outcome.backend == "mock-heuristic"
    assert outcome.suggestions >= 1
    assert outcome.operation == "analysis.correct.suggestions"
    assert outcome.model_calls == 1
    assert outcome.source_policy_version == "1.1"


@pytest.mark.parametrize(
    ("backend", "expected_status"),
    [
        (UnavailableBackend(), "unavailable"),
        (TimeoutBackend(), "timed_out"),
        (InvalidResponseBackend(), "invalid_response"),
    ],
)
def test_suggestion_outcome_classifies_optional_backend_failures(
    backend: object, expected_status: str
) -> None:
    analyzer = Analyzer(AnalyzerConfig(use_local_heuristic_backend=True))
    analyzer._backend = backend

    result = analyzer.correct("zeby")

    assert len(result.suggestion_outcomes) == 1
    assert result.suggestion_outcomes[0].status == expected_status
    assert result.suggestion_outcomes[0].model_calls == 1


def test_specialist_suggestion_is_reviewable_and_never_auto_applied() -> None:
    engine, backend = _specialist_engine(
        ('{"corrected_text":"Wiem, że wróci."}', '{"decision":"accept"}')
    )
    analyzer = Analyzer(AnalyzerConfig(), specialist_engine=engine)

    result = analyzer.correct("Wiem że wróci.")

    assert result.corrected_text == result.original_text
    assert result.applied_findings == ()
    assert len(result.skipped_findings) == 1
    assert result.skipped_findings[0].source.name == "fake-specialist"
    assert result.skipped_findings[0].suggestion == ","
    assert len(result.suggestion_outcomes) == 1
    outcome = result.suggestion_outcomes[0]
    assert outcome.status == "complete"
    assert outcome.model_calls == 2
    assert outcome.protocol_versions == (
        "specialist-corrected-text/1.0",
        "specialist-proposal-verifier/1.0",
    )
    assert len(backend.calls) == 2
    assert result.apply_suggestions((result.skipped_findings[0].id,)) == (
        "Wiem, że wróci."
    )


def test_model_confidence_cannot_grant_automatic_correction() -> None:
    engine, _backend = _specialist_engine(
        ('{"corrected_text":"Wiem, że wróci."}', '{"decision":"accept"}'),
        calibrated_confidence=Confidence(1.0),
    )

    result = Analyzer(AnalyzerConfig(), specialist_engine=engine).correct(
        "Wiem że wróci."
    )

    assert result.corrected_text == result.original_text
    assert result.skipped_findings[0].confidence == Confidence(1.0)


def test_specialist_failure_preserves_deterministic_correction() -> None:
    failure = BackendUnavailableError(
        "unavailable",
        code="backend.unavailable",
        retryable=True,
        context={"backend": "fake-specialist"},
    )
    engine, _backend = _specialist_engine((failure,))
    analyzer = Analyzer(AnalyzerConfig(), specialist_engine=engine)

    result = analyzer.correct("Zeby")

    assert result.corrected_text == "Żeby"
    assert len(result.applied_findings) == 1
    assert result.suggestion_outcomes[0].status == "unavailable"
    assert result.suggestion_outcomes[0].model_calls == 1


def test_qualified_deterministic_finding_wins_specialist_conflict() -> None:
    engine, _backend = _specialist_engine(
        ('{"corrected_text":"Żeby jutro"}', '{"decision":"accept"}')
    )
    analyzer = Analyzer(AnalyzerConfig(), specialist_engine=engine)

    result = analyzer.correct("Zeby jutro")

    assert result.corrected_text == "Żeby jutro"
    assert len(result.applied_findings) == 1
    assert result.applied_findings[0].source.kind.value == "rule"
    assert len(result.skipped_findings) == 1
    assert result.skipped_findings[0].source.kind.value == "llm"
    with pytest.raises(CorrectionConflictError):
        result.apply_suggestions((result.skipped_findings[0].id,))


def test_sync_and_async_correction_paths_are_equivalent() -> None:
    responses = ('{"corrected_text":"Wiem, że wróci."}', '{"decision":"accept"}')
    sync_engine, _sync_backend = _specialist_engine(responses)
    async_engine, _async_backend = _specialist_engine(responses)

    sync_result = Analyzer(AnalyzerConfig(), specialist_engine=sync_engine).correct(
        "Wiem że wróci."
    )
    async_result = asyncio.run(
        Analyzer(AnalyzerConfig(), specialist_engine=async_engine).correct_async(
            "Wiem że wróci."
        )
    )

    assert async_result == sync_result


def test_sync_and_async_optional_failures_are_equivalent() -> None:
    def failure() -> BackendUnavailableError:
        return BackendUnavailableError(
            "unavailable",
            code="backend.unavailable",
            retryable=True,
            context={"backend": "fake-specialist"},
        )

    sync_engine, _sync_backend = _specialist_engine((failure(),))
    async_engine, _async_backend = _specialist_engine((failure(),))

    sync_result = Analyzer(AnalyzerConfig(), specialist_engine=sync_engine).correct(
        "Zeby"
    )
    async_result = asyncio.run(
        Analyzer(AnalyzerConfig(), specialist_engine=async_engine).correct_async("Zeby")
    )

    assert async_result == sync_result
