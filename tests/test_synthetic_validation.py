from __future__ import annotations

from dataclasses import dataclass

import pytest

from polis.evaluation._synthetic_corpus_validation import (
    assert_source_disjoint,
    split_source_disjoint,
    validate_single_edit,
)


@dataclass(frozen=True, slots=True)
class _Item:
    source_case_id: str
    correct_text: str


def test_validate_single_edit_uses_the_declared_span() -> None:
    incorrect = "Kontekst wybiera formę „najstarsze kawy”."
    correct = "Kontekst wybiera formę „starym kawy”."
    start = incorrect.index("najstarsze")

    assert validate_single_edit(
        incorrect,
        correct,
        start=start,
        end=start + len("najstarsze"),
        original="najstarsze",
        suggestion="starym",
    )
    assert not validate_single_edit(
        incorrect,
        correct,
        start=start,
        end=start + len("najstarsze") - 1,
        original="najstarsze",
        suggestion="starym",
    )


def test_validate_single_edit_accepts_zero_width_insertions() -> None:
    incorrect = "Jeśli pada zostaję w domu."
    correct = "Jeśli pada, zostaję w domu."

    assert validate_single_edit(
        incorrect,
        correct,
        start=10,
        end=10,
        original="",
        suggestion=",",
    )


def test_validate_single_edit_rejects_out_of_range_and_wrong_reconstruction() -> None:
    assert not validate_single_edit(
        "Ala.",
        "Ala.",
        start=0,
        end=3,
        original="Ala",
        suggestion="Ala",
    )
    assert not validate_single_edit(
        "Ala.",
        "Ola.",
        start=99,
        end=99,
        original="",
        suggestion="O",
    )
    assert not validate_single_edit(
        "Ala ma kota.",
        "Ola ma psa.",
        start=0,
        end=3,
        original="Ala",
        suggestion="Ola",
    )


def test_split_source_disjoint_is_deterministic_and_blocks_case_or_text_leakage() -> (
    None
):
    items = (
        _Item("case-a", "To zdanie."),
        _Item("case-a", "To zdanie."),
        _Item("case-b", "Inny tekst."),
        _Item("case-c", "Jeszcze inny tekst."),
        _Item("case-d", "Czwarty tekst."),
    )

    first = split_source_disjoint(items, development_ratio=0.4, seed=426)
    second = split_source_disjoint(items, development_ratio=0.4, seed=426)

    assert first == second
    assert first.development
    assert first.test
    assert {item.source_case_id for item in first.development}.isdisjoint(
        item.source_case_id for item in first.test
    )
    assert {item.correct_text for item in first.development}.isdisjoint(
        item.correct_text for item in first.test
    )


def test_assert_source_disjoint_reports_a_leakage_instead_of_hiding_it() -> None:
    with pytest.raises(ValueError, match="source-disjoint split leakage"):
        assert_source_disjoint(
            (_Item("case-a", "To zdanie."),),
            (_Item("case-a", "Inny tekst."),),
        )

    with pytest.raises(ValueError, match="source-disjoint split leakage"):
        assert_source_disjoint(
            (_Item("case-a", "To zdanie."),),
            (_Item("case-b", "To zdanie."),),
        )
