"""Text segmentation and original-character offset mapping."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PARAGRAPH_SEPARATOR = re.compile(r"(?:\r?\n[ \t]*\r?\n+)")
_TRAILING_SENTENCE_MARKS = frozenset("'\"”’»)]}")
_ABBREVIATIONS = frozenset(
    {
        "al",
        "doc",
        "dr",
        "itd",
        "itp",
        "m.in",
        "miedzy",
        "nr",
        "np",
        "prof",
        "r",
        "s",
        "tj",
        "tzn",
        "ul",
    }
)


@dataclass(frozen=True, slots=True)
class Segment:
    """One immutable text segment represented with stable offsets."""

    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class Paragraph(Segment):
    """Stable paragraph slice in the original text."""


@dataclass(frozen=True, slots=True)
class Sentence(Segment):
    """Stable sentence slice in the original text."""


def segment_paragraphs(text: str) -> tuple[Paragraph, ...]:
    """Segment text into paragraph-sized spans using blank-line boundaries."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text:
        return ()

    paragraphs: list[Paragraph] = []
    segment_start = 0

    for separator in _PARAGRAPH_SEPARATOR.finditer(text):
        segment_end = separator.end()
        if segment_end > segment_start:
            paragraphs.append(
                Paragraph(
                    start=segment_start,
                    end=segment_end,
                    text=text[segment_start:segment_end],
                )
            )
        segment_start = segment_end

    if segment_start < len(text):
        paragraphs.append(
            Paragraph(
                start=segment_start,
                end=len(text),
                text=text[segment_start:],
            )
        )
    elif not paragraphs:
        paragraphs.append(
            Paragraph(
                start=0,
                end=0,
                text="",
            )
        )

    return tuple(paragraphs)


def segment_sentences(text: str) -> tuple[Sentence, ...]:
    """Segment text into sentence-sized spans using simple delimiter heuristics."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    if not text:
        return ()

    sentences: list[Sentence] = []
    for paragraph in segment_paragraphs(text):
        if not paragraph.text:
            continue

        local_start = 0
        paragraph_text = paragraph.text
        i = 0
        while i < len(paragraph_text):
            if _is_sentence_boundary(paragraph_text, i):
                boundary_end = _consume_sentence_run(paragraph_text, i)
                boundary_end = _consume_trailing_marks(paragraph_text, boundary_end)
                boundary_end = _consume_blank_line_ending(paragraph_text, boundary_end)
                if boundary_end > local_start:
                    sentences.append(
                        Sentence(
                            start=paragraph.start + local_start,
                            end=paragraph.start + boundary_end,
                            text=text[
                                paragraph.start + local_start : paragraph.start
                                + boundary_end
                            ],
                        )
                    )
                local_start = boundary_end
                i = boundary_end
                continue
            i += 1

        if local_start < len(paragraph_text):
            start = paragraph.start + local_start
            end = paragraph.start + len(paragraph_text)
            sentences.append(Sentence(start=start, end=end, text=text[start:end]))

    return tuple(sentences)


def _is_sentence_boundary(text: str, index: int) -> bool:
    """Return True if text[index] ends a sentence by a deterministic heuristic."""

    if text[index] not in ".!?":
        return False

    if text[index] == "." and _is_abbreviation_token(text, index):
        return False

    if _is_decimal_point(text, index):
        return False

    boundary_end = _consume_sentence_run(text, index)
    return _can_split_after(text, boundary_end)


def _can_split_after(text: str, index: int) -> bool:
    """Return whether a sentence can be split at ``index``."""

    if index >= len(text):
        return True
    next_char = text[index]
    if next_char.isspace():
        return True
    if next_char in _TRAILING_SENTENCE_MARKS:
        return _can_split_after(text, index + 1)
    return False


def _consume_sentence_run(text: str, index: int) -> int:
    """Consume a run of consecutive sentence-ending punctuation characters."""

    end = index + 1
    while end < len(text) and text[end] in ".!?":
        end += 1
    return end


def _consume_trailing_marks(text: str, start: int) -> int:
    """Consume closing punctuation that belongs to the sentence boundary."""

    end = start
    while end < len(text) and text[end] in _TRAILING_SENTENCE_MARKS:
        end += 1
    return end


def _consume_blank_line_ending(text: str, start: int) -> int:
    """Consume a blank-line separator when it follows a sentence boundary."""

    if start >= len(text):
        return start

    end = start
    while end < len(text) and text[end] in "\r\n":
        end += 1

    if end == start:
        return start

    if _count_line_breaks(text[start:end]) >= 2:
        return end
    return start


def _count_line_breaks(text: str) -> int:
    """Count logical line breaks in a ``\\r\\n`` / ``\\n`` sequence."""

    count = 0
    i = 0
    while i < len(text):
        if text[i] == "\r":
            if i + 1 < len(text) and text[i + 1] == "\n":
                count += 1
                i += 2
                continue
            count += 1
            i += 1
            continue
        if text[i] == "\n":
            count += 1
        i += 1
    return count


def _is_decimal_point(text: str, index: int) -> bool:
    """Return True when a dot should not be interpreted as sentence punctuation."""

    if text[index] != ".":
        return False
    has_left_digit = index > 0 and text[index - 1].isdigit()
    has_right_digit = index + 1 < len(text) and text[index + 1].isdigit()
    return has_left_digit and has_right_digit


def _is_abbreviation_token(text: str, index: int) -> bool:
    """Return True if the punctuation at ``index`` is part of a known abbreviation."""

    start = index - 1
    end = index + 1

    while start >= 0 and (text[start].isalnum() or text[start] == "."):
        start -= 1
    while end < len(text) and (text[end].isalnum() or text[end] == "."):
        end += 1

    token = text[start + 1 : end].rstrip(".").lower()
    if not token:
        return False
    return token in _ABBREVIATIONS


__all__ = [
    "Paragraph",
    "Sentence",
    "Segment",
    "segment_paragraphs",
    "segment_sentences",
]
