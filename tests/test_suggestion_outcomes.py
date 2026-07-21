from collections.abc import Callable

import pytest

from polis import Analyzer, AnalyzerConfig
from polis.core import (
    AnalysisTimeoutError,
    BackendUnavailableError,
    InvalidBackendResponseError,
)


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
