from __future__ import annotations

import pytest

from polis import (
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


def test_correct_applies_safe_rule_corrections_to_a_sentence() -> None:
    result = Analyzer(AnalyzerConfig()).correct("Zeby jutro,powiem o tym.")

    assert result.original_text == "Zeby jutro,powiem o tym."
    assert result.corrected_text == "Żeby jutro, powiem o tym."
    assert {finding.original for finding in result.applied_findings} == {"Zeby", ","}
    assert result.skipped_findings == ()


def test_correct_handles_a_multi_sentence_paragraph_and_preserves_names() -> None:
    text = "Jestes gotowa, Aniu. Zeby zacząć,przyjdź jutro."

    result = Analyzer(AnalyzerConfig()).correct(text)

    assert result.corrected_text == "Jesteś gotowa, Aniu. Żeby zacząć, przyjdź jutro."
    assert "Aniu" in result.corrected_text
    assert len(result.applied_findings) == 3


def test_correct_keeps_text_unchanged_without_safe_suggestions() -> None:
    result = Analyzer(AnalyzerConfig()).correct("Rozmawiałem z Anną Kowalską.")

    assert result.corrected_text == result.original_text
    assert result.applied_findings == ()
    assert result.skipped_findings == ()


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

    async def fake_analysis_for_correction(
        _text: str, _options: object
    ) -> tuple[AnalysisResult, tuple[object, ...]]:
        return AnalysisResult(text, (first, second)), ()

    monkeypatch.setattr(
        analyzer,
        "_analysis_for_correction",
        fake_analysis_for_correction,
    )

    result = analyzer.correct(text)

    assert result.corrected_text == "Żeby"
    assert result.applied_findings == (first,)
    assert result.skipped_findings == (second,)
