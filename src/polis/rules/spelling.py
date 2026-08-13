"""High-precision spelling rules."""

from __future__ import annotations

import re
from typing import Final

from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)

_MENTION_WRAPPERS: Final = frozenset(
    {('"', '"'), ("`", "`"), ("„", "”"), ("“", "”"), ("«", "»")}
)


class _CasePatternRule:
    """Simple word-level spelling replacement rule."""

    _CATEGORY = Category.SPELLING
    _IGNORE_WRAPPED_MENTIONS = False

    def __init__(
        self, source_name: str, typed: str, corrected: str, confidence: float
    ) -> None:
        self.source = Source(SourceKind.RULE, source_name)
        self._typed = typed
        self._corrected = corrected
        self._confidence = Confidence(confidence)
        self._pattern = re.compile(rf"(?<!\w){re.escape(typed)}(?!\w)", re.IGNORECASE)

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()

        findings: list[Finding] = []
        for match in self._pattern.finditer(text):
            start = match.start()
            end = match.end()
            if (
                self._IGNORE_WRAPPED_MENTIONS
                and start > 0
                and end < len(text)
                and (text[start - 1], text[end]) in _MENTION_WRAPPERS
            ):
                continue
            observed = match.group()
            candidate = self._apply_case(observed, self._corrected)
            if candidate == observed:
                continue
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=self._severity(),
                    message=self._message(observed),
                    explanation=self._explanation(observed, candidate),
                    original=observed,
                    suggestion=candidate,
                    start=start,
                    end=end,
                    confidence=self._confidence,
                    source=self.source,
                )
            )

        return tuple(findings)

    def _severity(self) -> Severity:
        return Severity.SUGGESTION

    @staticmethod
    def _apply_case(observed: str, replacement: str) -> str:
        if observed.isupper():
            return replacement.upper()
        if observed[:1].isupper():
            return replacement[:1].upper() + replacement[1:]
        return replacement

    @staticmethod
    def _message(observed: str) -> str:
        return f"Wygląda jak częsty błąd ortograficzny: {observed}."

    @staticmethod
    def _explanation(typed: str, fixed: str) -> str:
        return f"Zamiast '{typed}' zwykle poprawnie pisze się '{fixed}'."


class TypoSpellingRule(_CasePatternRule):
    """Rule for a single typo family."""


class SpellingZebyRule(TypoSpellingRule):
    """Corrects ``zeby`` -> ``żeby``."""

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.zeby", typed="zeby", corrected="żeby", confidence=0.98
        )

    @property
    def operation(self) -> str:
        """Return the qualified action performed by this rule."""

        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        """Return the qualified implementation behavior version."""

        return "spelling-zeby/1.0"


class SpellingWlasnieRule(TypoSpellingRule):
    """Corrects ``wlasnie`` -> ``właśnie``."""

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.wlasnie",
            typed="wlasnie",
            corrected="właśnie",
            confidence=0.97,
        )

    @property
    def operation(self) -> str:
        """Return the qualified action performed by this rule."""

        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        """Return the qualified implementation behavior version."""

        return "spelling-wlasnie/1.0"


class SpellingJestesRule(TypoSpellingRule):
    """Corrects ``jestes`` -> ``jesteś``."""

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.jestes",
            typed="jestes",
            corrected="jesteś",
            confidence=0.96,
        )

    @property
    def operation(self) -> str:
        """Return the qualified action performed by this rule."""

        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        """Return the qualified implementation behavior version."""

        return "spelling-jestes/1.0"


class SpellingNapewnoRule(TypoSpellingRule):
    """Corrects ``napewno`` -> ``na pewno``."""

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.napewno",
            typed="napewno",
            corrected="na pewno",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        """Return the qualified action performed by this rule."""

        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        """Return the qualified implementation behavior version."""

        return "spelling-napewno/1.0"


class SpellingWogoleRule(TypoSpellingRule):
    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.wogole",
            typed="wogole",
            corrected="w ogóle",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-wogole/1.0"


class SpellingNarazieRule(TypoSpellingRule):
    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.narazie",
            typed="narazie",
            corrected="na razie",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-narazie/1.0"


__all__ = [
    "SpellingJestesRule",
    "SpellingNapewnoRule",
    "SpellingNarazieRule",
    "SpellingWogoleRule",
    "SpellingWlasnieRule",
    "SpellingZebyRule",
    "TypoSpellingRule",
]
