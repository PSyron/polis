from __future__ import annotations

import re
import unicodedata
from typing import Final

from polis.evaluation.calibration_json import fail

_EMAIL: Final = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
_URL: Final = re.compile(r"https?://\S+", re.IGNORECASE)
_PLACEHOLDER: Final = re.compile(
    r"(?:<|\[)(?:person|name|email|phone|address|pesel|nip|regon)(?:>|\])",
    re.IGNORECASE,
)
_MAX_PLAINTEXT_CHARS: Final = 4096


def _normalize_separators(value: str) -> str:
    return "".join(
        ""
        if unicodedata.category(character) in {"Cf", "Mn", "Me"}
        else " "
        if character.isspace()
        else "-"
        if unicodedata.category(character) == "Pd" or character == "\u2212"
        else character
        for character in value
    )


def _digit_candidates(value: str) -> tuple[str, ...]:
    candidates: list[str] = []
    digits: list[str] = []
    overflow = False

    def finish() -> None:
        nonlocal overflow
        if not overflow and 9 <= len(digits) <= 19:
            candidates.append("".join(digits))
        digits.clear()
        overflow = False

    for character in value:
        if character.isdecimal():
            if len(digits) < 19 and not overflow:
                digits.append(str(unicodedata.decimal(character)))
            else:
                digits.clear()
                overflow = True
        elif character.isalnum():
            finish()
    finish()
    return tuple(candidates)


def _checksum_matches(digits: str, weights: tuple[int, ...]) -> bool:
    checksum = (
        sum(
            int(value) * weight
            for value, weight in zip(digits[:-1], weights, strict=True)
        )
        % 11
    )
    expected = 0 if checksum == 10 else checksum
    return expected == int(digits[-1])


def _valid_pesel(digits: str) -> bool:
    if len(digits) != 11:
        return False
    weights = (1, 3, 7, 9, 1, 3, 7, 9, 1, 3)
    checksum = (
        10
        - sum(
            int(value) * weight
            for value, weight in zip(digits[:-1], weights, strict=True)
        )
        % 10
    ) % 10
    return checksum == int(digits[-1])


def _valid_nip(digits: str) -> bool:
    if len(digits) != 10:
        return False
    weights = (6, 5, 7, 2, 3, 4, 5, 6, 7)
    checksum = (
        sum(
            int(value) * weight
            for value, weight in zip(digits[:-1], weights, strict=True)
        )
        % 11
    )
    return checksum != 10 and checksum == int(digits[-1])


def _valid_regon(digits: str) -> bool:
    if len(digits) == 9:
        return _checksum_matches(digits, (8, 9, 2, 3, 4, 5, 6, 7))
    if len(digits) == 14:
        return _checksum_matches(digits, (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8))
    return False


def _valid_payment_card(digits: str) -> bool:
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    parity = len(digits) % 2
    for index, value in enumerate(digits):
        digit = int(value)
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def _valid_polish_phone(digits: str) -> bool:
    return (
        len(digits) == 9
        or (len(digits) == 11 and digits.startswith("48"))
        or (len(digits) == 13 and digits.startswith("0048"))
    )


def contains_sensitive_value(value: str) -> bool:
    if len(value) > _MAX_PLAINTEXT_CHARS:
        fail("plaintext value exceeds the frozen 4096-character scan limit")
    normalized = _normalize_separators(value)
    if any(
        pattern.search(normalized) is not None
        for pattern in (_EMAIL, _URL, _PLACEHOLDER)
    ):
        return True
    for digits in _digit_candidates(value):
        if (
            _valid_polish_phone(digits)
            or _valid_pesel(digits)
            or _valid_nip(digits)
            or _valid_regon(digits)
            or _valid_payment_card(digits)
        ):
            return True
    return False
