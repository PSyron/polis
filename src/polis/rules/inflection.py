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

_PATTERN: Final = re.compile(
    r"(?:(?:Nie|nie) widzę (?P<lower>samochód)|NIE WIDZĘ (?P<upper>SAMOCHÓD))\.\Z"
)
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

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "inflection.negated_widziec")
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        """Return the review-only action performed by this rule."""

        return "replace.negated_government_form"

    @property
    def behavior_version(self) -> str:
        """Return the review-only implementation behavior version."""

        return "inflection-negated-widziec/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        """Return the one closed finding when its exact sentence is present."""

        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        match = _PATTERN.fullmatch(text)
        if match is None:
            return ()
        group = "upper" if match.group("upper") is not None else "lower"
        original = match.group(group)
        suggestion = "SAMOCHODU" if group == "upper" else "samochodu"
        return (
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
                start=match.start(group),
                end=match.end(group),
                confidence=self._confidence,
                source=self.source,
            ),
        )


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


__all__ = [
    "InflectionNegatedWidziecNominalGroupRule",
    "InflectionNegatedWidziecRule",
]
