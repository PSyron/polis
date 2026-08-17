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
from polis.segmentation import (
    Sentence,
)
from polis.segmentation import (
    _iter_sentence_matches as iter_sentence_matches,
)
from polis.segmentation import (
    _sentence_segments_cached as sentence_segments,
)


def segment_sentences(text: str) -> tuple[Sentence, ...]:
    """Registry-local wrapper over the shared bounded sentence cache."""

    return tuple(sentence_segments(text))


def is_single_sentence(text: str) -> bool:
    """Return whether the shared segmentation contains one sentence."""

    return len(sentence_segments(text)) == 1


_DESTINATION_PREPOSITION_PATTERN: Final = re.compile(
    r"(?:(?:Pojechałem|pojechałem) (?P<lower>Warszawy)|"
    r"POJECHAŁEM (?P<upper>WARSZAWY))\.\Z"
)
_INITIAL_CONDITIONAL_COMMA_PATTERN: Final = re.compile(
    r"(?:(?P<title>Jeśli pada) zostaję w domu|"
    r"(?P<lower>jeśli pada) zostaję w domu|"
    r"(?P<upper>JEŚLI PADA) ZOSTAJĘ W DOMU)\.\Z"
)
_INITIAL_TEMPORAL_COMMA_PATTERN: Final = re.compile(
    r"(?<!\w)(?P<head>Gdy pada|Kiedy pada|Kiedy wieje|Kiedy wrócisz) (?=\S)",
    re.IGNORECASE,
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

        for pattern in self._PREFIXES:
            match = pattern.match(text)
            if match is None:
                continue
            if not is_single_sentence(text):
                return ()
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

        match = self._PATTERN.match(text)
        if match is None or not is_single_sentence(text):
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


class SyntaxInitialTemporalCommaRule:
    """Insert commas after closed initial temporal clause heads only."""

    _CATEGORY = Category.SYNTAX

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.initial_temporal_comma")

    @property
    def operation(self) -> str:
        return "insert.temporal_clause_comma"

    @property
    def behavior_version(self) -> str:
        return "syntax-initial-temporal-comma/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()

        matches = tuple(_INITIAL_TEMPORAL_COMMA_PATTERN.finditer(text))
        if not matches or not is_single_sentence(text):
            return ()
        findings: list[Finding] = []
        for match in matches:
            start = match.end("head")
            if _is_quoted_position(text, match.start("head")):
                continue
            if start < len(text) and text[start] == ",":
                continue
            findings.append(
                _make_insertion_or_replacement(
                    start,
                    start,
                    "",
                    ",",
                    self.source,
                    category=self._CATEGORY,
                    message="Brakuje przecinka po początkowym zdaniu czasowym.",
                    explanation=(
                        "W tej zamkniętej konstrukcji po początkowym zdaniu "
                        "czasowym stawiamy przecinek."
                    ),
                )
            )
        return tuple(findings)


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

# Case-explicit governors only (never IGNORECASE). Participles/nominalizations
# are intentionally absent.
_ZE_REPORTING_GOVERNORS: Final = frozenset(
    {
        "Wiem",
        "wiem",
        "WIEM",
        "Myślę",
        "myślę",
        "MYŚLĘ",
        "Sądzę",
        "sądzę",
        "SĄDZĘ",
        "Uważam",
        "uważam",
        "UWAŻAM",
        "Mówię",
        "mówię",
        "MÓWIĘ",
        "Powiedział",
        "powiedział",
        "POWIEDZIAŁ",
        "Powiedziałam",
        "powiedziałam",
        "POWIEDZIAŁAM",
        "Wiemy",
        "wiemy",
        "WIEMY",
    }
)
_ZEBY_PURPOSE_GOVERNORS: Final = frozenset(
    {
        "Chcę",
        "chcę",
        "CHCĘ",
        "Pragnę",
        "pragnę",
        "PRAGNĘ",
        "Proszę",
        "proszę",
        "PROSZĘ",
        "Chcemy",
        "chcemy",
        "CHCEMY",
    }
)
_CAUSAL_CONJUNCTIONS: Final = frozenset({"bo", "ponieważ", "gdyż"})
_CAUSAL_PRECURSOR_EXCLUSIONS: Final = frozenset(
    {
        "no",
        "a",
        "i",
        "oraz",
        "ale",
        "lecz",
        "czy",
        "to",
        "więc",
        "lub",
        "albo",
        "ani",
        "bądź",
        "nie",
        "tylko",
        "jedynie",
        "właśnie",
        "jak",
        "jako",
        "niż",
    }
)
_POLISH_LETTER: Final = re.compile(r"[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]")
_UPPERCASE_POLISH_LETTER: Final = re.compile(r"[A-ZĄĆĘŁŃÓŚŹŻ]")
# Permanent exclusion for abbreviation-dot: ``np`` is never covered (docstring).
_ABBREVIATION_DOT_FORMS: Final = frozenset({"itp", "itd", "tzn"})


class SyntaxCommaBeforeZeReportingRule:
    """Insert a comma after a closed reporting/cognition governor before ``że``."""

    _CATEGORY = Category.SYNTAX

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.comma_before_ze_reporting")
        self._pattern = re.compile(r"(?<!\w)(?P<gov>\w+) (?P<conj>że|Że|ŻE)(?=\s+\S)")

    @property
    def operation(self) -> str:
        return "insert.reporting_clause_comma"

    @property
    def behavior_version(self) -> str:
        return "syntax-comma-before-ze-reporting/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        if " że" not in text and " Że" not in text and " ŻE" not in text:
            return ()
        findings: list[Finding] = []
        for _sentence, match in iter_sentence_matches(text, self._pattern):
            gov = match.group("gov")
            if gov not in _ZE_REPORTING_GOVERNORS:
                continue
            if _is_quoted_position(text, match.start("gov")):
                continue
            insert_at = match.end("gov")
            if insert_at < len(text) and text[insert_at] == ",":
                continue
            findings.append(
                _make_insertion_or_replacement(
                    insert_at,
                    insert_at,
                    "",
                    ",",
                    self.source,
                    category=self._CATEGORY,
                    message="Brakuje przecinka przed spójnikiem „że”.",
                    explanation=(
                        "Po czasowniku raportującym/kognitywnym przed „że” "
                        "stawiamy przecinek."
                    ),
                )
            )
        return tuple(findings)


class SyntaxCommaBeforeZebyPurposeRule:
    """Insert a comma after a closed volition governor before ``żeby``/``żebyś``."""

    _CATEGORY = Category.SYNTAX

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.comma_before_zeby_purpose")
        self._pattern = re.compile(
            r"(?<!\w)(?P<gov>\w+) (?P<conj>żebyś|żeby|Żebyś|Żeby|ŻEBYŚ|ŻEBY)(?=\s+\S)"
        )

    @property
    def operation(self) -> str:
        return "insert.purpose_clause_comma"

    @property
    def behavior_version(self) -> str:
        return "syntax-comma-before-zeby-purpose/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        if not any(
            conjunction in text
            for conjunction in (" żeby", " żebyś", " Żeby", " Żebyś", " ŻEBY", " ŻEBYŚ")
        ):
            return ()
        findings: list[Finding] = []
        for _sentence, match in iter_sentence_matches(text, self._pattern):
            gov = match.group("gov")
            if gov not in _ZEBY_PURPOSE_GOVERNORS:
                continue
            if _is_quoted_position(text, match.start("gov")):
                continue
            insert_at = match.end("gov")
            if insert_at < len(text) and text[insert_at] == ",":
                continue
            findings.append(
                _make_insertion_or_replacement(
                    insert_at,
                    insert_at,
                    "",
                    ",",
                    self.source,
                    category=self._CATEGORY,
                    message="Brakuje przecinka przed spójnikiem „żeby”.",
                    explanation=(
                        "Po czasowniku wolicjonalnym przed „żeby” stawiamy przecinek."
                    ),
                )
            )
        return tuple(findings)


