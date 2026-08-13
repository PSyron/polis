from __future__ import annotations

from polis import Analyzer, AnalyzerConfig
from polis.core import AnalysisOptions, Category
from polis.rules import DeterministicRuleRegistry, RuleRegistration
from polis.rules.spelling import (
    SpellingJestesRule,
    SpellingWlasnieRule,
    SpellingZebyRule,
)


def test_spelling_rules_emit_expected_fixes_with_offsets() -> None:
    text = "Zeby zeby, wlasnie! Jestes, ale to już jest."

    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(rule=SpellingZebyRule(), categories={Category.SPELLING}),
            RuleRegistration(
                rule=SpellingWlasnieRule(), categories={Category.SPELLING}
            ),
            RuleRegistration(rule=SpellingJestesRule(), categories={Category.SPELLING}),
        )
    )

    findings = registry.find(
        text, options=AnalysisOptions(categories={Category.SPELLING})
    )

    assert len(findings) == 4

    assert findings[0].original == "Zeby"
    assert findings[0].suggestion == "Żeby"
    assert findings[0].start == 0
    assert findings[0].end == 4

    assert findings[1].original == "zeby"
    assert findings[1].suggestion == "żeby"
    assert findings[1].start == 5

    assert findings[2].original == "wlasnie"
    assert findings[2].suggestion == "właśnie"
    assert text[findings[2].start : findings[2].end] == findings[2].original

    assert findings[3].original == "Jestes"
    assert findings[3].suggestion == "Jesteś"
    assert findings[3].start < findings[3].end


def test_spelling_rules_do_not_trigger_on_difficult_negatives() -> None:
    text = "Właśnie, to jest poprawna forma.\nJesteś ważny. Zebyj, wlasniew, niezeby"

    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=SpellingWlasnieRule(), categories={Category.SPELLING}
            ),
            RuleRegistration(rule=SpellingJestesRule(), categories={Category.SPELLING}),
            RuleRegistration(rule=SpellingZebyRule(), categories={Category.SPELLING}),
        )
    )

    findings = registry.find(
        text, options=AnalysisOptions(categories={Category.SPELLING})
    )

    assert len(findings) == 0


def test_default_analyzer_detects_napewno_with_case_and_unicode_offsets() -> None:
    text = "Żółw: NAPEWNO; Napewno, napewno."

    analyzer = Analyzer(AnalyzerConfig())
    result = analyzer.analyze(text)

    assert [
        (
            finding.category.value,
            str(finding.source),
            finding.original,
            finding.suggestion,
            finding.start,
            finding.end,
        )
        for finding in result.issues
    ] == [
        ("spelling", "rule:spelling.napewno", "NAPEWNO", "NA PEWNO", 6, 13),
        ("spelling", "rule:spelling.napewno", "Napewno", "Na pewno", 15, 22),
        ("spelling", "rule:spelling.napewno", "napewno", "na pewno", 24, 31),
    ]
    assert all(
        text[finding.start : finding.end] == finding.original
        for finding in result.issues
    )
    assert analyzer._registry.source_behavior(result.issues[0].source).operation == (
        "replace.common_typo"
    )
    assert (
        analyzer._registry.source_behavior(result.issues[0].source).behavior_version
        == "spelling-napewno/1.0"
    )
    assert result.apply(tuple(finding.id for finding in result.issues)) == (
        "Żółw: NA PEWNO; Na pewno, na pewno."
    )
    correction = analyzer.correct(text)
    assert correction.corrected_text == text
    assert correction.applied_findings == ()
    assert correction.skipped_findings == result.issues


def test_napewno_rule_respects_token_and_clause_boundaries() -> None:
    text = "(napewno), napewno;napewno\nnapewno na pewno napewności xnapewno napewnoX"

    findings = (
        Analyzer(AnalyzerConfig())
        .analyze(
            text,
            options=AnalysisOptions(categories={Category.SPELLING}),
        )
        .issues
    )

    assert [(finding.start, finding.end, finding.original) for finding in findings] == [
        (1, 8, "napewno"),
        (11, 18, "napewno"),
        (19, 26, "napewno"),
        (27, 34, "napewno"),
    ]
    assert (
        Analyzer(AnalyzerConfig())
        .analyze("na pewno napewności xnapewno napewnoX")
        .issues
        == ()
    )


def test_default_analyzer_detects_wogole_review_only_correction() -> None:
    text = "Wogole tego nie pamiętam."

    result = Analyzer(AnalyzerConfig()).analyze(text)

    assert tuple(str(finding.source) for finding in result.issues) == (
        "rule:spelling.wogole",
    )
