from __future__ import annotations

import pytest

from polis import Analyzer, AnalyzerConfig
from polis.core import AnalysisOptions, Category
from polis.rules import (
    AgreementTeZdanieRule,
    DeterministicRuleRegistry,
    RuleRegistration,
)
from polis.rules.agreement import AgreementCopulaRule


def test_agreement_copula_rule_fixes_obvious_mismatches() -> None:
    text = "Ona jestem.\nTy jestem.\nMy jestem.\nONA JESTEM.\nTy Jestem"

    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=AgreementCopulaRule(), categories={Category.AGREEMENT}),)
    )

    findings = registry.find(
        text, options=AnalysisOptions(categories={Category.AGREEMENT})
    )

    assert len(findings) == 5

    assert findings[0].category == Category.AGREEMENT
    assert findings[0].original == "jestem"
    assert findings[0].suggestion == "jest"
    assert findings[0].start == 4
    assert findings[0].end == 10

    assert findings[1].original == "jestem"
    assert findings[1].suggestion == "jesteś"

    assert findings[2].original == "jestem"
    assert findings[2].suggestion == "jesteśmy"

    assert findings[3].original == "JESTEM"
    assert findings[3].suggestion == "JEST"

    assert findings[4].original == "Jestem"
    assert findings[4].suggestion == "Jesteś"


def test_agreement_copula_rule_respects_category_filtering() -> None:
    text = "Ona jestem, to jest poprawne."

    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=AgreementCopulaRule(), categories={Category.AGREEMENT}),)
    )

    findings = registry.find(
        text, options=AnalysisOptions(categories={Category.SPELLING})
    )

    assert findings == ()


@pytest.mark.parametrize(
    ("text", "original", "suggestion", "start", "end"),
    (
        ("Te zdanie jest poprawne.", "Te zdanie", "To zdanie", 0, 9),
        ("te zdanie jest poprawne.", "te zdanie", "to zdanie", 0, 9),
        ("Te\tzdanie jest poprawne.", "Te\tzdanie", "To\tzdanie", 0, 9),
        ("🙂 Te zdanie jest poprawne.", "Te zdanie", "To zdanie", 2, 11),
        ("Te zdanie, które czytasz, jest krótkie.", "Te zdanie", "To zdanie", 0, 9),
        ("Pierwsze. Te zdanie jest drugie.", "Te zdanie", "To zdanie", 10, 19),
    ),
)
def test_agreement_te_zdanie_rule_finds_allowlisted_phrase_with_exact_offsets(
    text: str,
    original: str,
    suggestion: str,
    start: int,
    end: int,
) -> None:
    analyzer = Analyzer(AnalyzerConfig())

    findings = analyzer.analyze(
        text, options=AnalysisOptions(categories={Category.AGREEMENT})
    ).issues

    assert len(findings) == 1
    finding = findings[0]
    assert finding.category is Category.AGREEMENT
    assert str(finding.source) == "rule:agreement.te_zdanie"
    assert finding.original == original
    assert finding.suggestion == suggestion
    assert (finding.start, finding.end) == (start, end)
    assert text[finding.start : finding.end] == finding.original


@pytest.mark.parametrize(
    "text",
    (
        "To zdanie jest poprawne.",
        "Te zdania są poprawne.",
        "moTe zdanie jest poprawne.",
        "Te zdaniem zajmuje się redaktor.",
        "Te\nzdanie.",
        "Te\r\nzdanie.",
    ),
)
def test_agreement_te_zdanie_rule_abstains_outside_the_closed_pattern(
    text: str,
) -> None:
    analyzer = Analyzer(AnalyzerConfig())

    findings = analyzer.analyze(
        text, options=AnalysisOptions(categories={Category.AGREEMENT})
    ).issues

    assert findings == ()


def test_agreement_te_zdanie_rule_does_not_own_te_dziecko_surface() -> None:
    """``Te dziecko`` belongs to ``agreement.te_neuter_noun``, not te_zdanie."""
    analyzer = Analyzer(AnalyzerConfig())
    findings = analyzer.analyze(
        "Te dziecko jest gotowe.",
        options=AnalysisOptions(categories={Category.AGREEMENT}),
    ).issues
    assert all(str(item.source) != "rule:agreement.te_zdanie" for item in findings)
    assert any(str(item.source) == "rule:agreement.te_neuter_noun" for item in findings)


def test_agreement_te_zdanie_rule_has_closed_behavior_metadata() -> None:
    rule = AgreementTeZdanieRule()

    assert rule.operation == "replace.demonstrative_neuter_phrase"
    assert rule.behavior_version == "agreement-te-zdanie/1.0"


def test_default_analyzer_exposes_te_zdanie_for_explicit_application_only() -> None:
    text = "Te zdanie jest poprawne."
    analyzer = Analyzer(AnalyzerConfig())

    analysis = analyzer.analyze(
        text, options=AnalysisOptions(categories={Category.AGREEMENT})
    )
    filtered = analyzer.analyze(
        text, options=AnalysisOptions(categories={Category.SPELLING})
    )
    correction = analyzer.correct(text)

    assert len(analysis.issues) == 1
    assert analysis.apply((analysis.issues[0].id,)) == "To zdanie jest poprawne."
    assert filtered.issues == ()
    assert correction.corrected_text == text
    assert correction.applied_findings == ()
    assert correction.skipped_findings == analysis.issues
