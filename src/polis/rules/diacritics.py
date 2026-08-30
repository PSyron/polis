from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)
from polis.rules._morfeusz import _QualifiedMorfeusz
from polis.rules.spelling import should_abstain_literal_context

_TOKEN_PATTERN: Final = re.compile(r"(?<!\w)[^\W\d_]+(?!\w)")
_MAX_REPLACEABLE_POSITIONS: Final = 4
_POLISH_DIACRITIC_CHARACTERS: Final = frozenset("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
_DIACRITIC_VARIANTS: Final[Mapping[str, tuple[str, ...]]] = MappingProxyType(
    {
        "a": ("ą",),
        "c": ("ć",),
        "e": ("ę",),
        "l": ("ł",),
        "n": ("ń",),
        "o": ("ó",),
        "s": ("ś",),
        "z": ("ź", "ż"),
    }
)
_SOURCE: Final = Source(SourceKind.RULE, "spelling.diacritics_restore")
_OPERATION: Final = "replace.diacritics_restore"
_BEHAVIOR_VERSION: Final = "spelling-diacritics-restore/1.0"


def _diacritic_candidates(token: str) -> tuple[str, ...]:
    if not token.isalpha():
        return ()
    choices: list[tuple[str, ...]] = []
    replaceable_positions = 0
    for character in token:
        if not character.isascii() and character not in _POLISH_DIACRITIC_CHARACTERS:
            return ()
        variants = _DIACRITIC_VARIANTS.get(character.casefold())
        if variants is None:
            choices.append((character,))
            continue
        replaceable_positions += 1
        if replaceable_positions > _MAX_REPLACEABLE_POSITIONS:
            return ()
        if character.isupper():
            choices.append((character, *(variant.upper() for variant in variants)))
        else:
            choices.append((character, *variants))
    if replaceable_positions == 0:
        return ()

    variants = ("",)
    for options in choices:
        variants = tuple(prefix + option for prefix in variants for option in options)
    return tuple(variant for variant in variants if variant != token)


def _minimal_change(
    token: str, suggestion: str, start: int
) -> tuple[str, str, int, int]:
    if len(token) != len(suggestion):
        return token, suggestion, start, start + len(token)
    changes = tuple(
        index
        for index, (original, replacement) in enumerate(
            zip(token, suggestion, strict=True)
        )
        if original != replacement
    )
    if len(changes) == 1:
        index = changes[0]
        return token[index], suggestion[index], start + index, start + index + 1
    return token, suggestion, start, start + len(token)


class SpellingDiacriticsRestoreRule:
    _CATEGORY = Category.SPELLING
    _provider: _QualifiedMorfeusz | None
    _excluded_surfaces: frozenset[str]

    def __init__(
        self,
        provider: _QualifiedMorfeusz | None,
        *,
        excluded_surfaces: frozenset[str] = frozenset(),
    ) -> None:
        self.source = _SOURCE
        self._provider = provider
        self._excluded_surfaces = excluded_surfaces

    @property
    def operation(self) -> str:
        return _OPERATION

    @property
    def behavior_version(self) -> str:
        return _BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if (
            self._provider is None
            or options.categories is not None
            and self._CATEGORY not in options.categories
        ):
            return ()

        findings: list[Finding] = []
        for match in _TOKEN_PATTERN.finditer(text):
            start, end = match.span()
            if should_abstain_literal_context(text, start, end):
                continue
            token = match.group(0)
            if token.casefold() in self._excluded_surfaces:
                continue
            candidates = _diacritic_candidates(token)
            if not candidates:
                continue
            suggestion = self._provider.diacritics_restore_replacement(
                token, candidates
            )
            if suggestion is None or suggestion == token:
                continue
            original, replacement, finding_start, finding_end = _minimal_change(
                token, suggestion, start
            )
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message=f"Brakuje znaków diakrytycznych w wyrazie „{token}”.",
                    explanation=(
                        f"Zakwalifikowany Morfeusz rozpoznaje dokładnie jedną "
                        f"poprawną wersję: „{suggestion}”."
                    ),
                    original=original,
                    suggestion=replacement,
                    start=finding_start,
                    end=finding_end,
                    confidence=Confidence(0.98),
                    source=self.source,
                )
            )
        return tuple(findings)


__all__ = ["SpellingDiacriticsRestoreRule"]
