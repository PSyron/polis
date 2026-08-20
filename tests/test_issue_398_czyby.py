from __future__ import annotations

from polis import Analyzer, AnalyzerConfig, Severity

_SOURCE = "rule:spelling.czyby"
_BEHAVIOR_VERSION = "spelling-czyby/1.0"
_RJP_HARD_NEGATIVES = (
    "aby",
    "ażeby",
    "byleby",
    "chociażby",
    "choćby",
    "czyżby",
    "gdyby",
    "gdzieżby",
    "iżby",
    "jakby",
    "jakoby",
    "jakżeby",
    "niby",
    "niżby",
    "oby",
    "żeby",
)


def test_czyby_emits_exact_review_only_findings_for_each_occurrence() -> None:
    text = "Czyby to prawda? CZYBY to możliwe. czyby to działało."

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
        if str(finding.source) == _SOURCE
    ] == [
        ("spelling", _SOURCE, Severity.SUGGESTION, "Czyby", "Czy by", 0, 5),
        ("spelling", _SOURCE, Severity.SUGGESTION, "CZYBY", "CZY BY", 17, 22),
        ("spelling", _SOURCE, Severity.SUGGESTION, "czyby", "czy by", 35, 40),
    ]
    findings = tuple(
        finding for finding in result.issues if str(finding.source) == _SOURCE
    )
    assert all(
        text[finding.start : finding.end] == finding.original for finding in findings
    )
    behavior = Analyzer(AnalyzerConfig())._registry.source_behavior(findings[0].source)
    assert behavior is not None
    assert behavior.behavior_version == _BEHAVIOR_VERSION


def test_czyby_preserves_abstention_and_requires_explicit_apply() -> None:
    text = (
        'Czy by to prawda? "czyby" `czyby` '
        "https://example.test/czyby email@czyby.test "
        "xCzyby czybyX nieczyby czybym.\nCzyby to prawda."
    )
    analyzer = Analyzer(AnalyzerConfig())

    result = analyzer.analyze(text)
    findings = tuple(
        finding for finding in result.issues if str(finding.source) == _SOURCE
    )

    assert len(findings) == 1
    finding = findings[0]
    assert text[finding.start : finding.end] == "Czyby"
    assert analyzer.correct(text).corrected_text == text
    assert analyzer.correct(text).skipped_findings == findings
    assert result.apply((finding.id,)) == text.replace(
        "Czyby to prawda.", "Czy by to prawda."
    )


def test_czyby_rejects_rjp_lexical_negatives_and_embedded_hosts() -> None:
    negatives = " ".join(_RJP_HARD_NEGATIVES)
    text = (
        f"{negatives} czy by czybym nieczyby xczyby czybyX. "
        '"czyby" `czyby` https://example.test/czyby email@czyby.test '
        "zażółć czyby."
    )

    findings = tuple(
        finding
        for finding in Analyzer(AnalyzerConfig()).analyze(text).issues
        if str(finding.source) == _SOURCE
    )

    assert len(findings) == 1
    finding = findings[0]
    assert text[finding.start : finding.end] == "czyby"
    assert finding.original == "czyby"
    assert finding.suggestion == "czy by"
    assert finding.category.value == "spelling"
    assert finding.severity is Severity.SUGGESTION
