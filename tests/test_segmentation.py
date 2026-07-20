from __future__ import annotations

import json
from pathlib import Path

import pytest

from polis.segmentation import (
    Paragraph,
    Sentence,
    segment_paragraphs,
    segment_sentences,
)


def _load_case_texts() -> list[str]:
    path = Path(__file__).with_name("fixtures").joinpath("segmentation_cases.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [item["text"] for item in payload["cases"]]


@pytest.mark.parametrize("text", _load_case_texts())
def test_segments_preserve_offsets_for_dataset_cases(text: str) -> None:
    paragraphs = segment_paragraphs(text)
    sentences = segment_sentences(text)

    assert all(seg.start <= seg.end <= len(text) for seg in (*paragraphs, *sentences))

    assert "".join(seg.text for seg in paragraphs) == text
    assert "".join(seg.text for seg in sentences) == text
    assert all(
        text[seg.start : seg.end] == seg.text for seg in (*paragraphs, *sentences)
    )

    assert all(sentence.start <= sentence.end for sentence in sentences)


def test_blank_lines_create_multiple_paragraphs_and_sentence_segments() -> None:
    text = "Pierwsze zdanie.\n\nDrugie zdanie.\n\n\nTrzecie zdanie."

    paragraphs = segment_paragraphs(text)
    assert len(paragraphs) == 3
    assert paragraphs[0].text == "Pierwsze zdanie.\n\n"
    assert paragraphs[1].text == "Drugie zdanie.\n\n\n"
    assert paragraphs[2].text == "Trzecie zdanie."

    sentences = segment_sentences(text)
    assert [segment.text for segment in sentences] == [
        "Pierwsze zdanie.\n\n",
        "Drugie zdanie.\n\n\n",
        "Trzecie zdanie.",
    ]


def test_abbreviation_periods_do_not_create_sentence_splits() -> None:
    text = "To np. przykład, czyli m.in. pierwszy przypadek. Kolejne zdanie."

    sentences = segment_sentences(text)

    assert len(sentences) == 2
    assert sentences[0].text == "To np. przykład, czyli m.in. pierwszy przypadek."
    assert sentences[1].text == " Kolejne zdanie."


def test_punctuation_and_quotes_are_covered_without_offset_drift() -> None:
    text = '"Tak?" powiedziała Ola! Czy to prawda?'

    sentences = segment_sentences(text)

    assert len(sentences) == 3
    assert sentences[0].text == '"Tak?"'
    assert text[sentences[0].start : sentences[0].end] == sentences[0].text
    assert sentences[1].text == " powiedziała Ola!"
    assert sentences[2].text == " Czy to prawda?"


def test_sentence_indices_cover_combining_character_boundaries() -> None:
    text = "Kobieta z e\u0301m."  # decomposed accent

    sentences = segment_sentences(text)

    assert len(sentences) == 1
    segment = sentences[0]
    assert segment.start == 0
    assert segment.end == len(text)
    assert text[segment.start : segment.end] == segment.text


def test_sentence_indices_cover_emoji_and_crlf_offsets() -> None:
    text = "Witaj 🙂.\r\nJaki to\u20ac test?\r\nKolejny."

    paragraphs = segment_paragraphs(text)
    sentences = segment_sentences(text)

    assert paragraphs[0].start == 0
    assert sentences[0].text == "Witaj 🙂."
    assert sentences[1].text == "\r\nJaki to\u20ac test?"
    assert sentences[2].text == "\r\nKolejny."

    for sentence in sentences:
        assert text[sentence.start : sentence.end] == sentence.text


def test_models_accept_expected_fields() -> None:
    paragraph = Paragraph(start=0, end=5, text="tekst")
    sentence = Sentence(start=0, end=5, text="tekst")

    assert paragraph.start == 0
    assert paragraph.text == "tekst"
    assert sentence.end == 5
    assert sentence.text == "tekst"
