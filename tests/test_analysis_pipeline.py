from __future__ import annotations

import asyncio

import pytest

from polis.analysis.pipeline import analyze_text, analyze_text_async
from polis.core import (
    AnalysisOptions,
    AnalysisTimeoutError,
    Category,
    Confidence,
    Finding,
    InvalidBackendResponseError,
    Source,
)
from polis.core.models import Severity
from polis.rules import DeterministicRuleRegistry, RuleRegistration


class FakeRule:
    def __init__(self, source: str, findings: tuple[Finding, ...]) -> None:
        self.source = Source.parse(source)
        self.findings = findings
        self.calls: list[str] = []

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        self.calls.append(text)
        return self.findings


class DeterministicBackend:
    def __init__(
        self,
        *,
        responses: tuple[tuple[Finding, ...], ...],
    ) -> None:
        self.name = "mock"
        self._responses = list(responses)
        self.calls: list[str] = []

    async def generate_findings(
        self,
        text: str,
        *,
        policy: object | None = None,
        clock: object | None = None,
        sleep: object = asyncio.sleep,
        operation: str = "analysis.llm.generate",
    ) -> tuple[Finding, ...]:
        self.calls.append(text)
        return self._responses.pop(0)


class MalformedBackend:
    def __init__(self) -> None:
        self.name = "mock"

    async def generate_findings(
        self,
        text: str,
        *,
        policy: object | None = None,
        clock: object | None = None,
        sleep: object = asyncio.sleep,
        operation: str = "analysis.llm.generate",
    ) -> tuple[Finding, ...]:
        raise InvalidBackendResponseError(
            "backend response is malformed",
            code="backend.invalid_response",
            retryable=False,
            context={"operation": operation, "backend": self.name},
        )


class TimeoutBackend:
    def __init__(self) -> None:
        self.name = "mock"

    async def generate_findings(
        self,
        text: str,
        *,
        policy: object | None = None,
        clock: object | None = None,
        sleep: object = asyncio.sleep,
        operation: str = "analysis.llm.generate",
    ) -> tuple[Finding, ...]:
        raise AnalysisTimeoutError(
            "local generation timed out",
            code="analysis.timeout",
            retryable=True,
            context={"operation": operation, "backend": self.name},
        )


def make_finding(
    *,
    source: str,
    category: Category,
    start: int,
    end: int,
    original: str,
    suggestion: str,
) -> Finding:
    return Finding.create(
        category=category,
        severity=Severity.ERROR,
        message="test",
        explanation="test",
        original=original,
        suggestion=suggestion,
        start=start,
        end=end,
        confidence=Confidence(0.93),
        source=Source.parse(source),
    )


def test_analyze_text_merges_rules_and_llm_findings_with_offset_translation() -> None:
    deterministic = DeterministicBackend(
        responses=(
            (),
            (
                make_finding(
                    source="llm:local",
                    category=Category.PUNCTUATION,
                    start=0,
                    end=4,
                    original="Zeby",
                    suggestion="Żeby",
                ),
            ),
        )
    )
    deterministic_rule = FakeRule(
        "rule:test",
        (
            make_finding(
                source="rule:test",
                category=Category.SPELLING,
                start=0,
                end=4,
                original="To j",
                suggestion="To je",
            ),
        ),
    )
    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=deterministic_rule),),
    )

    result = analyze_text(
        "To jest.\n\nZeby",
        registry=registry,
        local_backend=deterministic,
    )

    assert len(result) == 2
    assert result[0].start == 0
    assert result[1].start == 10
    assert result[1].end == 14


def test_analyze_text_rejects_malformed_llm_response_by_default() -> None:
    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=FakeRule(
                    "rule:test",
                    (
                        make_finding(
                            source="rule:test",
                            category=Category.SYNTAX,
                            start=0,
                            end=4,
                            original="To j",
                            suggestion="To je",
                        ),
                    ),
                )
            ),
        )
    )

    with pytest.raises(InvalidBackendResponseError):
        analyze_text(
            "To jest.\n\nZeby",
            registry=registry,
            local_backend=MalformedBackend(),
        )


def test_analyze_text_rejects_timeout_backend_failure_by_default() -> None:
    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=FakeRule(
                    "rule:test",
                    (
                        make_finding(
                            source="rule:test",
                            category=Category.SYNTAX,
                            start=0,
                            end=4,
                            original="To j",
                            suggestion="To je",
                        ),
                    ),
                )
            ),
        )
    )

    with pytest.raises(AnalysisTimeoutError):
        analyze_text(
            "To jest.\n\nZeby",
            registry=registry,
            local_backend=TimeoutBackend(),
        )


def test_analyze_text_without_llm_uses_only_deterministic_findings() -> None:
    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=FakeRule(
                    "rule:test",
                    (
                        make_finding(
                            source="rule:test",
                            category=Category.PUNCTUATION,
                            start=0,
                            end=4,
                            original="To j",
                            suggestion="To je",
                        ),
                    ),
                )
            ),
        )
    )

    result = analyze_text(
        "To jest.\n\nZeby",
        registry=registry,
        local_backend=None,
    )

    assert len(result) == 1
    assert str(result[0].source) == "rule:test"


def test_analyze_text_async_strict_mode_raises() -> None:
    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=FakeRule(
                    "rule:test",
                    (),
                )
            ),
        )
    )

    with pytest.raises(InvalidBackendResponseError):
        asyncio.run(
            analyze_text_async(
                "To jest.\n\nZeby",
                registry=registry,
                local_backend=MalformedBackend(),
                ignore_backend_failures=False,
            )
        )
