"""Review-only morphology-backed subject-verb agreement rules."""

from __future__ import annotations

import re
from functools import lru_cache
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

_ONI_PATTERN: Final = re.compile(r"Oni (?P<verb>czyta) książkę\.\Z")
_ONI_SUBJECT_LEMMA: Final = "on:S"
_ONI_SUBJECT_TAGS: Final = frozenset({"ppron3:pl:nom:m1:ter:akc.nakc:praep.npraep"})
_VERB_LEMMA: Final = "czytać"
_VERB_SOURCE_TAGS: Final = frozenset({"fin:sg:ter:imperf"})
_ONI_VERB_TARGET_TAG: Final = "fin:pl:ter:imperf"
_ONI_BEHAVIOR_VERSION: Final = (
    "agreement-subject-verb-oni-czyta/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)

_MY_PATTERN: Final = re.compile(
    r"(?<!\w)(?P<phrase>(?P<subject>My) (?P<verb>czyta) "
    r"(?P<object>książkę|książke|gazetę|gazete|KSIĄŻKĘ|GAZETĘ))"
    r"(?!\w)",
    re.IGNORECASE,
)
_MY_SUBJECT_LEMMA: Final = "my"
_MY_SUBJECT_TAGS: Final = frozenset(
    {
        "ppron12:pl:nom:m1.m2.m3.f.n:pri",
        "ppron12:pl:voc:m1.m2.m3.f.n:pri",
    }
)
_MY_VERB_TARGET_TAG: Final = "fin:pl:pri:imperf"
_MY_BEHAVIOR_VERSION: Final = (
    "agreement-subject-verb-my-czyta/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
_MENTION_WRAPPERS: Final = frozenset(
    {('"', '"'), ("`", "`"), ("„", "”"), ("“", "”"), ("«", "»")}
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
        return _ONI_BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        match = _ONI_PATTERN.fullmatch(text)
        if (
            match is None
            or self._provider is None
            or _oni_subject_verb_replacement(self._provider) != "czytają"
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


class AgreementSubjectVerbMyCzytaRule:
    """Review the closed `My czyta książkę` agreement mismatch."""

    _CATEGORY = Category.AGREEMENT

    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        self.source = Source(SourceKind.RULE, "agreement.subject_verb_my_czyta")
        self._provider = provider
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.subject_verb_number"

    @property
    def behavior_version(self) -> str:
        return _MY_BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        matches = tuple(
            match
            for match in _MY_PATTERN.finditer(text)
            if not _is_wrapped_mention(text, match.start("phrase"), match.end("phrase"))
        )
        if (
            not matches
            or self._provider is None
            or _my_subject_verb_replacement(self._provider) != "czytamy"
        ):
            return ()

        findings: list[Finding] = []
        for match in matches:
            verb = match.group("verb")
            suggestion = _match_case(verb, "czytamy")
            if suggestion == verb:
                continue
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Niezgodność liczby podmiotu i czasownika.",
                    explanation=(
                        "W tej zamkniętej konstrukcji podmiot „My” wymaga formy "
                        "czasownika „czytamy”."
                    ),
                    original=verb,
                    suggestion=suggestion,
                    start=match.start("verb"),
                    end=match.end("verb"),
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


@lru_cache(maxsize=8)
def _oni_subject_verb_replacement(provider: _QualifiedMorfeusz) -> str | None:
    if provider.identity != _qualified_identity():
        return None
    try:
        subject_analyses = _analyses(provider.backend.analyse("Oni"), "Oni")
        verb_analyses = _analyses(provider.backend.analyse("czyta"), "czyta")
        target_forms = _forms(
            provider.backend.generate(_VERB_LEMMA),
            lemma=_VERB_LEMMA,
            target_tag=_ONI_VERB_TARGET_TAG,
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError):
        return None
    if (
        not _has_one_supported_lemma(
            subject_analyses,
            lemma=_ONI_SUBJECT_LEMMA,
            source_tags=_ONI_SUBJECT_TAGS,
        )
        or not _has_one_supported_lemma(
            verb_analyses,
            lemma=_VERB_LEMMA,
            source_tags=_VERB_SOURCE_TAGS,
        )
        or _tags_for_lemma(subject_analyses, _ONI_SUBJECT_LEMMA) != _ONI_SUBJECT_TAGS
        or _tags_for_lemma(verb_analyses, _VERB_LEMMA) != _VERB_SOURCE_TAGS
        or target_forms != {"czytają"}
    ):
        return None
    return "czytają"


@lru_cache(maxsize=8)
def _my_subject_verb_replacement(provider: _QualifiedMorfeusz) -> str | None:
    if provider.identity != _qualified_identity():
        return None
    try:
        subject_analyses = _analyses(provider.backend.analyse("My"), "My")
        verb_analyses = _analyses(provider.backend.analyse("czyta"), "czyta")
        target_forms = _forms(
            provider.backend.generate(_VERB_LEMMA),
            lemma=_VERB_LEMMA,
            target_tag=_MY_VERB_TARGET_TAG,
        )
    except (KeyError, OSError, RuntimeError, TypeError, ValueError):
        return None
    if (
        not _has_one_supported_lemma(
            subject_analyses,
            lemma=_MY_SUBJECT_LEMMA,
            source_tags=_MY_SUBJECT_TAGS,
        )
        or not _has_one_supported_lemma(
            verb_analyses,
            lemma=_VERB_LEMMA,
            source_tags=_VERB_SOURCE_TAGS,
        )
        or _tags_for_lemma(subject_analyses, _MY_SUBJECT_LEMMA) != _MY_SUBJECT_TAGS
        or _tags_for_lemma(verb_analyses, _VERB_LEMMA) != _VERB_SOURCE_TAGS
        or target_forms != {"czytamy"}
    ):
        return None
    return "czytamy"


def _match_case(reference: str, replacement: str) -> str:
    if reference.isupper():
        return replacement.upper()
    if reference[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _is_wrapped_mention(text: str, start: int, end: int) -> bool:
    if start <= 0 or end >= len(text):
        return False
    left = text[start - 1]
    right = text[end]
    if (left, right) in _MENTION_WRAPPERS:
        return True
    if left == "`":
        rest = text[end:]
        return rest.startswith("`") or rest.startswith("()`")
    return False


__all__ = [
    "AgreementSubjectVerbMyCzytaRule",
    "AgreementSubjectVerbOniCzytaRule",
]
