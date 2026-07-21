"""Experimental strict contract for model-produced corrected text."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass(frozen=True)
class TextEdit:
    """One non-overlapping replacement expressed against the original text."""

    start: int
    end: int
    original: str
    suggestion: str


def validate_corrected_text_response(raw: str, *, source_text: str) -> str:
    """Return one corrected text value from the closed experimental JSON schema."""

    payload = json.loads(raw)
    if not isinstance(payload, dict) or set(payload) != {"corrected_text"}:
        raise ValueError("response must contain exactly corrected_text")
    corrected = payload["corrected_text"]
    if not isinstance(corrected, str):
        raise TypeError("corrected_text must be a string")
    if not isinstance(source_text, str):
        raise TypeError("source_text must be a string")
    return corrected


def derive_text_edits(source_text: str, corrected_text: str) -> tuple[TextEdit, ...]:
    """Derive deterministic non-overlapping edits from source to corrected text."""

    if not isinstance(source_text, str) or not isinstance(corrected_text, str):
        raise TypeError("source_text and corrected_text must be strings")
    if source_text != corrected_text and not (
        set(re.findall(r"\w{3,}", source_text, flags=re.UNICODE))
        & set(re.findall(r"\w{3,}", corrected_text, flags=re.UNICODE))
    ):
        raise ValueError("corrected_text must preserve source text")
    matcher = SequenceMatcher(a=source_text, b=corrected_text, autojunk=False)
    return tuple(
        TextEdit(
            start=source_start,
            end=source_end,
            original=source_text[source_start:source_end],
            suggestion=corrected_text[corrected_start:corrected_end],
        )
        for (
            tag,
            source_start,
            source_end,
            corrected_start,
            corrected_end,
        ) in matcher.get_opcodes()
        if tag != "equal"
    )


__all__ = ["TextEdit", "derive_text_edits", "validate_corrected_text_response"]
