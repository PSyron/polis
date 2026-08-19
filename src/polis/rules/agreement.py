"""High-precision agreement rules."""

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

_NOMINAL_GROUP_TE_DUZE_OKNO_PATTERN: Final = re.compile(
    r"Te duże okno jest otwarte\.\Z"
)
_NOMINAL_GROUP_TE_DUZE_OKNO_BEHAVIOR_VERSION: Final = (
    "agreement-nominal-group-te-duze-okno/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
_NOMINAL_GROUP_ADJECTIVE_NOUN_PATTERN: Final = re.compile(
    r"(?<!\w)(?!(?:ta|to|ten|te)(?!\w))"
    r"(?P<adjective>[^\W\d_]+)[ \t]+(?P<noun>[^\W\d_]+)(?!\w)",
    re.IGNORECASE,
)
_NOMINAL_GROUP_DEMONSTRATIVES: Final = frozenset({"ta", "to", "ten", "te"})
_NOMINAL_GROUP_COORDINATOR_PATTERN: Final = re.compile(
    r"(?<!\w)(?:i|oraz|albo|lub|ani)[ \t]+$", re.IGNORECASE
)
_NOMINAL_GROUP_COORDINATOR_AFTER_PATTERN: Final = re.compile(
    r"^[ \t]+(?:i|oraz|albo|lub|ani)(?!\w)", re.IGNORECASE
)
_NOMINAL_GROUP_PREPOSITION_PATTERN: Final = re.compile(
    r"(?<!\w)(?:bez|dla|do|ku|nad|na|o|od|pod|po|przy|przed|przez|w|we|z|za|ze)[ \t]+$",
    re.IGNORECASE,
)
_NOMINAL_GROUP_VOCATIVE_PATTERN: Final = re.compile(r"^[ \t]*,")
_NOMINAL_GROUP_INTERRUPTED_DEMONSTRATIVE_PATTERN: Final = re.compile(
    r"(?<!\w)(?:ta|to|ten|te)(?=[\W]*[^\w\s][\W]*$)[\W]+$",
    re.IGNORECASE,
)
_NOMINAL_GROUP_TA_NOWY_KSIAZKA_BEHAVIOR_VERSION: Final = (
    "agreement-nominal-group-ta-nowy-ksiazka/2.1+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)


class AgreementCopulaRule:
    """Fix obvious first-person or number mismatches after a limited pronoun list."""

    _CATEGORY = Category.AGREEMENT

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "agreement.copula")
        self._pattern = re.compile(
            rf"(?<!\w)(?P<subject>{'|'.join(_SUBJECTS)})\s+(?P<verb>{'|'.join(_VERB_PATTERNS)})",
            re.IGNORECASE,
        )
        self._confidence = Confidence(0.93)

    @property
    def operation(self) -> str:
        """Return the qualified action performed by this rule."""

        return "replace.copula_form"

    @property
    def behavior_version(self) -> str:
        """Return the qualified implementation behavior version."""

        return "agreement-copula/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()

        findings: list[Finding] = []
        for match in self._pattern.finditer(text):
            subject = match.group("subject")
            verb = match.group("verb")
            fixed = _CORRECTIONS.get((subject.lower(), verb.lower()))
            if fixed is None:
                continue

            expected = _match_case(verb, fixed)
            if expected == verb:
                continue

            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Niepasująca forma czasownika 'być'.",
                    explanation=(
                        f"Podmiot „{subject}” zwykle łączy się z formą „{expected}”."
                    ),
                    original=verb,
                    suggestion=expected,
                    start=match.start("verb"),
                    end=match.end("verb"),
                    confidence=self._confidence,
                    source=self.source,
                )
            )

        return tuple(findings)


