"""Regressions for shared literal-rule context abstention (#338 F0.1)."""

from __future__ import annotations

import pytest

from polis import Analyzer, AnalyzerConfig
from polis.core import AnalysisOptions, Category
from polis.rules.spelling import SpellingWogoleRule, SpellingZebyRule


@pytest.mark.parametrize(
    "text",
    (
        "https://example.org/wogole/index.html",
        "http://example.org/path?x=wogole",
        "example.org/wogole/index.html",
        "Napisz do mnie: wogole@example.org",
        "Kontakt: admin@wogole.example.org",
        "Cytat: „Zdanie to jest wogole dziwne, jak pisano w 1925 r.” tak brzmi.",
        'Powiedziano: "To wogole nie ma sensu w 1925 r." — koniec.',
        "Identyfikator foo-wogole-bar nie jest literówką zdaniową.",
        "Kod: wogole_v2 w konfiguracji.",
    ),
)
def test_literal_rules_abstain_in_url_email_quote_and_mixed_case_contexts(
    text: str,
) -> None:
    result = Analyzer(AnalyzerConfig()).analyze(
        text,
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    assert result.issues == ()


def test_measured_wogole_false_positives_abstain() -> None:
    """Exact measured defects from #338 must not emit spelling.wogole."""
    cases = (
        "https://example.org/wogole/index.html",
        "Napisz do mnie: wogole@example.org",
        "Cytat: „Zdanie to jest wogole dziwne, jak pisano w 1925 r.” tak brzmi.",
    )
    rule = SpellingWogoleRule()
    options = AnalysisOptions(categories={Category.SPELLING})

    for text in cases:
        assert rule.find(text, options=options) == ()


@pytest.mark.parametrize(
    "text",
    (
        "Wogole tego nie pamiętam.",
        "wogole",
        "WOGOLE to błąd.",
        "Zeby zdążyć, wyjdź wcześniej.",
    ),
)
def test_literal_rules_still_fire_on_plain_sentence_tokens(text: str) -> None:
    result = Analyzer(AnalyzerConfig()).analyze(
        text,
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    assert result.issues
    assert all(finding.category is Category.SPELLING for finding in result.issues)


def test_context_guard_applies_to_all_literal_sources_not_only_wogole() -> None:
    options = AnalysisOptions(categories={Category.SPELLING})
    assert (
        SpellingZebyRule().find("https://example.org/zeby/docs", options=options) == ()
    )
    assert SpellingZebyRule().find("Zeby zdążyć.", options=options)
