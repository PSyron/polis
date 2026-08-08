"""One closed, review-only morphology-backed government rule."""

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

_PATTERN: Final = re.compile(r"Potrzebuję (?P<governed>pomoc)\.\Z")
_BEHAVIOR_VERSION: Final = (
    "inflection-government-potrzebowac-pomoc/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)


@dataclass(frozen=True, slots=True)
class _GovernedFormRow:
    governor_surface: str
    governor_lemma: str
    governor_tags: frozenset[str]
    governed_surface: str
    governed_lemma: str
    governed_tags: frozenset[str]
    target_tag: str
    target_form: str


_GOVERNED_FORMS: Final = (
    _GovernedFormRow(
        governor_surface="Potrzebuję",
        governor_lemma="potrzebować",
        governor_tags=frozenset({"fin:sg:pri:imperf"}),
        governed_surface="pomoc",
        governed_lemma="pomoc",
        governed_tags=frozenset({"subst:sg:nom:f", "subst:sg:acc:f"}),
        target_tag="subst:sg:gen:f",
        target_form="pomocy",
    ),
)


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
        return _BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        match = _PATTERN.fullmatch(text)
        if match is None or self._provider is None:
            return ()
        replacement = _governed_form_replacement(self._provider)
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


def _governed_form_replacement(provider: _QualifiedMorfeusz) -> str | None:
    if provider.identity != _qualified_identity():
        return None
    (row,) = _GOVERNED_FORMS
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


__all__ = ["InflectionGovernmentPotrzebowacPomocRule"]
