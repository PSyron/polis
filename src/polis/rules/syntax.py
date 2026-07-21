"""Selected syntax and punctuation correction rules."""

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


class SyntaxCommaSpacingRule:
    """Fix missing spaces after comma punctuation."""

    _CATEGORY = Category.PUNCTUATION

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.comma_space")
        self._pattern = re.compile(r"(?<!\d),(?=[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ])")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()

        findings: list[Finding] = []
        for match in self._pattern.finditer(text):
            start = match.start()
            end = match.end()
            if _is_abbreviation_fragment(text, start):
                continue
            findings.append(
                _make_insertion_or_replacement(
                    start,
                    end,
                    text[start:end],
                    ", ",
                    self.source,
                    category=Category.PUNCTUATION,
                    message="Brakuje spacji po przecinku.",
                    explanation=(
                        "W standardowej interpunkcji po przecinku zostawiamy spację."
                    ),
                )
            )

        return tuple(findings)


class SyntaxSentenceSpacingRule:
    """Fix a missing space between two sentence-like fragments."""

    _CATEGORY = Category.PUNCTUATION

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.sentence_space")
        self._pattern = re.compile(
            r"(?<!\d)(?<!\bnp)(?<!\bitp)(?<!\btj)\.(?=[A-ZĄĆĘŁŃÓŚŹŻ])"
        )

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        return tuple(
            _make_insertion_or_replacement(
                match.start(),
                match.end(),
                ".",
                ". ",
                self.source,
                category=self._CATEGORY,
                message="Brakuje spacji między zdaniami.",
                explanation="Po kropce kończącej zdanie stawiamy spację.",
            )
            for match in self._pattern.finditer(text)
        )


class SyntaxListSpacingRule:
    """Fix missing space after markdown-like list markers."""

    _CATEGORY = Category.SYNTAX

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.list_space")
        self._pattern = re.compile(r"(?m)(?:^|\n)([0-9]+\.|-|\*)(?=\S)")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()

        findings: list[Finding] = []
        for match in self._pattern.finditer(text):
            marker = match.group(1)
            marker_end = match.end(1)

            if marker.endswith("."):
                following = text[marker_end : marker_end + 1]
                if following.isdigit():
                    continue
                if following in "\r\n":
                    continue

            if marker_end < len(text) and text[marker_end] not in " \t":
                findings.append(
                    _make_insertion_or_replacement(
                        marker_end,
                        marker_end,
                        "",
                        " ",
                        self.source,
                        category=Category.SYNTAX,
                        message="Brakuje spacji po znaczniku listy.",
                        explanation=(
                            "Znacznik listy powinien być oddzielony pojedynczą spacją "
                            "od treści elementu."
                        ),
                    )
                )

        return tuple(findings)


class SyntaxQuoteSpacingRule:
    """Add a missing space after a quote when attached to text."""

    _CATEGORY = Category.PUNCTUATION

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.quote_space")
        self._pattern = re.compile(r"([\"“”„])(?=[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ])")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()

        findings: list[Finding] = []
        for match in self._pattern.finditer(text):
            start = match.start()
            end = match.end()
            if start > 0 and not text[start - 1].isspace():
                findings.append(
                    _make_insertion_or_replacement(
                        start,
                        end,
                        text[start:end],
                        f"{text[start]} ",
                        self.source,
                        category=Category.PUNCTUATION,
                        message="Brakuje spacji po znaku cudzysłowia.",
                        explanation=(
                            "Między znakiem otwierającym a następującym wyrazem "
                            "zazwyczaj pozostawiamy spację."
                        ),
                    )
                )

        return tuple(findings)


def _is_abbreviation_fragment(text: str, comma_end: int) -> bool:
    before = text[:comma_end].rsplit(" ", 1)[-1]
    if before.lower() in _ABBREVIATIONS:
        return True
    return False


def _make_insertion_or_replacement(
    start: int,
    end: int,
    original: str,
    replacement: str,
    source: Source,
    category: Category,
    *,
    message: str,
    explanation: str,
) -> Finding:
    return Finding.create(
        category=category,
        severity=Severity.SUGGESTION,
        message=message,
        explanation=explanation,
        original=original,
        suggestion=replacement,
        start=start,
        end=end,
        confidence=Confidence(0.9),
        source=source,
    )


_ABBREVIATIONS = frozenset({"itp", "np", "tj", "m.in", "i.e", "np."})


__all__ = [
    "SyntaxCommaSpacingRule",
    "SyntaxSentenceSpacingRule",
    "SyntaxListSpacingRule",
    "SyntaxQuoteSpacingRule",
]
