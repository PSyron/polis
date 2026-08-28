from __future__ import annotations

import pytest

from polis import AnalysisOptions, Analyzer, AnalyzerConfig
from polis.core import Category
from polis.rules._morfeusz import (
    _load_qualified_morfeusz,
    _QualifiedMorfeusz,
)


def _provider() -> _QualifiedMorfeusz:
    provider = _load_qualified_morfeusz()
    assert provider is not None
    return provider


def test_existing_literal_conditional_comma_behavior_is_preserved() -> None:
    # Given
    text = "Jeśli pada zostaję w domu."

    # When
    findings = Analyzer(AnalyzerConfig()).analyze(text).issues

    # Then
    assert tuple(
        (str(finding.source), finding.start, finding.end, finding.suggestion)
        for finding in findings
    ) == (("rule:syntax.initial_conditional_comma", 10, 10, ","),)


@pytest.mark.parametrize(
    ("text", "source", "offset"),
    (
        ("Jeśli pada wracam.", "rule:syntax.initial_conditional_comma", 10),
        ("Jeśli chcesz przyjdź.", "rule:syntax.initial_conditional_comma", 12),
        (
            "Jeżeli pada zostaję w domu.",
            "rule:syntax.initial_conditional_comma",
            11,
        ),
        ("Gdy chcesz przyjdź.", "rule:syntax.initial_temporal_comma", 10),
        ("Kiedy wrócisz zadzwoń.", "rule:syntax.initial_temporal_comma", 13),
        ("Gdyby padało zostałbym.", "rule:syntax.initial_conditional_comma", 12),
    ),
)
def test_required_examples_emit_minimal_review_only_insertions(
    text: str, source: str, offset: int
) -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    findings = tuple(
        finding
        for finding in analyzer.analyze(text).issues
        if str(finding.source) == source
    )

    # Then
    assert len(findings) == 1
    assert (
        findings[0].start,
        findings[0].end,
        findings[0].original,
        findings[0].suggestion,
    ) == (offset, offset, "", ",")
    correction = analyzer.correct(text)
    assert findings[0] in correction.skipped_findings
    assert findings[0] not in correction.applied_findings


@pytest.mark.parametrize(
    ("text", "offset"),
    (
        ("Jeśli pada wracam.", 10),
        ("Jeśli chcesz przyjdź.", 12),
        ("Jeśli skończysz zadzwoń.", 15),
        ("Jeżeli pada zostaję.", 11),
        ("Jeżeli możesz wróć.", 13),
        ("Jeżeli wrócisz zadzwoń.", 14),
        ("Gdy pada wracam.", 8),
        ("Gdy chcesz przyjdź.", 10),
        ("Gdy skończysz zadzwoń.", 13),
        ("Kiedy wrócisz zadzwoń.", 13),
        ("Kiedy pada zostaję.", 10),
        ("Kiedy skończysz odpocznij.", 15),
        ("Gdyby padało zostałbym.", 12),
        ("Gdyby chciał przyszedłby.", 12),
        ("Gdyby wiedział zadzwoniłby.", 14),
    ),
)
def test_closed_conjunctions_support_three_distinct_predicate_pairs(
    text: str, offset: int
) -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    findings = tuple(
        finding
        for finding in analyzer.analyze(text).issues
        if str(finding.source).startswith("rule:syntax.initial_")
    )

    # Then
    observed = [
        (finding.start, finding.end, finding.suggestion) for finding in findings
    ]
    assert observed == [(offset, offset, ",")]


@pytest.mark.parametrize(
    "text",
    (
        "jeśli pada wracam.",
        "JEŚLI PADA WRACAM.",
        "gDy ChCeSz PrZyJdŹ.",
        "KIEDY WRÓCISZ ZADZWOŃ.",
        "GDYBY PADAŁO ZOSTAŁBYM.",
    ),
)
def test_closed_conjunctions_preserve_case_variants(text: str) -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    findings = tuple(
        finding
        for finding in analyzer.analyze(text).issues
        if str(finding.source).startswith("rule:syntax.initial_")
    )

    # Then
    assert len(findings) == 1
    assert findings[0].original == ""
    assert findings[0].suggestion == ","


@pytest.mark.parametrize(
    "text",
    (
        "Jeśli pada, wracam.",
        "Jeśli pada.",
        "Jeśli chcesz to przyjdź.",
        "„Jeśli pada wracam.”",
        '"Jeśli pada wracam."',
        "Fraza `Jeśli pada wracam` jest przykładem.",
        "Choć pada wracam.",
        "Wracam, jeśli pada.",
        "Jeśli pada i wieje zostaję.",
        "Jeżeli możesz zostań.",
        "Jeśli pada wracam. Potem odpoczywam.",
    ),
)
def test_unsafe_or_out_of_scope_contexts_abstain(text: str) -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    findings = analyzer.analyze(
        text, options=AnalysisOptions(categories={Category.SYNTAX})
    ).issues

    # Then
    assert all(
        not str(finding.source).startswith("rule:syntax.initial_")
        for finding in findings
    )
