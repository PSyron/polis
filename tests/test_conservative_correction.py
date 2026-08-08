from __future__ import annotations

from typing import cast

import pytest

from polis import (
    AnalysisOptions,
    AnalysisResult,
    Analyzer,
    AnalyzerConfig,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)
from polis.core import Rule
from polis.rules import DeterministicRuleRegistry, RuleRegistration
from polis.rules.spelling import SpellingZebyRule


class _VersionedZebyRule:
    def __init__(self, *, operation: str, behavior_version: str) -> None:
        self._delegate = SpellingZebyRule()
        self.source = self._delegate.source
        self._operation = operation
        self._behavior_version = behavior_version

    @property
    def operation(self) -> str:
        return self._operation

    @property
    def behavior_version(self) -> str:
        return self._behavior_version

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return cast(tuple[Finding, ...], self._delegate.find(text, options=options))


class _UnversionedZebyRule:
    def __init__(self) -> None:
        self._delegate = SpellingZebyRule()
        self.source = self._delegate.source

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return cast(tuple[Finding, ...], self._delegate.find(text, options=options))


def _analyzer_with_rule(rule: Rule) -> Analyzer:
    analyzer = Analyzer(AnalyzerConfig())
    analyzer._registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=rule,
                categories=frozenset({Category.SPELLING}),
            ),
        )
    )
    return analyzer


def test_correct_applies_safe_rule_corrections_to_a_sentence() -> None:
    result = Analyzer(AnalyzerConfig()).correct("Zeby jutro,powiem o tym.")

    assert result.original_text == "Zeby jutro,powiem o tym."
    assert result.corrected_text == "Żeby jutro, powiem o tym."
    assert {finding.original for finding in result.applied_findings} == {"Zeby", ","}
    assert result.skipped_findings == ()
    assert result.suggestion_outcomes == ()


def test_correct_handles_a_multi_sentence_paragraph_and_preserves_names() -> None:
    text = "Jestes gotowa, Aniu. Zeby zacząć,przyjdź jutro."

    result = Analyzer(AnalyzerConfig()).correct(text)

    assert result.corrected_text == "Jesteś gotowa, Aniu. Żeby zacząć, przyjdź jutro."
    assert "Aniu" in result.corrected_text
    assert len(result.applied_findings) == 3


def test_default_analyzer_composes_exactly_eighteen_conservative_v1_rules() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    assert tuple(str(rule.source) for rule in analyzer._registry.rules()) == (
        "rule:agreement.copula",
        "rule:agreement.te_zdanie",
        "rule:agreement.nominal_group_te_duze_okno",
        "rule:inflection.negated_widziec",
        "rule:inflection.negated_widziec_nominal_group",
        "rule:spelling.jestes",
        "rule:spelling.napewno",
        "rule:spelling.wlasnie",
        "rule:spelling.zeby",
        "rule:syntax.comma_space",
        "rule:syntax.duplicate_comma",
        "rule:syntax.initial_conditional_comma",
        "rule:syntax.list_space",
        "rule:syntax.missing_correlative",
        "rule:syntax.missing_destination_preposition",
        "rule:syntax.missing_reflexive",
        "rule:syntax.quote_space",
        "rule:syntax.sentence_space",
    )


@pytest.mark.parametrize(
    ("text", "corrected_text", "source"),
    (
        ("Ona jestem.", "Ona jest.", "rule:agreement.copula"),
        ("Jestes gotowa.", "Jesteś gotowa.", "rule:spelling.jestes"),
        ("Wlasnie wrócił.", "Właśnie wrócił.", "rule:spelling.wlasnie"),
        ("Zeby wrócić.", "Żeby wrócić.", "rule:spelling.zeby"),
        ("Tak,nie.", "Tak, nie.", "rule:syntax.comma_space"),
        ("-pierwszy", "- pierwszy", "rule:syntax.list_space"),
        ('On powiedział"tak.', 'On powiedział" tak.', "rule:syntax.quote_space"),
        ("To działa.Dalej.", "To działa. Dalej.", "rule:syntax.sentence_space"),
    ),
)
def test_each_qualified_builtin_source_remains_automatic(
    text: str,
    corrected_text: str,
    source: str,
) -> None:
    result = Analyzer(AnalyzerConfig()).correct(text)

    assert result.corrected_text == corrected_text
    assert tuple(str(finding.source) for finding in result.applied_findings) == (
        source,
    )
    assert result.skipped_findings == ()


