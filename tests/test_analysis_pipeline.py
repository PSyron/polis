from __future__ import annotations

import asyncio

from polis.analysis.pipeline import analyze_text, analyze_text_async
from polis.core import AnalysisOptions, Category, Confidence, Finding, Source
from polis.core.models import Severity
from polis.rules import DeterministicRuleRegistry, RuleRegistration


class FakeRule:
    source = Source.parse("rule:test")

    def __init__(self, findings: tuple[Finding, ...]) -> None:
        self._findings = findings
        self.calls: list[str] = []

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        self.calls.append(text)
        return self._findings


def _finding(
    *,
    category: Category = Category.SPELLING,
    confidence: float = 0.93,
) -> Finding:
    return Finding.create(
        category=category,
        severity=Severity.ERROR,
        message="Test.",
        explanation="Test deterministic pipeline.",
        original="Zeby",
        suggestion="Żeby",
        start=0,
        end=4,
        confidence=Confidence(confidence),
        source=Source.parse("rule:test"),
    )


def _registry(rule: FakeRule) -> DeterministicRuleRegistry:
    return DeterministicRuleRegistry((RuleRegistration(rule=rule),))


def test_analyze_text_uses_only_the_deterministic_registry() -> None:
    rule = FakeRule((_finding(),))

    result = analyze_text("Zeby wrócić.", registry=_registry(rule))

    assert result == rule._findings
    assert rule.calls == ["Zeby wrócić."]


def test_analyze_text_async_matches_the_sync_entry_point() -> None:
    sync_rule = FakeRule((_finding(),))
    async_rule = FakeRule((_finding(),))

    sync_result = analyze_text("Zeby wrócić.", registry=_registry(sync_rule))
    async_result = asyncio.run(
        analyze_text_async("Zeby wrócić.", registry=_registry(async_rule))
    )

    assert async_result == sync_result
    assert async_rule.calls == sync_rule.calls == ["Zeby wrócić."]


def test_analyze_text_applies_analysis_options_to_deterministic_findings() -> None:
    finding = _finding(category=Category.SPELLING, confidence=0.8)
    options = AnalysisOptions(
        categories=frozenset({Category.SPELLING}),
        minimum_confidence=0.9,
    )

    result = analyze_text(
        "Zeby wrócić.",
        registry=_registry(FakeRule((finding,))),
        options=options,
    )

    assert result == ()
