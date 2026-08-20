from __future__ import annotations

from polis import Analyzer, AnalyzerConfig, Severity

_SOURCE = "rule:spelling.nie_byc_joint"
_BEHAVIOR_VERSION = "spelling-nie-byc-joint/1.0"


def test_niejestes_emits_exact_review_only_findings_for_each_occurrence() -> None:
    text = "Niejestes gotowy. NIEJESTES pewny. niejestes spóźniony."

    result = Analyzer(AnalyzerConfig()).analyze(text)

    assert [
        (
            finding.category.value,
            str(finding.source),
            finding.severity,
            finding.original,
            finding.suggestion,
            finding.start,
            finding.end,
        )
        for finding in result.issues
    ] == [
        ("spelling", _SOURCE, Severity.SUGGESTION, "Niejestes", "Nie jesteś", 0, 9),
        (
            "spelling",
            _SOURCE,
            Severity.SUGGESTION,
            "NIEJESTES",
            "NIE JESTEŚ",
            18,
            27,
        ),
        (
            "spelling",
            _SOURCE,
            Severity.SUGGESTION,
            "niejestes",
            "nie jesteś",
            35,
            44,
        ),
    ]
    assert all(
        text[finding.start : finding.end] == finding.original
        for finding in result.issues
    )
    behavior = Analyzer(AnalyzerConfig())._registry.source_behavior(
        result.issues[0].source
    )
    assert behavior is not None
    assert behavior.behavior_version == _BEHAVIOR_VERSION


def test_niejestes_preserves_abstention_and_requires_explicit_apply() -> None:
    text = (
        'Nie jesteś gotowy. "Niejestes" `Niejestes` '
        "https://example.test/Niejestes email@Niejestes.test "
        "xNiejestes NiejestesX.\nNiejestes gotowy."
    )
    analyzer = Analyzer(AnalyzerConfig())

    result = analyzer.analyze(text)
    findings = result.issues

    assert len(findings) == 1
    finding = findings[0]
    assert str(finding.source) == _SOURCE
    assert text[finding.start : finding.end] == "Niejestes"
    assert analyzer.correct(text).corrected_text == text
    assert analyzer.correct(text).skipped_findings == findings
    assert result.apply((finding.id,)) == text.replace(
        "Niejestes gotowy.", "Nie jesteś gotowy."
    )
