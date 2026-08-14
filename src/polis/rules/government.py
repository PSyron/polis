"""Closed, review-only morphology-backed government rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
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
from polis.rules._morfeusz import (
    _analyses,
    _forms,
    _has_one_supported_lemma,
    _qualified_identity,
    _QualifiedMorfeusz,
    _tags_for_lemma,
)

_POTRZEBOWAC_PATTERN: Final = re.compile(r"Potrzebuję (?P<governed>pomoc)\.\Z")
_POTRZEBOWAC_BEHAVIOR_VERSION: Final = (
    "inflection-government-potrzebowac-pomoc/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
_SZUKAC_PATTERN: Final = re.compile(
    r"(?<!\w)(?P<phrase>(?P<governor>Szukam) (?P<governed>klucz))(?!\w)",
    re.IGNORECASE,
)
_SZUKAC_BEHAVIOR_VERSION: Final = (
    "inflection-government-szukac-klucz/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
_MENTION_WRAPPERS: Final = frozenset(
    {('"', '"'), ("`", "`"), ("„", "”"), ("“", "”"), ("«", "»")}
)
_CLOSING_QUOTES: Final = frozenset({'"', "”", "»", "'", "`"})


@dataclass(frozen=True, slots=True)
class _GovernedFormProp:
    governor_surface: str
    governor_lemma: str
    governor_tags: frozenset[str]
    governed_surface: str
    governed_lemma: str
    governed_tags: frozenset[str]
    target_tag: str
    target_form: str


_POTRZEBOWAC_FORM: Final = _GovernedFormProp(
    governor_surface="Potrzebuję",
    governor_lemma="potrzebować",
    governor_tags=frozenset({"fin:sg:pri:imperf"}),
    governed_surface="pomoc",
    governed_lemma="pomoc",
    governed_tags=frozenset({"subst:sg:nom:f", "subst:sg:acc:f"}),
    target_tag="subst:sg:gen:f",
    target_form="pomocy",
)
_SZUKAC_FORM: Final = _GovernedFormProp(
    governor_surface="szukam",
    governor_lemma="szukać",
    governor_tags=frozenset({"fin:sg:pri:imperf"}),
    governed_surface="klucz",
    governed_lemma="klucz",
    governed_tags=frozenset({"subst:sg:nom.acc:m3"}),
    target_tag="subst:sg:gen:m3",
    target_form="klucza",
)
_GOVERNED_FORMS: Final = (_POTRZEBOWAC_FORM,)


class InflectionGovernmentPotrzebowacPomocRule:
    """Review the one qualified `Potrzebuję pomoc.` government mismatch."""

    _CATEGORY = Category.INFLECTION

    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        self.source = Source(
            SourceKind.RULE,
            "inflection.government_potrzebowac_pomoc",
        )
        self._provider = provider
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.governed_form"

    @property
    def behavior_version(self) -> str:
        return _POTRZEBOWAC_BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        match = _POTRZEBOWAC_PATTERN.fullmatch(text)
        if match is None or self._provider is None:
            return ()
        replacement = _governed_form_replacement(self._provider, _POTRZEBOWAC_FORM)
        if replacement != "pomocy":
            return ()
        return (
            Finding.create(
                category=self._CATEGORY,
                severity=Severity.SUGGESTION,
                message="Niepoprawna forma dopełnienia po czasowniku „potrzebować”.",
                explanation=(
                    "W tej zamkniętej konstrukcji czasownik „Potrzebuję” wymaga formy "
                    "dopełniacza „pomocy”."
                ),
                original=match.group("governed"),
                suggestion=replacement,
                start=match.start("governed"),
                end=match.end("governed"),
                confidence=self._confidence,
                source=self.source,
            ),
        )


class InflectionGovernmentSzukacKluczRule:
    """Review the closed `Szukam klucz` government mismatch."""

    _CATEGORY = Category.INFLECTION

    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        self.source = Source(
            SourceKind.RULE,
            "inflection.government_szukac_klucz",
        )
        self._provider = provider
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.governed_form"

    @property
    def behavior_version(self) -> str:
        return _SZUKAC_BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        matches = tuple(
            match
            for match in _SZUKAC_PATTERN.finditer(text)
            if not _is_wrapped_mention(text, match.start("phrase"), match.end("phrase"))
        )
        if (
            not matches
            or self._provider is None
            or _governed_form_replacement(self._provider, _SZUKAC_FORM) != "klucza"
        ):
            return ()

        findings: list[Finding] = []
        for match in matches:
            original = match.group("governed")
            suggestion = _match_case(original, "klucza")
            if suggestion == original:
                continue
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Niepoprawna forma dopełnienia po czasowniku „szukać”.",
                    explanation=(
                        "W tej zamkniętej konstrukcji czasownik „Szukam” wymaga formy "
                        "dopełniacza „klucza”."
                    ),
                    original=original,
                    suggestion=suggestion,
                    start=match.start("governed"),
                    end=match.end("governed"),
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


def _governed_form_replacement(
    provider: _QualifiedMorfeusz, row: _GovernedFormProp
) -> str | None:
    if provider.identity != _qualified_identity():
        return None
    try:
        governor_analyses = _analyses(
            provider.backend.analyse(row.governor_surface),
            row.governor_surface,
        )
        governed_analyses = _analyses(
            provider.backend.analyse(row.governed_surface),
            row.governed_surface,
        )
        target_forms = _forms(
            provider.backend.generate(row.governed_lemma),
            lemma=row.governed_lemma,
            target_tag=row.target_tag,
        )
    except (KeyError, RuntimeError, TypeError, ValueError):
        return None
    if (
        not _has_one_supported_lemma(
            governor_analyses,
            lemma=row.governor_lemma,
            source_tags=row.governor_tags,
        )
        or not _has_one_supported_lemma(
            governed_analyses,
            lemma=row.governed_lemma,
            source_tags=row.governed_tags,
        )
        or _tags_for_lemma(governor_analyses, row.governor_lemma) != row.governor_tags
        or _tags_for_lemma(governed_analyses, row.governed_lemma) != row.governed_tags
        or target_forms != {row.target_form}
    ):
        return None
    return row.target_form


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
        if right in _CLOSING_QUOTES:
            return True
    return False


__all__ = [
    "InflectionGovernmentPotrzebowacPomocRule",
    "InflectionGovernmentSzukacKluczRule",
]
