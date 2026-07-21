from __future__ import annotations

import json

import pytest

from polis.llm.corrected_text import (
    FiniteCandidate,
    build_inflection_candidate_prompt_request,
    build_proposal_verifier_prompt_request,
    build_specialist_corrected_text_prompt,
    build_specialist_corrected_text_prompt_request,
    derive_text_edits,
    validate_candidate_selection_response,
    validate_corrected_text_response,
    validate_verifier_response,
)


def test_specialist_request_keeps_text_as_input_data_and_tracks_prompt_version() -> (
    None
):
    request = build_specialist_corrected_text_prompt_request(
        "Maria powiedziała że wróci.", focus="punctuation"
    )

    assert request.protocol_id == "specialist-corrected-text"
    assert request.protocol_version == "1.0"
    assert request.messages[0]["role"] == "system"
    assert request.messages[1]["role"] == "user"
    assert request.response_schema_version == 1

    system_content = request.messages[0]["content"]
    user_content = request.messages[1]["content"]

    assert "<TEXT_START>" in user_content
    assert "<TEXT_END>" in user_content
    assert "Maria powiedziała że wróci." in user_content
    assert "<INPUT_JSON_START>" in user_content
    assert "</INPUT_JSON_END>" in user_content
    assert "interpunkcję" in system_content
    assert "Zwróć wyłącznie JSON" in system_content
    assert (
        request.prompt_hash
        == build_specialist_corrected_text_prompt_request(
            "Maria powiedziała że wróci.", focus="punctuation"
        ).prompt_hash
    )
    assert request.max_input_chars == 8_192
    assert request.max_output_chars == 2_048


def test_candidate_request_only_contains_candidate_ids_and_delimited_input() -> None:
    request = build_inflection_candidate_prompt_request(
        "Jacek zobaczył Kasię.",
        candidates=(
            FiniteCandidate("c1", 0, 5, "Jacek", None, ("nominative",)),
            FiniteCandidate("c2", 15, 20, "Kasia", "Kasia", ("accusative",)),
        ),
    )

    user_content = request.messages[1]["content"]
    payload = json.loads(user_content.split("\n")[4])

    assert request.protocol_id == "specialist-candidate-selection"
    assert payload["candidates"][0]["candidate_id"] == "c1"
    assert payload["candidates"][1]["candidate_id"] == "c2"
    assert len(payload["candidates"]) == 2
    assert payload["candidates"][0]["start"] == 0
    assert payload["candidates"][1]["start"] == 15
    assert request.response_schema_version == 1


def test_verifier_request_marks_source_and_proposal_as_data() -> None:
    request = build_proposal_verifier_prompt_request(
        "Gdzie jest Ania?",
        "Gdzie jest Anka?",
    )

    user_content = request.messages[1]["content"]
    marker_start = user_content.index("<TEXT_START>") + len("<TEXT_START>")
    marker_end = user_content.index("<TEXT_END>")
    payload = json.loads(user_content[marker_start:marker_end].strip())

    assert request.protocol_id == "specialist-proposal-verifier"
    assert payload["source"] == "Gdzie jest Ania?"
    assert payload["proposal"] == "Gdzie jest Anka?"


def test_compatibility_prompt_view_contains_expected_sections() -> None:
    prompt = build_specialist_corrected_text_prompt(
        "Maria powiedziała że wróci.",
        focus="syntax",
    )

    assert "[system]" in prompt
    assert "[user]" in prompt
    assert "Przykład:" in prompt
    assert '{"corrected_text"' in prompt


def test_requests_reject_excessive_input_length() -> None:
    too_long = "a" * 8_193

    with pytest.raises(ValueError, match="exceeds maximum allowed input size"):
        build_specialist_corrected_text_prompt_request(too_long, focus="syntax")
    with pytest.raises(ValueError, match="exceeds maximum allowed input size"):
        build_inflection_candidate_prompt_request(
            too_long,
            candidates=(FiniteCandidate("c1", 0, 1, "a"),),
        )
    with pytest.raises(ValueError, match="exceeds maximum allowed input size"):
        build_proposal_verifier_prompt_request(too_long, "ok")
    with pytest.raises(ValueError, match="exceeds maximum allowed output size"):
        build_proposal_verifier_prompt_request("ok", too_long)


