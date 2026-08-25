"""Closed, review-only inflection rules."""

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
from polis.rules.government import _is_followed_by_nominal_group
from polis.segmentation import (
    _iter_sentence_template_matches as iter_sentence_template_matches,
)

_PATTERN: Final = re.compile(
    r"(?<!\w)(?:(?:Nie|nie) widzę (?P<lower>samochód)|"
    r"NIE WIDZĘ (?P<upper>SAMOCHÓD))(?!\w)"
)
_TRAILING_MATERIAL_PATTERN: Final = re.compile(
    r"(?<!\w)(?:(?:Nie|nie) widzę (?P<lower>samochód)|"
    r"NIE WIDZĘ (?P<upper>SAMOCHÓD))(?!\w)(?=[ \t]+[^\W\d_]+)"
)
_NEGATED_REPEAT_SEPARATOR: Final = re.compile(r"\s+(?:i znów|I ZNÓW)\s+")
_NOMINAL_GROUP_PATTERN: Final = re.compile(
    r"Nie widzę (?P<nominal_group>czerwony samochód)\.\Z"
)
_NOMINAL_GROUP_BEHAVIOR_VERSION: Final = (
    "inflection-negated-widziec-nominal-group/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)


class InflectionNegatedWidziecRule:
    """Correct one reviewed negated-government form and abstain elsewhere."""

    _CATEGORY = Category.INFLECTION

    def __init__(self, provider: _QualifiedMorfeusz | None = None) -> None:
        self.source = Source(SourceKind.RULE, "inflection.negated_widziec")
        if provider is not None:
            self._provider = provider
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        """Return the review-only action performed by this rule."""

        return "replace.negated_government_form"

    @property
    def behavior_version(self) -> str:
        """Return the review-only implementation behavior version."""

        return "inflection-negated-widziec/3.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        """Return the one closed finding when its exact sentence is present."""

        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        if "widzę" not in text and "WIDZĘ" not in text:
            return ()
        matches = [
            match
            for _sentence, match in iter_sentence_template_matches(
                text,
                _PATTERN,
                require_terminal=True,
                repeat_separator=_NEGATED_REPEAT_SEPARATOR,
            )
        ]
        provider = getattr(self, "_provider", None)
        if provider is not None:
            for sentence, match in iter_sentence_template_matches(
                text, _TRAILING_MATERIAL_PATTERN
            ):
                group = "upper" if match.group("upper") is not None else "lower"
                if (
                    not _is_followed_by_nominal_group(text, match.end(group), provider)
                    and text[match.end() : sentence.end]
                    .strip()
                    .endswith((".", "!", "?"))
                    and not text[match.end() : sentence.end].strip().endswith("...")
                ):
                    matches.append(match)
        findings: list[Finding] = []
        for match in sorted(matches, key=re.Match.start):
            group = "upper" if match.group("upper") is not None else "lower"
            original = match.group(group)
            suggestion = "SAMOCHODU" if group == "upper" else "samochodu"
            start, end = match.start(group), match.end(group)
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Niepoprawna forma dopełnienia po zaprzeczonym „widzieć”.",
                    explanation=(
                        "W tej zamkniętej konstrukcji zaprzeczenie wymaga formy "
                        f"„{suggestion}”."
                    ),
                    original=original,
                    suggestion=suggestion,
                    start=start,
                    end=end,
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


class InflectionNegatedWidziecNominalGroupRule:
    """Review one exact nominal-group error using qualified morphology."""

    _CATEGORY = Category.INFLECTION

    def __init__(self, provider: _QualifiedMorfeusz | None) -> None:
        self.source = Source(
            SourceKind.RULE,
            "inflection.negated_widziec_nominal_group",
        )
        self._provider = provider
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.negated_government_nominal_group"

    @property
    def behavior_version(self) -> str:
        return _NOMINAL_GROUP_BEHAVIOR_VERSION

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        match = _NOMINAL_GROUP_PATTERN.fullmatch(text)
        if match is None or self._provider is None:
            return ()
        replacement = self._provider.negated_widziec_nominal_group_replacement(
            "czerwony", "samochód"
        )
        if replacement != "czerwonego samochodu":
            return ()
        original = match.group("nominal_group")
        return (
            Finding.create(
                category=self._CATEGORY,
                severity=Severity.SUGGESTION,
                message="Niepoprawna odmiana grupy nominalnej po zaprzeczeniu.",
                explanation=(
                    "W tej zamkniętej konstrukcji przymiotnik i rzeczownik "
                    "wymagają dopełniacza."
                ),
                original=original,
                suggestion=replacement,
                start=match.start("nominal_group"),
                end=match.end("nominal_group"),
                confidence=self._confidence,
                source=self.source,
            ),
        )


_MIEC_CZAS_PATTERN: Final = re.compile(
    r"(?<!\w)(?:(?:Nie|nie) mam (?P<lower>czas)|"
    r"NIE MAM (?P<upper>CZAS))(?!\w)"
)
_NUMERAL_FIVE_PATTERN: Final = re.compile(
    r"(?<!\w)(?P<head>Pięć|pięć|PIĘĆ)\s+"
    r"(?P<object>książki|KSIĄŻKI)(?=\s)",
)


class InflectionNegatedMiecCzasRule:
    """Closed whole-input ``Nie mam czas.`` → ``czasu`` (no morphology)."""

    _CATEGORY = Category.INFLECTION

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "inflection.negated_miec_czas")
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.governed_form"

    @property
    def behavior_version(self) -> str:
        return "inflection-negated-miec-czas/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        if "mam" not in text and "MAM" not in text:
            return ()
        findings: list[Finding] = []
        for _sentence, match in iter_sentence_template_matches(
            text,
            _MIEC_CZAS_PATTERN,
            require_terminal=True,
            repeat_separator=_NEGATED_REPEAT_SEPARATOR,
        ):
            group = "upper" if match.group("upper") is not None else "lower"
            original = match.group(group)
            suggestion = "CZASU" if group == "upper" else "czasu"
            start, end = match.start(group), match.end(group)
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Niepoprawna forma dopełnienia po zaprzeczonym „mieć”.",
                    explanation=(
                        "W tej zamkniętej konstrukcji zaprzeczenie wymaga formy "
                        f"„{suggestion}”."
                    ),
                    original=original,
                    suggestion=suggestion,
                    start=start,
                    end=end,
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


class InflectionNumeralFiveGenitivePluralRule:
    """Sentence-anchored closed map ``Pięć książki`` → ``książek``."""

    _CATEGORY = Category.INFLECTION
    _MAP: Final = {"książki": "książek", "KSIĄŻKI": "KSIĄŻEK"}

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "inflection.numeral_five_genitive_plural")
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.governed_form"

    @property
    def behavior_version(self) -> str:
        return "inflection-numeral-five-genitive-plural/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        if "książki" not in text and "KSIĄŻKI" not in text:
            return ()
        findings: list[Finding] = []
        for _sentence, match in iter_sentence_template_matches(
            text, _NUMERAL_FIVE_PATTERN
        ):
            original = match.group("object")
            suggestion = self._MAP.get(original)
            if suggestion is None:
                continue
            start, end = match.start("object"), match.end("object")
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Niepoprawna forma rzeczownika po liczebniku „pięć”.",
                    explanation=(
                        "Po liczebniku „pięć” w tej zamkniętej konstrukcji "
                        f"potrzebna jest forma „{suggestion}”."
                    ),
                    original=original,
                    suggestion=suggestion,
                    start=start,
                    end=end,
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


__all__ = [
    "InflectionNegatedMiecCzasRule",
    "InflectionNegatedWidziecNominalGroupRule",
    "InflectionNegatedWidziecRule",
    "InflectionNumeralFiveGenitivePluralRule",
]
