from __future__ import annotations

from typing import Protocol, cast

import pytest

import polis.rules as rules
from polis import Analyzer, AnalyzerConfig
from polis.core import AnalysisOptions, Category
from polis.rules import (
    DeterministicRuleRegistry,
    RuleRegistration,
    SyntaxMissingCorrelativeRule,
    SyntaxMissingReflexiveRule,
)


def test_residual_syntax_rules_are_public() -> None:
    assert hasattr(rules, "SyntaxMissingReflexiveRule")
    assert hasattr(rules, "SyntaxMissingCorrelativeRule")


class _FindingView(Protocol):
    start: int
    end: int
    original: str
    suggestion: str
    source: object
    category: object


def _find(text: str) -> tuple[_FindingView, ...]:
    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=SyntaxMissingReflexiveRule(),
                categories={Category.SYNTAX},
            ),
            RuleRegistration(
                rule=SyntaxMissingCorrelativeRule(),
                categories={Category.SYNTAX},
            ),
        )
    )
    return cast(
        tuple[_FindingView, ...],
        registry.find(text, options=AnalysisOptions(categories={Category.SYNTAX})),
    )


@pytest.mark.parametrize(
    ("text", "start", "suggestion", "source"),
    (
        (
            "Ona boi ciemności od dziecka.",
            len("Ona boi"),
            " się",
            "rule:syntax.missing_reflexive",
        ),
        (
            "Nie spodziewaliśmy tak szybkiej odpowiedzi.",
            len("Nie spodziewaliśmy"),
            " się",
            "rule:syntax.missing_reflexive",
        ),
        (
            "Im dłużej czekaliśmy, bardziej byliśmy niecierpliwi.",
            len("Im dłużej czekaliśmy, "),
            "tym ",
            "rule:syntax.missing_correlative",
        ),
    ),
)
def test_residual_syntax_rules_emit_exact_unicode_insertions(
    text: str,
    start: int,
    suggestion: str,
    source: str,
) -> None:
    findings = _find(text)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.start == start
    assert finding.end == start
    assert finding.original == ""
    assert finding.suggestion == suggestion
    assert str(finding.source) == source
    assert finding.category == Category.SYNTAX


@pytest.mark.parametrize(
    "text",
    (
        "Ona boi się ciemności od dziecka.",
        "Nie spodziewaliśmy się tak szybkiej odpowiedzi.",
        "Im dłużej czekaliśmy, tym bardziej byliśmy niecierpliwi.",
        "Hałas boi dzieci i zwierzęta.",
        "Jan boi ciemności od dziecka.",
        "Liczba 2026 i adres https://example.org pozostają bez zmian.",
        "Napisała: „Ona boi ciemności od dziecka”.",
        "Bardziej byliśmy niecierpliwi, im dłużej czekaliśmy.",
    ),
)
def test_residual_syntax_rules_leave_protected_and_out_of_scope_sentences_unchanged(
    text: str,
) -> None:
    assert _find(text) == ()


@pytest.mark.parametrize(
    "text",
    (
        "Ona boi ciemności. Drugie zdanie jest poprawne.",
        "Nie spodziewaliśmy odpowiedzi! Potem wyszliśmy.",
        "Im dłużej czekaliśmy, bardziej się martwiliśmy? Tak było.",
    ),
)
def test_residual_syntax_rules_abstain_from_multi_sentence_input(text: str) -> None:
    assert _find(text) == ()


def test_residual_syntax_rules_respect_category_filter() -> None:
    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=SyntaxMissingReflexiveRule(),
                categories={Category.SYNTAX},
            ),
        )
    )
    assert (
        registry.find(
            "Ona boi ciemności.",
            options=AnalysisOptions(categories={Category.SPELLING}),
        )
        == ()
    )


def test_default_analyzer_exposes_sentence_only_residual_syntax_findings() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    single = analyzer.analyze("Ona boi ciemności.")
    multiple = analyzer.analyze("Ona boi ciemności. Drugie zdanie jest poprawne.")

    assert [str(finding.source) for finding in single.issues] == [
        "rule:syntax.missing_reflexive"
    ]
    assert multiple.issues == ()


def test_residual_syntax_findings_require_explicit_caller_selection() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    result = analyzer.correct("Nie spodziewaliśmy tak szybkiej odpowiedzi.")

    assert result.corrected_text == result.original_text
    assert result.applied_findings == ()
    assert [str(finding.source) for finding in result.skipped_findings] == [
        "rule:syntax.missing_reflexive"
    ]
    assert result.apply_suggestions([result.skipped_findings[0].id]) == (
        "Nie spodziewaliśmy się tak szybkiej odpowiedzi."
    )
