"""Review-only morphology-backed subject-verb agreement rules."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
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
    _analyses_with_metadata,
    _forms,
    _GenerationRow,
    _has_one_supported_lemma,
    _ParsedAnalysis,
    _qualified_identity,
    _QualifiedMorfeusz,
    _tag_features,
    _tags_for_lemma,
)
from polis.rules.agreement import _is_quoted_position

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


_PRESENT_SOURCE_NAME: Final = "agreement.subject_verb_present"
_PRESENT_BEHAVIOR_VERSION: Final = (
    "agreement-subject-verb-present/1.8+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
_PRESENT_PATTERN: Final = re.compile(
    r"(?<!\w)(?P<subject>Ona|Ono|Oni|One|Ja|Ty|My|Wy|On)"
    r"(?P<gap>(?:[ \t]+|[ \t]*[,;:—–-][ \t]+)(?:nie[ \t]+)?)"
    r"(?P<verb>[^\W\d_]+)(?!\w)",
    re.IGNORECASE,
)
_PRESENT_COORDINATOR_BEFORE: Final = re.compile(
    r"(?<!\w)(?:i|oraz|albo|lub|ani|a|ale|lecz|natomiast)[ \t]+$",
    re.IGNORECASE,
)
_PRESENT_COORDINATOR_AFTER: Final = re.compile(
    r"^[ \t]*(?:[,;:][ \t]*)?(?:i|oraz|albo|lub|ani|a|ale|lecz|natomiast)"
    r"(?!\w)",
    re.IGNORECASE,
)
_PRESENT_CLAUSE_BOUNDARY_BEFORE: Final = re.compile(r";[ \t]*$")
_PRESENT_OLD_MY_OBJECTS: Final = frozenset({"książkę", "książke", "gazetę", "gazete"})
_PRESENT_LITERAL_COPULA_PAIRS: Final = frozenset(
    {
        ("ja", "jest"),
        ("ona", "jestem"),
        ("ona", "jesteś"),
        ("ona", "jestes"),
        ("ona", "jestesz"),
        ("ona", "jesteśmy"),
        ("ona", "jesteście"),
        ("ona", "są"),
        ("on", "jestem"),
        ("on", "jesteś"),
        ("on", "jestes"),
        ("on", "jesteśmy"),
        ("on", "jesteście"),
        ("on", "są"),
        ("ono", "jestem"),
        ("ono", "jesteś"),
        ("ono", "jestes"),
        ("ono", "są"),
        ("ono", "jesteśmy"),
        ("ono", "jesteście"),
        ("oni", "jestem"),
        ("oni", "jesteś"),
        ("oni", "jest"),
        ("oni", "jestes"),
        ("oni", "jesteście"),
        ("oni", "jesteśmy"),
        ("one", "jestem"),
        ("one", "jesteś"),
        ("one", "jest"),
        ("one", "jestes"),
        ("one", "jesteśmy"),
        ("one", "jesteście"),
        ("ty", "jestem"),
        ("ty", "jest"),
        ("my", "jestem"),
        ("my", "jesteś"),
        ("my", "jestes"),
        ("my", "jesteśmy"),
        ("my", "jesteście"),
        ("wy", "jestem"),
        ("wy", "jesteś"),
        ("wy", "jestes"),
        ("wy", "jesteśmy"),
        ("wy", "jesteście"),
    }
)
_PRESENT_GENERATION_TAG_PREFIXES: Final = frozenset(
    {
        "aglt",
        "bedzie",
        "fin",
        "ger",
        "imps",
        "impt",
        "inf",
        "pact",
        "pacta",
        "pcon",
        "ppas",
        "praet",
    }
)
_PRESENT_PREPOSITIONAL_COMPLEMENT_PATTERN: Final = re.compile(
    r"^[ \t]+(?:w|we|na|do|z|ze|od|u|o|po|przy|pod|nad|za|przez|między)"
    r"[ \t]+[^\W\d_]+",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class _PresentPronounProfile:
    lemma: str
    number: str
    person: str
    tags: frozenset[str]


def present_replacement(
    provider: _QualifiedMorfeusz,
    *,
    subject: str,
    verb: str,
    continuation: str = "",
) -> str | None:
    if provider.identity != _qualified_identity():
        return None
    try:
        subject_analyses = _analyses_with_metadata(
            provider.backend.analyse(subject), subject
        )
        verb_analyses = _analyses_with_metadata(provider.backend.analyse(verb), verb)
        profile = _present_subject_profile(subject, subject_analyses)
        lemma = _present_verb(verb_analyses, continuation=continuation)
        if profile is None or lemma is None:
            return None
        return _present_generated_target_form(
            provider.backend.generate(lemma),
            lemma=lemma,
            target_tag=f"fin:{profile.number}:{profile.person}:imperf",
        )
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        return None


def _present_pronoun_profile(subject: str) -> _PresentPronounProfile | None:
    key = subject.casefold()
    first_person = {"ja": ("sg", "pri"), "my": ("pl", "pri")}
    second_person = {"ty": ("sg", "sec"), "wy": ("pl", "sec")}
    if key in first_person or key in second_person:
        number, person = (first_person | second_person)[key]
        cases = ("nom",) if key == "ja" else ("nom", "voc")
        tags = frozenset(
            f"ppron12:{number}:{case}:m1.m2.m3.f.n:{person}" for case in cases
        )
        return _PresentPronounProfile(key, number, person, tags)
    third_person = {
        "on": ("sg", "m1.m2.m3"),
        "ona": ("sg", "f"),
        "ono": ("sg", "n"),
        "oni": ("pl", "m1"),
        "one": ("pl", "m2.m3.f.n"),
    }
    if key not in third_person:
        return None
    number, gender = third_person[key]
    tag = f"ppron3:{number}:nom:{gender}:ter:akc.nakc:praep.npraep"
    return _PresentPronounProfile("on:S", number, "ter", frozenset({tag}))


def _present_subject_profile(
    subject: str, analyses: tuple[_ParsedAnalysis, ...] | None
) -> _PresentPronounProfile | None:
    profile = _present_pronoun_profile(subject)
    if profile is None or analyses is None or not analyses:
        return None
    if len(analyses) != len(set(analyses)) or _present_has_ignored_tag(analyses):
        return None
    pronouns = tuple(
        item for item in analyses if item.tag.startswith(("ppron12:", "ppron3:"))
    )
    if (
        len(pronouns) != len(profile.tags)
        or {item.lemma for item in pronouns} != {profile.lemma}
        or {item.tag for item in pronouns} != profile.tags
    ):
        return None
    if any(
        not (
            profile.lemma == "on:S"
            and item.lemma == "on:A"
            and item.tag.startswith("adj:")
            and _tag_features(item.tag, prefix="adj") is not None
        )
        for item in analyses
        if item not in pronouns
    ):
        return None
    return profile


def _present_verb(
    analyses: tuple[_ParsedAnalysis, ...] | None, *, continuation: str
) -> str | None:
    if analyses is None or not analyses or _present_has_ignored_tag(analyses):
        return None
    finite: list[str] = []
    for analysis in analyses:
        if not _present_analysis_tag_is_valid(analysis.tag):
            return None
        parts = analysis.tag.split(":")
        if parts[0] != "fin":
            continue
        lemma = analysis.lemma
        if (
            not lemma
            or len(parts) != 4
            or parts[1] not in {"sg", "pl"}
            or parts[2] not in {"pri", "sec", "ter"}
            or parts[3] != "imperf"
        ):
            return None
        finite.append(lemma)
    if len(finite) != 1:
        return None
    if (
        len(analyses) != 1
        and _PRESENT_PREPOSITIONAL_COMPLEMENT_PATTERN.match(continuation) is None
    ):
        return None
    return finite[0]


def _present_generated_target_form(
    rows: Sequence[_GenerationRow], *, lemma: str, target_tag: str
) -> str | None:
    if isinstance(rows, (str, bytes)):
        return None
    forms = _forms(rows, lemma=lemma, target_tag=target_tag)
    if (
        not isinstance(forms, set)
        or not all(isinstance(form, str) for form in forms)
        or len(forms) != 1
    ):
        return None
    target_forms = {form for form in forms if isinstance(form, str)}
    seen_rows: list[tuple[str, str, str, list[str], list[str]]] = []
    seen_forms: set[tuple[str, str]] = set()
    for row in rows:
        if not isinstance(row, tuple) or len(row) != 5:
            return None
        form, row_lemma, tag, labels, qualifiers = row
        if (
            not isinstance(form, str)
            or not form
            or not isinstance(row_lemma, str)
            or row_lemma != lemma
            or not isinstance(tag, str)
            or not tag
            or not isinstance(labels, list)
            or not isinstance(qualifiers, list)
            or not all(isinstance(value, str) for value in labels)
            or not all(isinstance(value, str) for value in qualifiers)
            or not _present_generation_tag_is_valid(tag)
        ):
            return None
        validated_row = (form, row_lemma, tag, labels, qualifiers)
        if any(validated_row == previous for previous in seen_rows):
            return None
        seen_rows.append(validated_row)
        if tag.startswith("fin:"):
            parts = tag.split(":")
            if (
                len(parts) != 4
                or parts[1] not in {"sg", "pl"}
                or parts[2] not in {"pri", "sec", "ter"}
                or parts[3] != "imperf"
            ):
                return None
        if (form, tag) in seen_forms:
            return None
        seen_forms.add((form, tag))
    return next(iter(target_forms))


def _present_has_ignored_tag(analyses: Sequence[_ParsedAnalysis]) -> bool:
    return any(item.tag.partition(":")[0] == "ign" for item in analyses)


def _present_analysis_tag_is_valid(tag: str) -> bool:
    prefix = tag.partition(":")[0]
    if prefix == "fin":
        parts = tag.split(":")
        return (
            len(parts) == 4
            and parts[1] in {"sg", "pl"}
            and parts[2] in {"pri", "sec", "ter"}
            and parts[3] == "imperf"
        )
    if prefix in {"adj", "subst"}:
        return _tag_features(tag, prefix=prefix) is not None
    return False


def _present_generation_tag_is_valid(tag: str) -> bool:
    prefix = tag.partition(":")[0]
    if prefix in {"fin", "adj", "subst"}:
        return _present_analysis_tag_is_valid(tag)
    if prefix == "pacta":
        return tag == "pacta"
    if prefix not in _PRESENT_GENERATION_TAG_PREFIXES:
        return False
    parts = tag.split(":")
    if prefix in {"imps", "inf", "pcon"}:
        return parts == [prefix, "imperf"]
    if prefix == "impt":
        return (
            len(parts) == 4
            and parts[1] in {"sg", "pl"}
            and parts[2] in {"pri", "sec", "ter"}
            and parts[3] == "imperf"
        )
    if prefix == "bedzie":
        return (
            len(parts) == 4
            and parts[1] in {"sg", "pl"}
            and parts[2] in {"pri", "sec", "ter"}
            and parts[3] == "imperf"
        )
    if prefix == "aglt":
        return (
            len(parts) == 5
            and parts[1] in {"sg", "pl"}
            and parts[2] in {"pri", "sec"}
            and parts[3] == "imperf"
            and parts[4] in {"wok", "nwok"}
        )
    if prefix == "praet":
        return (
            len(parts) == 4
            and parts[1] in {"sg", "pl"}
            and _present_tag_values(parts[2], {"m1", "m2", "m3", "f", "n"})
            and parts[3] == "imperf"
        )
    if prefix == "ger":
        return (
            len(parts) == 6
            and parts[1] in {"sg", "pl"}
            and _present_tag_values(
                parts[2], {"nom", "acc", "gen", "dat", "inst", "loc", "voc"}
            )
            and parts[3] == "n"
            and parts[4] == "imperf"
            and parts[5] in {"aff", "neg"}
        )
    if prefix in {"pact", "ppas"}:
        return (
            len(parts) == 6
            and parts[1] in {"sg", "pl"}
            and _present_tag_values(
                parts[2], {"nom", "acc", "gen", "dat", "inst", "loc", "voc"}
            )
            and _present_tag_values(parts[3], {"m1", "m2", "m3", "f", "n"})
            and parts[4] == "imperf"
            and parts[5] in {"aff", "neg"}
        )
    return False


def _present_tag_values(value: str, allowed: set[str]) -> bool:
    values = value.split(".")
    return bool(values) and all(item in allowed for item in values)


class AgreementSubjectVerbPresentRule:
    _CATEGORY = Category.AGREEMENT

    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        self.source = Source(SourceKind.RULE, _PRESENT_SOURCE_NAME)
        self._provider = provider
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.subject_verb_person_number"

    @property
    def behavior_version(self) -> str:
        return _PRESENT_BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        if self._provider is None:
            return ()
        findings: list[Finding] = []
        for match in _PRESENT_PATTERN.finditer(text):
            subject_start = match.start("subject")
            verb_start = match.start("verb")
            verb_end = match.end("verb")
            if _present_excluded_context(text, subject_start, verb_end):
                continue
            subject = match.group("subject")
            verb = match.group("verb")
            if not _present_has_supported_case(subject) or _present_has_combining_mark(
                text[subject_start : verb_end + 1]
            ):
                continue
            if _present_overlaps_literal_consumer(text, subject, verb, verb_end):
                continue
            replacement = present_replacement(
                self._provider,
                subject=subject,
                verb=verb,
                continuation=text[verb_end:],
            )
            if replacement is None:
                continue
            suggestion = _present_match_case(verb, replacement)
            if suggestion is None or suggestion == verb:
                continue
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Niezgodność osoby lub liczby podmiotu i czasownika.",
                    explanation=(
                        f"Podmiot „{subject}” wymaga w tej konstrukcji formy "
                        f"„{suggestion}”."
                    ),
                    original=verb,
                    suggestion=suggestion,
                    start=verb_start,
                    end=verb_end,
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


def _present_excluded_context(text: str, subject_start: int, verb_end: int) -> bool:
    if _is_quoted_position(text, subject_start):
        return True
    return (
        _PRESENT_COORDINATOR_BEFORE.search(text[:subject_start]) is not None
        or _PRESENT_COORDINATOR_AFTER.match(text[verb_end:]) is not None
        or _PRESENT_CLAUSE_BOUNDARY_BEFORE.search(text[:subject_start]) is not None
    )


def _present_overlaps_literal_consumer(
    text: str, subject: str, verb: str, verb_end: int
) -> bool:
    subject_key = subject.casefold()
    verb_key = verb.casefold()
    if (subject_key, verb_key) in _PRESENT_LITERAL_COPULA_PAIRS:
        return True
    if subject_key == "oni" and verb_key == "czyta":
        return text == "Oni czyta książkę."
    if subject_key != "my" or verb_key != "czyta":
        return False
    following = text[verb_end:].lstrip(" \t")
    object_word = following.split(maxsplit=1)[0].rstrip(".!?,;:")
    return object_word.casefold() in _PRESENT_OLD_MY_OBJECTS


def _present_match_case(reference: str, replacement: str) -> str | None:
    if reference.isupper():
        return replacement.upper()
    if reference.islower():
        return replacement
    if reference[:1].isupper() and reference[1:].islower():
        return replacement[:1].upper() + replacement[1:]
    return None


def _present_has_supported_case(value: str) -> bool:
    return value.isupper() or (value[:1].isupper() and value[1:].islower())


def _present_has_combining_mark(value: str) -> bool:
    return any(unicodedata.combining(character) for character in value)


__all__ = [
    "AgreementSubjectVerbMyCzytaRule",
    "AgreementSubjectVerbOniCzytaRule",
    "AgreementSubjectVerbPresentRule",
]
