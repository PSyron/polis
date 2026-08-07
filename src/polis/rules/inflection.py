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

_PATTERN: Final = re.compile(
    r"(?:(?:Nie|nie) widzę (?P<lower>samochód)|NIE WIDZĘ (?P<upper>SAMOCHÓD))\.\Z"
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


__all__ = ["InflectionNegatedWidziecRule"]
