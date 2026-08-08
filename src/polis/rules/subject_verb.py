"""One review-only morphology-backed subject-verb agreement rule."""

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
from polis.rules._morfeusz import (
    _analyses,
    _forms,
    _has_one_supported_lemma,
    _qualified_identity,
    _QualifiedMorfeusz,
    _tags_for_lemma,
)

_PATTERN: Final = re.compile(r"Oni (?P<verb>czyta) książkę\.\Z")
_SUBJECT_LEMMA: Final = "on:S"
_SUBJECT_TAGS: Final = frozenset({"ppron3:pl:nom:m1:ter:akc.nakc:praep.npraep"})
_VERB_LEMMA: Final = "czytać"
_VERB_SOURCE_TAGS: Final = frozenset({"fin:sg:ter:imperf"})
_VERB_TARGET_TAG: Final = "fin:pl:ter:imperf"
_BEHAVIOR_VERSION: Final = (
    "agreement-subject-verb-oni-czyta/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)


class AgreementSubjectVerbOniCzytaRule:
    """Review the one qualified `Oni czyta książkę.` agreement mismatch."""

    _CATEGORY = Category.AGREEMENT

    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        self.source = Source(SourceKind.RULE, "agreement.subject_verb_oni_czyta")
        self._provider = provider
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.subject_verb_number"

    @property
    def behavior_version(self) -> str:
        return _BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        match = _PATTERN.fullmatch(text)
        if (
            match is None
            or self._provider is None
            or _subject_verb_replacement(self._provider) != "czytają"
        ):
            return ()
        return (
            Finding.create(
                category=self._CATEGORY,
                severity=Severity.SUGGESTION,
                message="Niezgodność liczby podmiotu i czasownika.",
                explanation=(
                    "W tej zamkniętej konstrukcji podmiot „Oni” wymaga formy "
                    "czasownika „czytają”."
                ),
                original="czyta",
                suggestion="czytają",
                start=match.start("verb"),
                end=match.end("verb"),
                confidence=self._confidence,
                source=self.source,
            ),
        )


def _subject_verb_replacement(provider: _QualifiedMorfeusz) -> str | None:
    if provider.identity != _qualified_identity():
        return None
    try:
        subject_analyses = _analyses(provider.backend.analyse("Oni"), "Oni")
        verb_analyses = _analyses(provider.backend.analyse("czyta"), "czyta")
        target_forms = _forms(
            provider.backend.generate(_VERB_LEMMA),
            lemma=_VERB_LEMMA,
            target_tag=_VERB_TARGET_TAG,
        )
    except (KeyError, RuntimeError, TypeError, ValueError):
        return None
    if (
        not _has_one_supported_lemma(
            subject_analyses,
            lemma=_SUBJECT_LEMMA,
            source_tags=_SUBJECT_TAGS,
        )
        or not _has_one_supported_lemma(
            verb_analyses,
            lemma=_VERB_LEMMA,
            source_tags=_VERB_SOURCE_TAGS,
        )
        or _tags_for_lemma(subject_analyses, _SUBJECT_LEMMA) != _SUBJECT_TAGS
        or _tags_for_lemma(verb_analyses, _VERB_LEMMA) != _VERB_SOURCE_TAGS
        or target_forms != {"czytają"}
    ):
        return None
    return "czytają"


__all__ = ["AgreementSubjectVerbOniCzytaRule"]
