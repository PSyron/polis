"""High-precision agreement rules."""

from __future__ import annotations

import re

from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Source,
    SourceKind,
)
from polis.core.models import Severity


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


__all__ = ["AgreementCopulaRule"]
