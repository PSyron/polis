"""Closed review-only morphology-backed governed nominal-group rule."""

from __future__ import annotations

import re
from typing import Final

from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Source,
    SourceKind,
)
from polis.core.models import Severity
from polis.rules._morfeusz import _QualifiedMorfeusz

_PATTERN: Final = re.compile(
    r"(?<!\w)(?P<governor>przyglądam się) "
    r"(?P<span>(?P<adjective>nowy) (?P<noun>budynek))(?!\w)",
    re.IGNORECASE,
)
_BEHAVIOR_VERSION: Final = (
    "inflection-przygladac-sie-nowy-budynek/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
_MENTION_WRAPPERS: Final = frozenset(
    {('"', '"'), ("`", "`"), ("„", "”"), ("“", "”"), ("«", "»")}
)
_CLOSING_QUOTES: Final = frozenset({'"', "”", "»", "'", "`"})


class InflectionPrzygladacSieNowyBudynekRule:
    """Review the closed `przyglądam się nowy budynek` government mismatch."""

    _CATEGORY = Category.INFLECTION

    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        self.source = Source(
            SourceKind.RULE,
            "inflection.przygladac_sie_nowy_budynek",
        )
        self._provider = provider
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.governed_nominal_group"

    @property
    def behavior_version(self) -> str:
        return _BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        matches = tuple(
            match
            for match in _PATTERN.finditer(text)
            if not _is_wrapped_mention(text, match.start("span"), match.end("span"))
        )
        if (
            not matches
            or self._provider is None
            or self._provider.przygladac_sie_nowy_budynek_replacement()
            != "nowemu budynkowi"
        ):
            return ()

        findings: list[Finding] = []
        for match in matches:
            original = match.group("span")
            suggestion = _match_case(original, "nowemu budynkowi")
            if suggestion == original:
                continue
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message=(
                        "Niepoprawna forma grupy nominalnej po czasowniku "
                        "„przyglądać się”."
                    ),
                    explanation=(
                        "W tej zamkniętej konstrukcji czasownik „przyglądam się” "
                        "wymaga celownika „nowemu budynkowi”."
                    ),
                    original=original,
                    suggestion=suggestion,
                    start=match.start("span"),
                    end=match.end("span"),
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


def _match_case(reference: str, replacement: str) -> str:
    if reference.isupper():
        return replacement.upper()
    if reference[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _is_wrapped_mention(text: str, start: int, end: int) -> bool:
    if start <= 0 or end > len(text):
        return False
    if end < len(text):
        left = text[start - 1]
        right = text[end]
        if (left, right) in _MENTION_WRAPPERS:
            return True
        if left == "`":
            rest = text[end:]
            if rest.startswith("`") or rest.startswith("()`"):
                return True
        # Quoted multi-token mentions often leave a space before the span
        # and a closing quote immediately after it.
        if right in _CLOSING_QUOTES:
            return True
    return False


__all__ = ["InflectionPrzygladacSieNowyBudynekRule"]
