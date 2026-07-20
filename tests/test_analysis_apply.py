from __future__ import annotations

import pytest

from polis import (
    CorrectionConflictError,
    CorrectionSelectionError,
    UncorrectableFindingError,
    UnknownFindingError,
)
from polis.core import (
    AnalysisResult,
    Category,
    Confidence,
    Finding,
    Source,
)
from polis.core.models import Severity


def make_finding(
    *, start: int, end: int, suggestion: str | None, original: str
) -> Finding:
    return Finding.create(
        category=Category.STYLE,
        severity=Severity.ERROR,
        message="m",
        explanation="e",
        original=original,
        suggestion=suggestion,
        start=start,
        end=end,
        confidence=Confidence(0.9),
        source=Source.parse("rule:style"),
    )


def test_apply_selected_findings_is_deterministic_of_input_order() -> None:
    text = "Ala ma kota."
    first = make_finding(start=0, end=3, original="Ala", suggestion="Ela")
    second = make_finding(start=7, end=11, original="kota", suggestion="psa")

    result = AnalysisResult(text=text, issues=(first, second))

    expected = "Ela ma psa."
    assert result.apply((first.id, second.id)) == expected
    assert result.apply((second.id, first.id)) == expected


def test_apply_rejects_unknown_or_duplicate_issue_ids() -> None:
    text = "ABC"
    first = make_finding(start=0, end=1, original="A", suggestion="B")
    result = AnalysisResult(text=text, issues=(first,))

    with pytest.raises(UnknownFindingError) as error:
        result.apply(("missing",))
    assert error.value.code == "correction.unknown_finding"
    assert error.value.context["finding_ids"] == "missing"

    with pytest.raises(UnknownFindingError):
        result.apply((first.id, first.id))


def test_apply_rejects_uncorrectable_and_conflicting_selection() -> None:
    text = "ABC"
    missing_suggestion = make_finding(start=0, end=1, original="A", suggestion=None)
    first = make_finding(start=0, end=1, original="A", suggestion="B")
    second = make_finding(start=1, end=1, original="", suggestion=" ")
    result = AnalysisResult(text=text, issues=(missing_suggestion, first, second))

    with pytest.raises(UncorrectableFindingError) as error:
        result.apply((missing_suggestion.id,))
    assert error.value.code == "correction.uncorrectable_finding"

    with pytest.raises(CorrectionConflictError) as error:
        result.apply((first.id, second.id))
    assert error.value.code == "correction.conflict"


def test_apply_raises_correction_selection_error_on_stale_finding_span() -> None:
    text = "Ala"
    first = make_finding(start=0, end=1, original="A", suggestion="B")
    result = AnalysisResult(text=text, issues=(first,))

    # Simulate a stale result where the stored issue no longer matches text.
    object.__setattr__(result, "text", "xxx")

    with pytest.raises(CorrectionSelectionError):
        result.apply((first.id,))
