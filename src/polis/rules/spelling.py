"""High-precision spelling rules."""

from __future__ import annotations

import re

from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)


class _CasePatternRule:
    """Simple word-level spelling replacement rule."""

    _CATEGORY = Category.SPELLING

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
            observed = match.group()
            candidate = self._apply_case(observed, self._corrected)
            if candidate == observed:
                continue
            start = match.start()
            end = match.end()
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


class SpellingWlasnieRule(TypoSpellingRule):
    """Corrects ``wlasnie`` -> ``właśnie``."""

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.wlasnie",
            typed="wlasnie",
            corrected="właśnie",
            confidence=0.97,
        )


class SpellingJestesRule(TypoSpellingRule):
    """Corrects ``jestes`` -> ``jesteś``."""

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.jestes",
            typed="jestes",
            corrected="jesteś",
            confidence=0.96,
        )


__all__ = [
    "SpellingJestesRule",
    "SpellingWlasnieRule",
    "SpellingZebyRule",
    "TypoSpellingRule",
]
