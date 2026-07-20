from __future__ import annotations

import pytest

from polis import Confidence
from polis.core import Category, Finding, Source
from polis.core.models import Severity
from polis.correction import findings_conflict, validate_non_conflicting_corrections


def make_finding(*, start: int, end: int, suggestion: str | None = "x") -> Finding:
    original = "" if start == end else "x" * (end - start)
    if suggestion is None:
        normalized_suggestion = None
    elif suggestion == original:
        normalized_suggestion = "y"
    else:
        normalized_suggestion = suggestion

    return Finding.create(
        category=Category.SPELLING,
        severity=Severity.ERROR,
        message="m",
        explanation="e",
        original=original,
        suggestion=normalized_suggestion,
        start=start,
        end=end,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test"),
    )


@pytest.mark.parametrize(
    "first,second,expected",
    [
        (make_finding(start=1, end=4), make_finding(start=2, end=5), True),
        (make_finding(start=1, end=3), make_finding(start=3, end=5), False),
        (make_finding(start=2, end=2), make_finding(start=0, end=3), True),
        (make_finding(start=2, end=2), make_finding(start=2, end=4), True),
        (make_finding(start=2, end=2), make_finding(start=4, end=6), False),
        (make_finding(start=2, end=2), make_finding(start=5, end=5), False),
        (make_finding(start=4, end=4), make_finding(start=4, end=4), True),
    ],
)
def test_pair_conflicts_match_contract(
    first: Finding, second: Finding, expected: bool
) -> None:
    assert findings_conflict(first, second) == expected


def test_conflict_validator_accepts_compatible_findings() -> None:
    first = make_finding(start=0, end=1)
    second = make_finding(start=1, end=2)

    validate_non_conflicting_corrections((first, second))


def test_conflict_validator_rejects_conflicting_findings() -> None:
    first = make_finding(start=0, end=1)
    second = make_finding(start=0, end=0)

    with pytest.raises(ValueError, match="conflicting findings selected"):
        validate_non_conflicting_corrections((first, second))
