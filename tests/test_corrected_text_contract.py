from __future__ import annotations

import pytest

from polis.llm.corrected_text import (
    build_specialist_corrected_text_prompt,
    derive_text_edits,
    validate_corrected_text_response,
)


def test_specialist_prompt_uses_polish_focus_and_isolates_input_as_data() -> None:
    prompt = build_specialist_corrected_text_prompt(
        "Maria powiedziała że wróci.", focus="punctuation"
    )

    assert "Jesteś" in prompt
    assert "interpunkcję" in prompt
    assert "Przykład" in prompt
    assert "<TEKST_START>" in prompt
    assert "<TEKST_END>" in prompt
    assert '{"corrected_text"' in prompt


def test_validates_exact_corrected_text_json_contract() -> None:
    corrected = validate_corrected_text_response(
        '{"corrected_text":"Żeby jutro, powiem o tym."}',
        source_text="Zeby jutro,powiem o tym.",
    )

    assert corrected == "Żeby jutro, powiem o tym."


def test_rejects_extra_or_missing_corrected_text_fields() -> None:
    with pytest.raises(ValueError, match="exactly"):
        validate_corrected_text_response(
            '{"correction":"Poprawne zdanie."}', source_text="Poprawne zdanie."
        )
    with pytest.raises(ValueError, match="exactly"):
        validate_corrected_text_response(
            '{"corrected_text":"Poprawne zdanie.","note":"extra"}',
            source_text="Poprawne zdanie.",
        )


def test_derives_non_overlapping_edits_using_original_offsets() -> None:
    edits = derive_text_edits("Zeby jutro,powiem o tym.", "Żeby jutro, powiem o tym.")

    actual = [(edit.start, edit.end, edit.original, edit.suggestion) for edit in edits]

    assert actual == [
        (0, 1, "Z", "Ż"),
        (11, 11, "", " "),
    ]


def test_rejects_a_wholesale_rewrite_without_shared_source_text() -> None:
    with pytest.raises(ValueError, match="preserve source text"):
        derive_text_edits("Ala ma kota.", "Całkowicie inne zdanie.")