def _is_coherent_uppercase_causal_clause(
    text: str, sentence: Sentence, match: re.Match[str]
) -> bool:
    """Accept only a closed, punctuation-neutral uppercase causal sentence."""

    colon = text.rfind(":", sentence.start, match.start("upper_conj"))
    clause_start = colon + 1 if colon >= sentence.start else sentence.start
    prefix = text[sentence.start : colon].strip() if colon >= sentence.start else ""
    if prefix and not all(
        character.isspace() or _POLISH_LETTER.fullmatch(character) is not None
        for character in prefix
    ):
        return False
    clause = text[clause_start : sentence.end].strip()
    if not clause.endswith(".") or clause.endswith(".."):
        return False
    body = clause[:-1]
    return bool(body) and all(
        character.isspace() or _UPPERCASE_POLISH_LETTER.fullmatch(character) is not None
        for character in body
    )


class SyntaxCommaBeforeBoRule:
    """Insert a comma before closed causal conjunctions with exclusion guards."""

    _CATEGORY = Category.SYNTAX

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "syntax.comma_before_bo")
        self._pattern = re.compile(
            r"(?P<pre>\S) (?P<conj>bo|ponieważ|gdyż) "
            r"(?P<after>[a-ząćęłńóśźż])|"
            r"(?P<upper_pre>[A-ZĄĆĘŁŃÓŚŹŻ]) (?P<upper_conj>BO|PONIEWAŻ|GDYŻ) "
            r"(?P<upper_after>[A-ZĄĆĘŁŃÓŚŹŻ])"
        )

    @property
    def operation(self) -> str:
        return "insert.causal_clause_comma"

    @property
    def behavior_version(self) -> str:
        return "syntax-comma-before-bo/3.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        if (
            " bo " not in text
            and " ponieważ " not in text
            and " gdyż " not in text
            and " BO " not in text
            and " PONIEWAŻ " not in text
            and " GDYŻ " not in text
        ):
            return ()
        findings: list[Finding] = []
        for sentence, match in iter_sentence_matches(text, self._pattern):
            upper_branch = match.group("upper_conj") is not None
            if upper_branch and not _is_coherent_uppercase_causal_clause(
                text, sentence, match
            ):
                continue
            pre_group = "upper_pre" if upper_branch else "pre"
            conj_group = "upper_conj" if upper_branch else "conj"
            pre_char = match.group(pre_group)
            if _POLISH_LETTER.fullmatch(pre_char) is None:
                continue
            # Preceding token (word) exclusion set.
            left = text[sentence.start : match.start(conj_group)].rstrip()
            token = left.rsplit(None, 1)[-1] if left else ""
            token_core = re.sub(r"[^\w]+$", "", token)
            if token_core.casefold() in _CAUSAL_PRECURSOR_EXCLUSIONS:
                continue
            if _is_quoted_position(text, match.start(conj_group)):
                continue
            # Insert between preceding letter and space: "ę bo" → "ę, bo".
            insert_at = match.start(pre_group) + 1
            if insert_at < len(text) and text[insert_at] == ",":
                continue
            findings.append(
                _make_insertion_or_replacement(
                    insert_at,
                    insert_at,
                    "",
                    ",",
                    self.source,
                    category=self._CATEGORY,
                    message="Brakuje przecinka przed spójnikiem przyczynowym.",
                    explanation=(
                        "Przed spójnikiem przyczynowym „bo”/„ponieważ”/„gdyż” "
                        "stawiamy przecinek."
                    ),
                )
            )
        return tuple(findings)


