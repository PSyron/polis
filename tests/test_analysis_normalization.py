from __future__ import annotations

from polis.analysis import (
    deduplicate_findings,
    filter_findings,
    normalize_findings,
    prioritize_findings,
)
from polis.core import AnalysisOptions, Category, Confidence, Finding, Source
from polis.core.models import Severity


def make_finding(
    *,
    category: Category,
    source: str,
    start: int,
    end: int,
    original: str,
    suggestion: str,
    confidence: float,
) -> Finding:
    return Finding.create(
        category=category,
        severity=Severity.ERROR,
        message="msg",
        explanation="exp",
        original=original,
        suggestion=suggestion,
        start=start,
        end=end,
        confidence=Confidence(confidence),
        source=Source.parse(source),
    )


def test_filter_findings_by_category_and_confidence() -> None:
    findings = (
        make_finding(
            category=Category.SPELLING,
            source="rule:one",
            start=0,
            end=1,
            original="a",
            suggestion="b",
            confidence=0.9,
        ),
        make_finding(
            category=Category.AGREEMENT,
            source="rule:two",
            start=1,
            end=2,
            original="b",
            suggestion="c",
            confidence=0.4,
        ),
    )

    filtered = filter_findings(
        findings,
        options=AnalysisOptions(categories={Category.SPELLING}, minimum_confidence=0.8),
    )

    assert len(filtered) == 1
    assert filtered[0].category == Category.SPELLING


def test_deduplicate_findings_keeps_preferred_confidence() -> None:
    high = make_finding(
        category=Category.SYNTAX,
        source="rule:syntax",
        start=0,
        end=1,
        original="x",
        suggestion="y",
        confidence=0.95,
    )
    low = make_finding(
        category=Category.SYNTAX,
        source="rule:syntax",
        start=0,
        end=1,
        original="x",
        suggestion="y",
        confidence=0.2,
    )

    deduplicated = deduplicate_findings((low, high))

    assert len(deduplicated) == 1
    assert deduplicated[0] == high


def test_prioritize_findings_is_deterministic_and_stable() -> None:
    first = make_finding(
        category=Category.PUNCTUATION,
        source="rule:punct",
        start=7,
        end=8,
        original="x",
        suggestion="",
        confidence=0.6,
    )
    second = make_finding(
        category=Category.PUNCTUATION,
        source="rule:punct",
        start=0,
        end=1,
        original="x",
        suggestion="y",
        confidence=0.2,
    )
    third = make_finding(
        category=Category.PUNCTUATION,
        source="rule:punct",
        start=3,
        end=4,
        original="x",
        suggestion="y",
        confidence=0.8,
    )

    ordered = prioritize_findings((first, second, third))

    assert [item.start for item in ordered] == [0, 3, 7]


def test_normalize_findings_runs_filter_deduplicate_and_prioritize() -> None:
    keep = make_finding(
        category=Category.AGREEMENT,
        source="rule:agree",
        start=0,
        end=1,
        original="x",
        suggestion="y",
        confidence=0.92,
    )
    duplicate_low = make_finding(
        category=Category.AGREEMENT,
        source="rule:agree",
        start=0,
        end=1,
        original="x",
        suggestion="y",
        confidence=0.2,
    )
    out_of_range = make_finding(
        category=Category.STYLE,
        source="rule:other",
        start=2,
        end=3,
        original="y",
        suggestion="z",
        confidence=0.99,
    )

    normalized = normalize_findings(
        (out_of_range, duplicate_low, keep),
        options=AnalysisOptions(
            categories={Category.AGREEMENT}, minimum_confidence=0.5
        ),
    )

    assert normalized == (keep,)
