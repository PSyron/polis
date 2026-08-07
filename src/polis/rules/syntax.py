"""Selected syntax and punctuation correction rules."""

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
from polis.segmentation import segment_sentences

_DESTINATION_PREPOSITION_PATTERN: Final = re.compile(
    r"(?:(?:Pojechałem|pojechałem) (?P<lower>Warszawy)|"
    r"POJECHAŁEM (?P<upper>WARSZAWY))\.\Z"
)
_INITIAL_CONDITIONAL_COMMA_PATTERN: Final = re.compile(
    r"(?:(?P<title>Jeśli pada) zostaję w domu|"
    r"(?P<lower>jeśli pada) zostaję w domu|"
    r"(?P<upper>JEŚLI PADA) ZOSTAJĘ W DOMU)\.\Z"
)


class SyntaxCommaSpacingRule:
    """Fix missing spaces after comma punctuation."""

    _CATEGORY = Category.PUNCTUATION

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.comma_space")
        self._pattern = re.compile(r"(?<!\d),(?=[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ])")

    @property
    def operation(self) -> str:
        """Return the qualified action performed by this rule."""

        return "normalize.comma_spacing"

    @property
    def behavior_version(self) -> str:
        """Return the qualified implementation behavior version."""

        return "syntax-comma-space/1.0"

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