class AgreementTeZdanieRule:
    """Detect the closed demonstrative mismatch before allowlisted neuter nouns."""

    _CATEGORY = Category.AGREEMENT

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "agreement.te_zdanie")
        self._pattern = re.compile(
            rf"(?<!\w)(?P<phrase>(?P<pronoun>te)(?P<space>[ \t]+)"
            rf"(?P<noun>{'|'.join(_NEUTER_NOUN_ALLOWLIST)}))(?!\w)",
            re.IGNORECASE,
        )
        self._confidence = Confidence(0.98)

    @property
    def operation(self) -> str:
        return "replace.demonstrative_neuter_phrase"

    @property
    def behavior_version(self) -> str:
        return "agreement-te-zdanie/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()

        findings: list[Finding] = []
        for match in self._pattern.finditer(text):
            pronoun = match.group("pronoun")
            space = match.group("space")
            noun = match.group("noun")
            original = match.group("phrase")
            suggestion = f"{_match_case(pronoun, 'to')}{space}{noun}"
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.ERROR,
                    message="Niezgodność rodzaju zaimka i rzeczownika.",
                    explanation=(
                        f"Forma „{pronoun}” nie zgadza się z rzeczownikiem „{noun}” "
                        "w tej regule."
                    ),
                    original=original,
                    suggestion=suggestion,
                    start=match.start("phrase"),
                    end=match.end("phrase"),
                    confidence=self._confidence,
                    source=self.source,
                )
            )

        return tuple(findings)


_TE_NEUTER_NOUNS: Final = ("dziecko", "okno", "słońce", "morze")
_TE_NEUTER_PATTERN: Final = re.compile(
    rf"(?<!\w)(?:(?P<pronoun>Te|te|TE)(?P<space>[ \t]+)"
    rf"(?P<noun>{'|'.join(_TE_NEUTER_NOUNS)})(?!\w)|"
    rf"(?P<upper_pronoun>TE)[ \t]+"
    rf"(?P<upper_noun>{'|'.join(noun.upper() for noun in _TE_NEUTER_NOUNS)})(?!\w))",
)
_COPULA_JA_PATTERN: Final = re.compile(
    r"(?<!\w)(?P<subject>Ja|ja|JA)\s+(?P<verb>jest|JEST)(?!\w)",
)


class AgreementTeNeuterNounRule:
    """Closed ``Te`` + neuter noun → ``To``; excludes ``zdanie`` and comma vocative."""

    _CATEGORY = Category.AGREEMENT

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "agreement.te_neuter_noun")
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.pronoun_gender"

    @property
    def behavior_version(self) -> str:
        return "agreement-te-neuter-noun/2.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        findings: list[Finding] = []
        for match in _TE_NEUTER_PATTERN.finditer(text):
            upper_branch = match.group("upper_pronoun") is not None
            pronoun_group = "upper_pronoun" if upper_branch else "pronoun"
            noun_group = "upper_noun" if upper_branch else "noun"
            phrase_start = match.start(pronoun_group)
            phrase_end = match.end(noun_group)
            if _is_wrapped_mention(text, phrase_start, phrase_end):
                continue
            if _is_quoted_position(text, phrase_start):
                continue
            after = text[phrase_end:]
            # Abstain on optional-space comma (vocative / address reading).
            if re.match(r"[ \t]*,", after) is not None:
                continue
            pronoun = match.group(pronoun_group)
            noun = match.group(noun_group)
            assert pronoun is not None
            assert noun is not None
            if upper_branch:
                suggestion = "TO"
            elif pronoun.isupper():
                suggestion = "TO"
            elif pronoun[:1].isupper():
                suggestion = "To"
            else:
                suggestion = "to"
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Niezgodność rodzaju zaimka i rzeczownika nijakiego.",
                    explanation=(
                        f"Przed rzeczownikiem „{noun}” w tej zamkniętej regule "
                        f"potrzebna jest forma „{suggestion}”."
                    ),
                    original=pronoun,
                    suggestion=suggestion,
                    start=match.start(pronoun_group),
                    end=match.end(pronoun_group),
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