@pytest.mark.parametrize(
    ("operation", "behavior_version"),
    (
        ("replace.changed_typo", "spelling-zeby/1.0"),
        ("replace.common_typo", "spelling-zeby/2.0"),
    ),
)
def test_source_name_alone_cannot_qualify_changed_rule_behavior(
    operation: str,
    behavior_version: str,
) -> None:
    analyzer = _analyzer_with_rule(
        _VersionedZebyRule(
            operation=operation,
            behavior_version=behavior_version,
        )
    )

    result = analyzer.correct("Zeby")

    assert result.corrected_text == result.original_text
    assert result.applied_findings == ()
    assert tuple(str(finding.source) for finding in result.skipped_findings) == (
        "rule:spelling.zeby",
    )


def test_same_source_unversioned_rule_remains_reviewable() -> None:
    result = _analyzer_with_rule(_UnversionedZebyRule()).correct("Zeby")

    assert result.corrected_text == result.original_text
    assert result.applied_findings == ()
    assert tuple(str(finding.source) for finding in result.skipped_findings) == (
        "rule:spelling.zeby",
    )


def test_exact_qualified_rule_behavior_is_automatically_applied() -> None:
    result = _analyzer_with_rule(
        _VersionedZebyRule(
            operation="replace.common_typo",
            behavior_version="spelling-zeby/1.0",
        )
    ).correct("Zeby")

    assert result.corrected_text == "Żeby"
    assert tuple(str(finding.source) for finding in result.applied_findings) == (
        "rule:spelling.zeby",
    )
    assert result.skipped_findings == ()


def test_correct_keeps_text_unchanged_without_safe_suggestions() -> None:
    result = Analyzer(AnalyzerConfig()).correct("Rozmawiałem z Anną Kowalską.")

    assert result.corrected_text == result.original_text
    assert result.applied_findings == ()
    assert result.skipped_findings == ()


def test_analyzer_abstains_from_semantically_incoherent_timing() -> None:
    text = "Gdy wrócisz, zadzwoń do mnie wczoraj."
    analyzer = Analyzer(AnalyzerConfig())

    analysis = analyzer.analyze(text)
    correction = analyzer.correct(text)

    assert analysis.issues == ()
    assert correction.corrected_text == text
    assert correction.applied_findings == ()
    assert correction.skipped_findings == ()
    assert correction.suggestion_outcomes == ()


def test_correct_skips_a_conflicting_rule_suggestion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = "Zeby"
    source = Source(SourceKind.RULE, "spelling.zeby")
    first = Finding.create(
        category=Category.SPELLING,
        severity=Severity.ERROR,
        message="First correction.",
        explanation="Test conflict.",
        original="Zeby",
        suggestion="Żeby",
        start=0,
        end=4,
        confidence=Confidence(0.99),
        source=source,
    )
    second = Finding.create(
        category=Category.SPELLING,
        severity=Severity.ERROR,
        message="Second correction.",
        explanation="Test conflict.",
        original="Zeby",
        suggestion="Żebyż",
        start=0,
        end=4,
        confidence=Confidence(0.99),
        source=source,
    )
    analyzer = Analyzer(AnalyzerConfig())

    async def fake_analyze_async(
        _text: str, *, options: AnalysisOptions | None = None
    ) -> AnalysisResult:
        return AnalysisResult(text, (first, second), options=options)

    monkeypatch.setattr(
        analyzer,
        "analyze_async",
        fake_analyze_async,
    )

    result = analyzer.correct(text)

    assert result.corrected_text == "Żeby"
    assert result.applied_findings == (first,)
    assert result.skipped_findings == (second,)