def test_validate_corrected_text_response_requires_exact_schema() -> None:
    corrected = validate_corrected_text_response(
        '{"corrected_text":"Żeby jutro, powiem o tym."}',
        source_text="Zeby jutro,powiem o tym.",
    )

    assert corrected == "Żeby jutro, powiem o tym."

    with pytest.raises(ValueError, match="exactly"):
        validate_corrected_text_response(
            '{"correction":"Poprawne zdanie."}', source_text="Poprawne zdanie."
        )
    with pytest.raises(ValueError, match="exactly"):
        validate_corrected_text_response(
            '{"corrected_text":"Poprawne zdanie.","note":"extra"}',
            source_text="Poprawne zdanie.",
        )


def test_validate_corrected_text_response_rejects_oversized_output() -> None:
    oversized = "a" * 2_049
    source = "Ala ma kota"

    with pytest.raises(ValueError, match="maximum allowed output size"):
        validate_corrected_text_response(
            f'{{"corrected_text":"{oversized}"}}',
            source_text=source,
        )


def test_validate_corrected_text_response_rejects_model_broadcasts() -> None:
    with pytest.raises(ValueError, match="preserve source content"):
        validate_corrected_text_response(
            '{"corrected_text":"Niezwiązany tekst bez łączenia."}',
            source_text="Ala ma kota.",
        )

    with pytest.raises(ValueError, match="broad rewrite"):
        validate_corrected_text_response(
            '{"corrected_text":"Ela kupiła kota i psa, a wczoraj poszli do domu."}',
            source_text="Ala ma kota i psa w parku.",
        )


def test_validate_candidate_selection_response_accepts_unchanged_or_known_id_only() -> (
    None
):
    candidate_ids = ("c1", "c2")

    assert (
        validate_candidate_selection_response(
            '{"unchanged":true}',
            candidate_ids=candidate_ids,
        )
        is None
    )
    assert (
        validate_candidate_selection_response(
            '{"candidate_id":"c2"}',
            candidate_ids=candidate_ids,
        )
        == "c2"
    )

    with pytest.raises(
        ValueError,
        match="candidate_id is not in the supplied candidate list",
    ):
        validate_candidate_selection_response(
            '{"candidate_id":"c3"}',
            candidate_ids=candidate_ids,
        )
    with pytest.raises(ValueError, match="candidate response must contain exactly"):
        validate_candidate_selection_response(
            '{"candidate":"c1"}',
            candidate_ids=candidate_ids,
        )
    with pytest.raises(TypeError, match="candidate_id must be a string"):
        validate_candidate_selection_response(
            '{"candidate_id":123}',
            candidate_ids=candidate_ids,
        )


def test_validate_verifier_response_only_accepts_decision() -> None:
    assert validate_verifier_response('{"decision":"accept"}') is True
    assert validate_verifier_response('{"decision":"reject"}') is False

    with pytest.raises(ValueError, match="accept or reject"):
        validate_verifier_response('{"decision":"skip"}')
    with pytest.raises(ValueError, match="must contain exactly decision"):
        validate_verifier_response('{"decision":"accept","notes":"x"}')


def test_derive_text_edits_preserves_unicode_offsets_and_can_protect_names() -> None:
    edits = derive_text_edits(
        "Zeby jutro,powiem o tym.",
        "Żeby jutro, powiem o tym.",
    )
    actual = [(edit.start, edit.end, edit.original, edit.suggestion) for edit in edits]

    assert actual == [
        (0, 1, "Z", "Ż"),
        (11, 11, "", " "),
    ]

    with pytest.raises(ValueError, match="changed an apparently protected token"):
        derive_text_edits(
            "Janina odwiedziła Annę Kowalską.",
            "Janina odwiedziła Anię Nowak.",
            protect_proper_tokens=True,
        )

    assert derive_text_edits(
        "Janina odwiedziła Annę.",
        "Janina odwiedziła Annę",
        protect_proper_tokens=True,
    )


def test_derive_text_edits_rejects_private_text_in_errors() -> None:
    with pytest.raises(ValueError, match="preserve source content") as exc_info:
        derive_text_edits("Ala ma kota.", "Niezgodny tekst absolutnie inny.")

    assert "Ala" not in str(exc_info.value)
    assert "Niezgodny" not in str(exc_info.value)
