from __future__ import annotations

from collections.abc import Callable

import pytest
from tests.generative import (
    UNICODE_FAMILIES,
    assert_structural_invariant,
    generate_unicode_text_cases,
)

from polis.segmentation import Segment, segment_paragraphs, segment_sentences


def test_generated_paragraph_spans_reconstruct_the_original_source() -> None:
    _assert_generated_segmentation(kind="paragraph", segmenter=segment_paragraphs)


def test_generated_sentence_spans_reconstruct_the_original_source() -> None:
    _assert_generated_segmentation(kind="sentence", segmenter=segment_sentences)


def test_generated_segmentation_failures_hide_source_text() -> None:
    case = generate_unicode_text_cases()[1]

    with pytest.raises(AssertionError) as error:
        _assert_generated_segmentation(kind="paragraph", segmenter=lambda _: ())

    message = str(error.value)
    assert "segmentation.paragraph.coverage" in message
    assert str(case.replay) in message
    assert case.text not in message


def _assert_generated_segmentation(
    *, kind: str, segmenter: Callable[[str], tuple[Segment, ...]]
) -> None:
    cases = generate_unicode_text_cases()
    assert_structural_invariant(
        frozenset().union(*(case.families for case in cases)) == UNICODE_FAMILIES,
        invariant=f"segmentation.{kind}.families",
        replay=cases[-1].replay,
    )

    for case in cases:
        segments = segmenter(case.text)
        next_start = 0
        for segment in segments:
            assert_structural_invariant(
                0 <= segment.start <= segment.end <= len(case.text),
                invariant=f"segmentation.{kind}.bounds",
                replay=case.replay,
            )
            assert_structural_invariant(
                segment.start == next_start,
                invariant=f"segmentation.{kind}.contiguous",
                replay=case.replay,
            )
            assert_structural_invariant(
                segment.text == case.text[segment.start : segment.end],
                invariant=f"segmentation.{kind}.slice",
                replay=case.replay,
            )
            next_start = segment.end

        assert_structural_invariant(
            next_start == len(case.text),
            invariant=f"segmentation.{kind}.coverage",
            replay=case.replay,
        )
        assert_structural_invariant(
            "".join(segment.text for segment in segments) == case.text,
            invariant=f"segmentation.{kind}.reconstruction",
            replay=case.replay,
        )
