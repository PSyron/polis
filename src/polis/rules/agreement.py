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


def _match_case(reference: str, replacement: str) -> str:
    if reference.isupper():
        return replacement.upper()
    if reference[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


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
    "AgreementCopulaRule",
    "AgreementNominalGroupTeDuzeOknoRule",
    "AgreementTeZdanieRule",
]