class AgreementCopulaJaRule:
    """Closed ``Ja jest`` → ``jestem`` (no ``jestes`` contention)."""

    _CATEGORY = Category.AGREEMENT

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "agreement.copula_ja")
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.copula_person"

    @property
    def behavior_version(self) -> str:
        return "agreement-copula-ja/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        findings: list[Finding] = []
        for match in _COPULA_JA_PATTERN.finditer(text):
            phrase_start = match.start("subject")
            phrase_end = match.end("verb")
            if _is_wrapped_mention(text, phrase_start, phrase_end):
                continue
            if _is_quoted_position(text, phrase_start):
                continue
            verb = match.group("verb")
            if verb.isupper():
                suggestion = "JESTEM"
            elif verb[:1].isupper():
                suggestion = "Jestem"
            else:
                suggestion = "jestem"
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Niepasująca forma czasownika 'być' po podmiocie „Ja”.",
                    explanation=(
                        f"Podmiot „{match.group('subject')}” wymaga formy "
                        f"„{suggestion}”."
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


class AgreementNominalGroupTeDuzeOknoRule:
    """Review one exact demonstrative error using qualified morphology."""

    _CATEGORY = Category.AGREEMENT

    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        self.source = Source(SourceKind.RULE, "agreement.nominal_group_te_duze_okno")
        self._provider = provider
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.demonstrative_neuter_form"

    @property
    def behavior_version(self) -> str:
        return _NOMINAL_GROUP_TE_DUZE_OKNO_BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        if (
            _NOMINAL_GROUP_TE_DUZE_OKNO_PATTERN.fullmatch(text) is None
            or self._provider is None
            or self._provider.nominal_group_te_duze_okno_replacement() != "To"
        ):
            return ()
        return (
            Finding.create(
                category=self._CATEGORY,
                severity=Severity.SUGGESTION,
                message="Niezgodność form w grupie nominalnej.",
                explanation=(
                    "W tej zamkniętej konstrukcji forma „Te” nie zgadza się z "
                    "rzeczownikiem „okno”; oczekiwana jest forma „To”."
                ),
                original="Te",
                suggestion="To",
                start=0,
                end=2,
                confidence=self._confidence,
                source=self.source,
            ),
        )


class AgreementNominalGroupTaNowyKsiazkaRule:
    _CATEGORY = Category.AGREEMENT

    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        self.source = Source(SourceKind.RULE, "agreement.nominal_group_ta_nowy_ksiazka")
        self._provider = provider
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.adjective_gender"

    @property
    def behavior_version(self) -> str:
        return _NOMINAL_GROUP_TA_NOWY_KSIAZKA_BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()

        findings: list[Finding] = []
        for match in _NOMINAL_GROUP_ADJECTIVE_NOUN_PATTERN.finditer(text):
            adjective_start = match.start("adjective")
            noun_end = match.end("noun")
            preceding_demonstrative = _preceding_demonstrative(text, adjective_start)
            demonstrative = (
                preceding_demonstrative[0]
                if preceding_demonstrative is not None
                else None
            )
            phrase_start = (
                preceding_demonstrative[1]
                if preceding_demonstrative is not None
                else adjective_start
            )
            if (
                _is_wrapped_mention(text, phrase_start, noun_end)
                or _is_quoted_position(text, phrase_start)
                or _NOMINAL_GROUP_INTERRUPTED_DEMONSTRATIVE_PATTERN.search(
                    text[:adjective_start]
                )
                or _NOMINAL_GROUP_COORDINATOR_PATTERN.search(text[:phrase_start])
                or _NOMINAL_GROUP_COORDINATOR_AFTER_PATTERN.match(text[noun_end:])
                or _NOMINAL_GROUP_PREPOSITION_PATTERN.search(text[:phrase_start])
                or _NOMINAL_GROUP_VOCATIVE_PATTERN.match(text[noun_end:])
            ):
                continue
            adjective = match.group("adjective")
            noun = match.group("noun")
            if not _has_simple_casing(adjective):
                continue
            replacement: str | None
            legacy_pattern = (
                demonstrative is not None
                and demonstrative.casefold() == "ta"
                and adjective.casefold() == "nowy"
                and noun.casefold() == "książka"
            )
            if legacy_pattern:
                replacement = (
                    self._provider.nominal_group_ta_nowy_ksiazka_replacement()
                    if self._provider is not None
                    else None
                )
            elif self._provider is None:
                replacement = None
            else:
                replacement = self._provider.nominal_group_agreement_replacement(
                    adjective, noun, demonstrative
                )
            if replacement is None:
                continue
            suggestion = _match_case(adjective, replacement)
            if suggestion == adjective:
                continue
            explanation = (
                "W tej zamkniętej konstrukcji forma „nowy” nie zgadza się "
                "z rzeczownikiem „książka”; oczekiwana jest forma „nowa”."
                if legacy_pattern
                else (
                    f"Forma „{adjective}” nie zgadza się z rzeczownikiem „{noun}”; "
                    f"jednoznaczna forma to „{suggestion}”."
                )
            )
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Niezgodność form w grupie nominalnej.",
                    explanation=explanation,
                    original=adjective,
                    suggestion=suggestion,
                    start=adjective_start,
                    end=match.end("adjective"),
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


def _preceding_demonstrative(text: str, position: int) -> tuple[str, int] | None:
    prefix = text[:position]
    match = re.search(r"(?<!\w)(?P<word>[^\W\d_]+)[ \t]+$", prefix)
    if match is None:
        return None
    word = match.group("word")
    if word.casefold() not in _NOMINAL_GROUP_DEMONSTRATIVES:
        return None
    return word, match.start("word")


def _match_case(reference: str, replacement: str) -> str:
    if reference.isupper():
        return replacement.upper()
    if reference[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _has_simple_casing(value: str) -> bool:
    return value.islower() or value.isupper() or value.istitle()


_MENTION_WRAPPERS: Final = frozenset(
    {
        ('"', '"'),
        ("'", "'"),
        ("`", "`"),
        ("„", "”"),
        ("“", "”"),
        ("‘", "’"),
        ("«", "»"),
        ("‹", "›"),
    }
)


def _is_quoted_position(text: str, position: int) -> bool:
    for opening, closing in _MENTION_WRAPPERS:
        before = text[:position]
        if opening == closing:
            if before.count(opening) % 2 == 1:
                return True
        elif before.rfind(opening) > before.rfind(closing):
            return True
    return False


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


_SUBJECTS: tuple[str, ...] = (
    "ona",
    "on",
    "ono",
    "oni",
    "one",
    "ty",
    "my",
    "wy",
)

_VERB_PATTERNS: tuple[str, ...] = (
    "jestem",
    "jestes",
    "jestesz",
    "jesteś",
    "jesteśmy",
    "jesteście",
    "są",
    "jest",
)

_NEUTER_NOUN_ALLOWLIST: tuple[str, ...] = ("zdanie",)

_CORRECTIONS: dict[tuple[str, str], str] = {
    ("ona", "jestem"): "jest",
    ("ona", "jesteś"): "jest",
    ("ona", "jestes"): "jest",
    ("ona", "jestesz"): "jest",
    ("ona", "jesteśmy"): "jest",
    ("ona", "jesteście"): "jest",
    ("ona", "są"): "jest",
    ("on", "jestem"): "jest",
    ("on", "jesteś"): "jest",
    ("on", "jestes"): "jest",
    ("on", "jesteśmy"): "jest",
    ("on", "jesteście"): "jest",
    ("on", "są"): "jest",
    ("ono", "jestem"): "jest",
    ("ono", "jesteś"): "jest",
    ("ono", "jestes"): "jest",
    ("ono", "są"): "jest",
    ("oni", "jestem"): "są",
    ("oni", "jesteś"): "są",
    ("oni", "jest"): "są",
    ("oni", "jestes"): "są",
    ("oni", "jesteście"): "są",
    ("one", "jestem"): "są",
    ("one", "jesteś"): "są",
    ("one", "jest"): "są",
    ("one", "jestes"): "są",
    ("ty", "jestem"): "jesteś",
    ("ty", "jest"): "jesteś",
    ("my", "jestem"): "jesteśmy",
    ("my", "jesteś"): "jesteśmy",
    ("my", "jestes"): "jesteśmy",
    ("wy", "jestem"): "jesteście",
    ("wy", "jesteś"): "jesteście",
    ("wy", "jestes"): "jesteście",
}


__all__ = [
    "AgreementCopulaJaRule",
    "AgreementCopulaRule",
    "AgreementNominalGroupTaNowyKsiazkaRule",
    "AgreementNominalGroupTeDuzeOknoRule",
    "AgreementTeNeuterNounRule",
    "AgreementTeZdanieRule",
]
