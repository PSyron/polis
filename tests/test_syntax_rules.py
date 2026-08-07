from __future__ import annotations

import pytest

from polis import Analyzer, AnalyzerConfig
from polis.core import AnalysisOptions, Category
from polis.rules import (
    DeterministicRuleRegistry,
    RuleRegistration,
    SyntaxCommaSpacingRule,
    SyntaxDuplicateCommaRule,
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


@pytest.mark.parametrize(
    ("text", "expected_start"),
    [
        ("Cześć,, Anno.", 6),
        ("Żółw,, biegnie.", 5),
        ("Mówię,, że wrócę.", 6),
        ("Tak,, ale idziemy.", 4),
    ],
)
def test_default_analyzer_removes_second_comma_for_safe_adjacent_comma_context(
    text: str, expected_start: int
) -> None:
    analysis = Analyzer(AnalyzerConfig()).analyze(text)

    assert len(analysis.issues) == 1
    finding = analysis.issues[0]
    assert finding.category == Category.PUNCTUATION
    assert str(finding.source) == "rule:syntax.duplicate_comma"
    assert finding.original == ","
    assert finding.suggestion == ""
    assert (finding.start, finding.end) == (expected_start, expected_start + 1)
    assert (
        analysis.apply((finding.id,))
        == text[:expected_start] + text[expected_start + 1 :]
    )
    correction = Analyzer(AnalyzerConfig()).correct(text)
    assert correction.corrected_text == text
    assert correction.applied_findings == ()
    assert correction.skipped_findings == (finding,)


@pytest.mark.parametrize(
    "text",
    [
        "Cześć, Anno.",
        "Cześć,,, Anno.",
        "1,, 2",
        "„Cześć,, Anno.”",
        "„Cześć,, Anno.",
        "Cześć,,,, Anno.",
    ],
)
def test_default_analyzer_abstains_from_ambiguous_adjacent_comma_contexts(
    text: str,
) -> None:
    analysis = Analyzer(AnalyzerConfig()).analyze(text)

    assert analysis.issues == ()


def test_duplicate_comma_rule_exposes_versioned_remove_operation() -> None:
    rule = SyntaxDuplicateCommaRule()

    assert str(rule.source) == "rule:syntax.duplicate_comma"
    assert rule.operation == "remove.duplicate_comma"
    assert rule.behavior_version == "syntax-duplicate-comma/1.0"


def test_default_analyzer_filters_duplicate_comma_by_punctuation_category() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    punctuation = analyzer.analyze(
        "Cześć,, Anno.",
        options=AnalysisOptions(categories={Category.PUNCTUATION}),
    )
    syntax = analyzer.analyze(
        "Cześć,, Anno.",
        options=AnalysisOptions(categories={Category.SYNTAX}),
    )

    assert len(punctuation.issues) == 1
    assert syntax.issues == ()