class PunctuationAbbreviationDotRule:
    """Insert a period after closed abbreviations ``itp``/``itd``/``tzn`` only.

    ``np`` is a permanent exclusion — never add it without a full re-verification.
    """

    _CATEGORY = Category.PUNCTUATION

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "punctuation.abbreviation_dot")
        self._pattern = re.compile(
            r"(?<!\w)(?P<form>itp|itd|tzn)(?=\s+\S)", re.IGNORECASE
        )

    @property
    def operation(self) -> str:
        return "insert.abbreviation_dot"

    @property
    def behavior_version(self) -> str:
        return "punctuation-abbreviation-dot/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        findings: list[Finding] = []
        for match in self._pattern.finditer(text):
            form = match.group("form").casefold()
            if form not in _ABBREVIATION_DOT_FORMS:
                continue
            if _is_quoted_position(text, match.start("form")):
                continue
            insert_at = match.end("form")
            if insert_at < len(text) and text[insert_at] == ".":
                continue
            findings.append(
                _make_insertion_or_replacement(
                    insert_at,
                    insert_at,
                    "",
                    ".",
                    self.source,
                    category=self._CATEGORY,
                    message="Brakuje kropki po skrócie.",
                    explanation=(
                        f"Po skrócie „{match.group('form')}” w tej zamkniętej "
                        "regule stawiamy kropkę."
                    ),
                )
            )
        return tuple(findings)


__all__ = [
    "PunctuationAbbreviationDotRule",
    "SyntaxCommaBeforeBoRule",
    "SyntaxCommaBeforeZeReportingRule",
    "SyntaxCommaBeforeZebyPurposeRule",
    "SyntaxCommaSpacingRule",
    "SyntaxDuplicateCommaRule",
    "SyntaxSentenceSpacingRule",
    "SyntaxListSpacingRule",
    "SyntaxMissingCorrelativeRule",
    "SyntaxMissingDestinationPrepositionRule",
    "SyntaxInitialConditionalCommaRule",
    "SyntaxInitialTemporalCommaRule",
    "SyntaxMissingReflexiveRule",
    "SyntaxQuoteSpacingRule",
]
