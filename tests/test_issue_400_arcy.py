from __future__ import annotations

from polis import AnalysisOptions, Analyzer, AnalyzerConfig, Category, Finding, Severity
from polis.rules import SpellingArcyPrefixRule

_SOURCE = "rule:spelling.arcy_prefix"
_BEHAVIOR_VERSION = "spelling-arcy-prefix/1.0"
_OPERATION = "replace.prefix_hyphenation"


def _source_findings(text: str) -> tuple[Finding, ...]:
    return tuple(
        finding
        for finding in Analyzer(AnalyzerConfig()).analyze(text).issues
        if str(finding.source) == _SOURCE
    )


def test_arcy_emits_exact_review_only_findings_for_non_initial_uppercase_targets() -> (
    None
):
    text = "To jest arcy Europa. Widziałem arcy Łódź i arcy EUROPA."

    findings = _source_findings(text)

    assert [
        (
            finding.category.value,
            finding.severity,
            finding.original,
            finding.suggestion,
            finding.start,
            finding.end,
        )
        for finding in findings
    ] == [
        ("spelling", Severity.SUGGESTION, "arcy Europa", "arcy-Europa", 8, 19),
        ("spelling", Severity.SUGGESTION, "arcy Łódź", "arcy-Łódź", 31, 40),
        ("spelling", Severity.SUGGESTION, "arcy EUROPA", "arcy-EUROPA", 43, 54),
    ]
    assert all(
        text[finding.start : finding.end] == finding.original for finding in findings
    )
    analyzer = Analyzer(AnalyzerConfig())
    behavior = analyzer._registry.source_behavior(findings[0].source)
    assert behavior is not None
    assert behavior.operation == _OPERATION
    assert behavior.behavior_version == _BEHAVIOR_VERSION


def test_arcy_requires_explicit_apply_and_preserves_repeated_sentence_offsets() -> None:
    text = "To jest arcy Europa. Potem arcy Europa."
    analyzer = Analyzer(AnalyzerConfig())

    result = analyzer.analyze(text)
    findings = tuple(
        finding for finding in result.issues if str(finding.source) == _SOURCE
    )

    assert [(finding.start, finding.end) for finding in findings] == [
        (8, 19),
        (27, 38),
    ]
    assert analyzer.correct(text).corrected_text == text
    assert analyzer.correct(text).skipped_findings == findings
    assert result.apply(tuple(finding.id for finding in findings)) == (
        "To jest arcy-Europa. Potem arcy-Europa."
    )


def test_arcy_abstains_on_sentence_initial_correct_and_non_prose_boundaries() -> None:
    text = (
        "Arcy Europa. arcy Europa. arcy pomysł. arcy-Europa. "
        "arcy  Europa. arcy\tEuropa. ARCY Europa. "
        '"arcy Europa" `arcy Europa` https://example.test/arcy Europa '
        "email@arcy Europa.test x_arcy Europa superarcy Europa arcy, Europa. "
        "arcy O'Connor. arcy O’Connor. arcy O＇Connor. arcy O‛Connor. "
        "arcy O′Connor. arcy O՚Connor. arcy O׳Connor. „To koniec.” arcy Europa. "
        "To koniec… arcy Europa. To koniec.› arcy Europa. "
        "To koniec…› arcy Europa. To koniec.」 arcy Europa. "
        "To koniec…」 arcy Europa. Nagłówek\narcy Europa. "
        "Nagłówek\u2028arcy Europa. Nagłówek\u2029arcy Europa. "
        "Nagłówek\u0085arcy Europa. "
        "(arcy Europa) 'arcy Europa' [arcy Europa]. "
        "To (arcy Europa. To arcy Europa)."
    )

    assert _source_findings(text) == ()


def test_arcy_abstains_on_unspaced_punctuation_candidate_streams() -> None:
    text = "arcy Europa,arcy Łódź;arcy EUROPA:arcy Polska"

    assert _source_findings(text) == ()


def test_arcy_abstains_on_unmatched_and_nested_wrappers() -> None:
    text = (
        "Wstęp ) arcy Europa. Wstęp ] arcy Polska. Wstęp } arcy Łódź. "
        "Wstęp › arcy EUROPA. Wstęp 」 arcy Europa. "
        "““arcy Europa” arcy Polska.” ((arcy Europa) arcy Polska.) "
    )

    assert _source_findings(text) == ()
    assert _source_findings("Wstęp ([)] arcy Europa.") == ()


def test_arcy_abstains_on_decomposed_unicode_target_boundary() -> None:
    assert _source_findings("Wstęp arcy Łodz\u0301.") == ()


def test_arcy_abstains_on_clause_punctuation_boundaries() -> None:
    assert _source_findings("To jest, arcy Europa.") == ()
    assert _source_findings("To jest arcy Europa, prawda?") == ()


def test_arcy_abstains_after_sentence_boundary_inside_closed_wrapper() -> None:
    assert _source_findings("To koniec. [uwaga] arcy Europa.") == ()
    assert _source_findings("To koniec. [uwaga [więcej]] arcy Europa.") == ()


def test_arcy_handles_large_candidate_rich_input_without_context_drift() -> None:
    text = "Wstęp " + " ".join("arcy Europa" for _ in range(4_000))
    findings = SpellingArcyPrefixRule().find(
        text,
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    assert len(findings) == 4_000
    assert findings[0].start == 6
    assert findings[-1].original == "arcy Europa"
