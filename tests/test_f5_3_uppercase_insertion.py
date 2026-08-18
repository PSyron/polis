"""F5.3 regressions for case-aware causal comma insertion."""

from __future__ import annotations

import pytest

from polis import Analyzer, AnalyzerConfig
from polis.core import Category
from polis.correction.policy import is_automatic_correction_eligible

_SOURCE = "rule:syntax.comma_before_bo"


@pytest.mark.parametrize(
    ("text", "start"),
    (
        ("ŻÓŁĆ: DZISIAJ NIE IDĘ BO PADA.", 21),
        ("ŻÓŁĆ: NIE IDĘ BO DESZCZ.", 13),
        ("ŻÓŁĆ: NIE IDĘ PONIEWAŻ PADA.", 13),
        ("ŻÓŁĆ: NIE IDĘ GDYŻ PADA.", 13),
        ("POTEM ZOSTAJĘ. NIE IDĘ BO PADA.", 22),
        ("Potem zostaję. NIE IDĘ BO PADA.", 22),
    ),
)
def test_f53_accepts_qualified_uppercase_causal_shapes(text: str, start: int) -> None:
    findings = tuple(
        finding
        for finding in Analyzer(AnalyzerConfig()).analyze(text).issues
        if str(finding.source) == _SOURCE
    )

    assert len(findings) == 1
    finding = findings[0]
    assert (finding.start, finding.end) == (start, start)
    assert (finding.original, finding.suggestion) == ("", ",")
    assert text[finding.start : finding.end] == ""
    assert finding.category is Category.SYNTAX


def test_f53_widening_remains_review_only_and_keeps_identity() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    finding = next(
        item
        for item in analyzer.analyze("ŻÓŁĆ: NIE IDĘ PONIEWAŻ PADA.").issues
        if str(item.source) == _SOURCE
    )
    behavior = analyzer._registry.source_behavior(finding.source)
    assert behavior is not None
    assert behavior.operation == "insert.causal_clause_comma"
    assert behavior.behavior_version == "syntax-comma-before-bo/3.0"
    assert finding.confidence.value == 0.9
    assert not is_automatic_correction_eligible(finding, behavior)
    correction = analyzer.correct("ŻÓŁĆ: NIE IDĘ PONIEWAŻ PADA.")
    assert correction.corrected_text == correction.original_text
    assert correction.applied_findings == ()
    assert correction.skipped_findings == (finding,)


@pytest.mark.parametrize(
    "text",
    (
        "NIE IDĘ bo PADA.",
        "NIE IDĘ BO pada.",
        "NIE IDĘ Bo PADA.",
        "NIE IDĘ BO Pada.",
        "NIE IDĘ BO PADA",
        "NIE IDĘ BO PADA!",
        "NIE IDĘ, BO PADA.",
        "NIE IDĘ ALBO PADA.",
        "NIE IDĘ BO PADA..",
        "API_KEY BO PADA.",
        "HTTPS://EXAMPLE.COM/BO/PADA.",
        "„NIE IDĘ BO PADA.”",
        "`NIE IDĘ BO PADA.`",
        "TO BO PADA.",
        "JAK BO PADA.",
        "NIE BO PADA.",
    ),
)
def test_f53_rejects_malformed_or_non_sentence_uppercase_mentions(text: str) -> None:
    assert not any(
        str(item.source) == _SOURCE
        for item in Analyzer(AnalyzerConfig()).analyze(text).issues
    )


@pytest.mark.parametrize(
    "precursor",
    (
        "NO",
        "A",
        "I",
        "ORAZ",
        "ALE",
        "LECZ",
        "CZY",
        "TO",
        "WIĘC",
        "LUB",
        "ALBO",
        "ANI",
        "BĄDŹ",
        "NIE",
        "TYLKO",
        "JEDYNIE",
        "WŁAŚNIE",
        "JAK",
        "JAKO",
        "NIŻ",
    ),
)
def test_f53_preserves_every_uppercase_precursor_exclusion(precursor: str) -> None:
    text = f"X {precursor} BO PADA."
    assert not any(
        str(item.source) == _SOURCE
        for item in Analyzer(AnalyzerConfig()).analyze(text).issues
    )


def test_f53_keeps_uppercase_repetition_order_and_sentence_containment() -> None:
    text = "NIE IDĘ BO PADA I NIE WRACAM BO PADA. POTEM ZOSTAJĘ."
    findings = tuple(
        item
        for item in Analyzer(AnalyzerConfig()).analyze(text).issues
        if str(item.source) == _SOURCE
    )

    assert tuple((item.start, item.end) for item in findings) == ((7, 7), (28, 28))
    assert all(text[item.start : item.end] == "" for item in findings)