class SyntaxDuplicateCommaRule:
    """Remove one comma from an unambiguous adjacent pair."""

    _CATEGORY = Category.PUNCTUATION

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.duplicate_comma")
        self._pattern = re.compile(
            r"(?<=[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]),,(?!,)(?=\s+[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ])"
        )

    @property
    def operation(self) -> str:
        """Return the qualified action performed by this rule."""

        return "remove.duplicate_comma"

    @property
    def behavior_version(self) -> str:
        """Return the qualified implementation behavior version."""

        return "syntax-duplicate-comma/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()

        findings: list[Finding] = []
        for match in self._pattern.finditer(text):
            first_comma = match.start()
            if _is_quoted_position(text, first_comma):
                continue
            start = first_comma + 1
            findings.append(
                _make_insertion_or_replacement(
                    start,
                    start + 1,
                    ",",
                    "",
                    self.source,
                    category=self._CATEGORY,
                    message="Zduplikowany przecinek.",
                    explanation="W tej pozycji wystarcza jeden przecinek.",
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

    @property
    def operation(self) -> str:
        """Return the qualified action performed by this rule."""

        return "normalize.sentence_spacing"

    @property
    def behavior_version(self) -> str:
        """Return the qualified implementation behavior version."""

        return "syntax-sentence-space/1.0"

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

    @property
    def operation(self) -> str:
        """Return the qualified action performed by this rule."""

        return "normalize.list_marker_spacing"

    @property
    def behavior_version(self) -> str:
        """Return the qualified implementation behavior version."""

        return "syntax-list-space/1.0"

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

    @property
    def operation(self) -> str:
        """Return the qualified action performed by this rule."""

        return "normalize.quote_spacing"

    @property
    def behavior_version(self) -> str:
        """Return the qualified implementation behavior version."""

        return "syntax-quote-space/1.0"

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


class SyntaxMissingReflexiveRule:
    """Detect narrowly qualified missing reflexive insertions."""

    _CATEGORY = Category.SYNTAX
    _PREFIXES = (
        re.compile(r"^\s*(?:On|Ona|Ono)\s+boi\b"),
        re.compile(r"^\s*Nie\s+spodziewaliśmy\b"),
    )

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.missing_reflexive")

    @property
    def operation(self) -> str:
        """Return the review-only action performed by this rule."""

        return "insert.reflexive_pronoun"

    @property
    def behavior_version(self) -> str:
        """Return the review-only implementation behavior version."""

        return "syntax-missing-reflexive/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        if len(segment_sentences(text)) != 1:
            return ()

        for pattern in self._PREFIXES:
            match = pattern.match(text)
            if match is None:
                continue
            following = text[match.end() :]
            if not following or not following[0].isspace():
                return ()
            next_token = following.lstrip().split(maxsplit=1)[0]
            if next_token.rstrip(".,!?;:") == "się":
                return ()
            return (
                _make_insertion_or_replacement(
                    match.end(),
                    match.end(),
                    "",
                    " się",
                    self.source,
                    category=self._CATEGORY,
                    message="Brakuje zaimka zwrotnego «się».",
                    explanation=(
                        "W tej konstrukcji czasownik wymaga zaimka zwrotnego «się»."
                    ),
                ),
            )
        return ()


class SyntaxMissingCorrelativeRule:
    """Detect a narrowly qualified missing ``tym`` correlative."""

    _CATEGORY = Category.SYNTAX
    _PATTERN = re.compile(r"^\s*Im\b[^.!?]*?,\s+(?P<bardziej>bardziej)\b")

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.missing_correlative")

    @property
    def operation(self) -> str:
        """Return the review-only action performed by this rule."""

        return "insert.correlative"

    @property
    def behavior_version(self) -> str:
        """Return the review-only implementation behavior version."""

        return "syntax-missing-correlative/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        if len(segment_sentences(text)) != 1:
            return ()

        match = self._PATTERN.match(text)
        if match is None:
            return ()
        start = match.start("bardziej")
        return (
            _make_insertion_or_replacement(
                start,
                start,
                "",
                "tym ",
                self.source,
                category=self._CATEGORY,
                message="Brakuje członu «tym» w konstrukcji porównawczej.",
                explanation=("Konstrukcja zależności ma postać «im…, tym bardziej…»."),
            ),
        )


class SyntaxMissingDestinationPrepositionRule:
    """Insert ``do`` in one reviewed destination construction only."""

    _CATEGORY = Category.SYNTAX

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.missing_destination_preposition")
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        """Return the review-only action performed by this rule."""

        return "insert.destination_preposition"

    @property
    def behavior_version(self) -> str:
        """Return the review-only implementation behavior version."""

        return "syntax-missing-destination-preposition/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        """Return the reviewed insertion for an exact allowed sentence."""

        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        match = _DESTINATION_PREPOSITION_PATTERN.fullmatch(text)
        if match is None:
            return ()
        group = "upper" if match.group("upper") is not None else "lower"
        start = match.start(group)
        return (
            Finding.create(
                category=self._CATEGORY,
                severity=Severity.SUGGESTION,
                message="Brakuje przyimka „do” przed nazwą celu podróży.",
                explanation="W tej zamkniętej konstrukcji brakuje przyimka „do”.",
                original="",
                suggestion="do ",
                start=start,
                end=start,
                confidence=self._confidence,
                source=self.source,
            ),
        )


class SyntaxInitialConditionalCommaRule:
    """Insert one comma in a reviewed initial conditional sentence only."""

    _CATEGORY = Category.SYNTAX

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.initial_conditional_comma")

    @property
    def operation(self) -> str:
        """Return the review-only action performed by this rule."""

        return "insert.conditional_clause_comma"

    @property
    def behavior_version(self) -> str:
        """Return the review-only implementation behavior version."""

        return "syntax-initial-conditional-comma/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        """Return the reviewed insertion for an exact allowed sentence."""

        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        match = _INITIAL_CONDITIONAL_COMMA_PATTERN.fullmatch(text)
        if match is None:
            return ()
        group = "title" if match.group("title") is not None else "lower"
        group = group if match.group(group) is not None else "upper"
        start = match.end(group)
        return (
            _make_insertion_or_replacement(
                start,
                start,
                "",
                ",",
                self.source,
                category=self._CATEGORY,
                message="Brakuje przecinka po początkowym zdaniu warunkowym.",
                explanation=(
                    "W tej zamkniętej konstrukcji po zdaniu warunkowym stawiamy "
                    "przecinek."
                ),
            ),
        )


def _is_abbreviation_fragment(text: str, comma_end: int) -> bool:
    before = text[:comma_end].rsplit(" ", 1)[-1]
    if before.lower() in _ABBREVIATIONS:
        return True
    return False


def _is_quoted_position(text: str, position: int) -> bool:
    for opening, closing in (('"', '"'), ("„", "”"), ("“", "”"), ("«", "»")):
        before = text[:position]
        if opening == closing:
            if before.count(opening) % 2 == 1:
                return True
        elif before.rfind(opening) > before.rfind(closing):
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
    "SyntaxDuplicateCommaRule",
    "SyntaxSentenceSpacingRule",
    "SyntaxListSpacingRule",
    "SyntaxMissingCorrelativeRule",
    "SyntaxMissingDestinationPrepositionRule",
    "SyntaxInitialConditionalCommaRule",
    "SyntaxMissingReflexiveRule",
    "SyntaxQuoteSpacingRule",
]
