from __future__ import annotations

from polis.core import AnalysisOptions, Category
from polis.rules import (
    DeterministicRuleRegistry,
    RuleRegistration,
    SyntaxCommaSpacingRule,
    SyntaxListSpacingRule,
    SyntaxQuoteSpacingRule,
    SyntaxSentenceSpacingRule,
)


def test_syntax_comma_space_rule_adds_missing_space_and_skips_abbreviations() -> None:
    text = "Tak,to, to. itp, to. m.in, to."

    findings = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=SyntaxCommaSpacingRule(), categories={Category.PUNCTUATION}
            ),
        )
    ).find(text, options=AnalysisOptions(categories={Category.PUNCTUATION}))

    assert len(findings) == 1
    assert findings[0].original == ","
    assert findings[0].suggestion == ", "
    assert findings[0].start == 3
    assert findings[0].category == Category.PUNCTUATION


def test_syntax_list_space_rule_handles_markers_without_following_space() -> None:
    text = "1.pierwszy\n-drugi\n*trzeci\n- poprawnie\n1. poprawnie\n"

    findings = DeterministicRuleRegistry(
        (RuleRegistration(rule=SyntaxListSpacingRule(), categories={Category.SYNTAX}),)
    ).find(text, options=AnalysisOptions(categories={Category.SYNTAX}))

    assert len(findings) == 3
    assert all(finding.suggestion == " " for finding in findings)
    assert all(finding.category == Category.SYNTAX for finding in findings)
    assert findings[0].start == 2
    assert findings[1].start == 12
    assert findings[2].start == 19


def test_syntax_quote_space_rule_adds_space_after_attached_quotes() -> None:
    text = 'On powiedział"zatem."'

    findings = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=SyntaxQuoteSpacingRule(), categories={Category.PUNCTUATION}
            ),
        )
    ).find(text, options=AnalysisOptions(categories={Category.PUNCTUATION}))

    assert len(findings) == 1
    assert findings[0].original == '"'
    assert findings[0].suggestion == '" '
    assert findings[0].start == len("On powiedział")
    assert findings[0].end == findings[0].start + 1


def test_syntax_quote_space_rule_ignores_whitespace_prefixed_quotes() -> None:
    text = 'On powiedział "zatem."'

    findings = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=SyntaxQuoteSpacingRule(), categories={Category.PUNCTUATION}
            ),
        )
    ).find(text, options=AnalysisOptions(categories={Category.PUNCTUATION}))

    assert findings == ()


def test_sentence_space_rule_skips_abbreviations() -> None:
    text = "To działa.Następne zdanie. np.Tak nie zapisujemy."

    findings = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=SyntaxSentenceSpacingRule(), categories={Category.PUNCTUATION}
            ),
        )
    ).find(text, options=AnalysisOptions(categories={Category.PUNCTUATION}))

    assert len(findings) == 1
    assert findings[0].original == "."
    assert findings[0].suggestion == ". "
    assert findings[0].start == len("To działa")
