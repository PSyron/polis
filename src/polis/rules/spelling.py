"""High-precision spelling rules."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType
from typing import Final, cast

from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)
from polis.rules.syntax import _is_quoted_position

_MENTION_WRAPPERS: Final = frozenset(
    {('"', '"'), ("`", "`"), ("„", "”"), ("“", "”"), ("«", "»")}
)
_METALINGUISTIC_QUOTE_CUES: Final = (
    "napis",
    "napisano",
    "napisy",
    "słowo",
    "wyraz",
    "forma",
    "termin",
    "przykład",
    "przyklad",
    "pisownia",
)
_METALINGUISTIC_QUOTE_CUE_RE: Final = re.compile(
    r"(?:^|[\s(\[{:;,.!?])(?:"
    + "|".join(re.escape(cue) for cue in _METALINGUISTIC_QUOTE_CUES)
    + r")\s*(?:(?:[:;,!.?]|[-–—])\s*)?$",
    flags=re.IGNORECASE,
)
_DIALOGUE_QUOTE_CUES: Final = (
    "powiedział",
    "powiedziała",
    "powiedzieli",
    "rzekł",
    "rzekła",
    "zapytał",
    "zapytała",
    "krzyknął",
    "krzyknęła",
    "odparł",
    "odparła",
)
_DIALOGUE_QUOTE_CUE_RE: Final = re.compile(
    r"(?:^|[\s(\[{:;,.!?])(?:"
    + "|".join(re.escape(cue) for cue in _DIALOGUE_QUOTE_CUES)
    + r")(?:\s+\w+){0,4}\s*(?:(?::|[-–—])\s*)$",
    flags=re.IGNORECASE,
)
_ARCY_BOUNDARY_MARKS: Final = frozenset("()[]{}<>\"'`„”“«»‘’‹›")
_ARCY_CONTEXT_PAIRS: Final = (
    ('"', '"'),
    ("`", "`"),
    ("'", "'"),
    ("„", "”"),
    ("“", "”"),
    ("‘", "’"),
    ("«", "»"),
    ("‹", "›"),
    ("(", ")"),
    ("[", "]"),
    ("{", "}"),
    ("<", ">"),
)
_ARCY_CONTEXT_MARKS: Final = frozenset(
    character for pair in _ARCY_CONTEXT_PAIRS for character in pair
)
_ARCY_APOSTROPHE_NAME_PARTS: Final = (
    "APOSTROPHE",
    "GERESH",
    "PRIME",
    "QUOTATION MARK",
    "REVERSED COMMA",
    "TURNED COMMA",
)


def _is_arcy_apostrophe_like(character: str) -> bool:
    name = unicodedata.name(character, "")
    return any(part in name for part in _ARCY_APOSTROPHE_NAME_PARTS)


def _is_arcy_sentence_closing_mark(character: str) -> bool:
    return character in _SENTENCE_CLOSING_MARKS or unicodedata.category(character) in {
        "Pe",
        "Pf",
    }


def _is_arcy_boundary_mark(character: str) -> bool:
    return character in _ARCY_BOUNDARY_MARKS or unicodedata.category(character) in {
        "Ps",
        "Pe",
        "Pi",
        "Pf",
    }


def _arcy_matching_opening_index(
    text: str, closing_index: int, opening: str, closing: str
) -> int | None:
    if opening == closing:
        return text.rfind(opening, 0, closing_index)
    depth = 0
    for index in range(closing_index, -1, -1):
        character = text[index]
        if character == closing:
            depth += 1
        elif character == opening:
            depth -= 1
            if depth == 0:
                return index
    return None


# Characters that glue a match into a larger address/identifier host token.
_HOST_TOKEN_CHARS: Final = frozenset("./:@?#%&+~_=-")
# Sentence/clause punctuation stripped from host edges so `wogole.` stays prose.
_HOST_EDGE_TRIM: Final = frozenset('.,;:!?)]}"»”\'„“«"')
_SENTENCE_CLOSING_MARKS: Final = frozenset("'\"”’»›)]}")
_ARCY_LINE_BREAKS: Final = frozenset("\r\n\u0085\u2028\u2029")
_SCHEME_RE: Final = re.compile(r"(?i)\b(?:https?|ftp)://")
_DOMAINISH_RE: Final = re.compile(
    r"(?i)\b(?:www\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b"
)
_LOWER_COMPATIBILITY_VARIANTS: Final = {"k": "K"}


def _host_token_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Return the non-space host token covering ``[start, end)``.

    Leading/trailing sentence punctuation is trimmed so a free-standing typo
    followed by ``.`` or ``,`` is not treated as a domain or identifier.
    """
    left = start
    while left > 0 and not text[left - 1].isspace():
        left -= 1
    right = end
    while right < len(text) and not text[right].isspace():
        right += 1
    while left < start and text[left] in _HOST_EDGE_TRIM:
        left += 1
    while right > end and text[right - 1] in _HOST_EDGE_TRIM:
        right -= 1
    return left, right


def _is_email_context(text: str, start: int, end: int) -> bool:
    """True when the match is the local-part or a domain label of an e-mail."""
    if end < len(text) and text[end] == "@":
        # local-part@domain
        domain = text[end + 1 : end + 1 + 254]
        if not domain or domain[0].isspace():
            return True  # incomplete / ambiguous → abstain
        return bool(re.match(r"[^\s@]+", domain))
    if start > 0 and text[start - 1] == "@":
        # local@domain-label...
        return True
    left, right = _host_token_span(text, start, end)
    host = text[left:right]
    if "@" not in host:
        return False
    # Match sits inside a single token that already contains `@`.
    return True


def _is_url_or_domain_context(text: str, start: int, end: int) -> bool:
    """True when the match sits in a URL, bare domain, or path-like host token."""
    left, right = _host_token_span(text, start, end)
    host = text[left:right]
    if not host:
        return False
    if _SCHEME_RE.search(host):
        return True
    if any(marker in host for marker in ("/", "?", "#")):
        # Path or query on a host-like token (with or without scheme).
        # Require a domain-ish prefix or scheme-like colon to avoid `a/b` prose.
        if "://" in host or _DOMAINISH_RE.search(host):
            return True
        # Conservative: slash-joined tokens with a dot somewhere look like paths.
        if "." in host and "/" in host:
            return True
        return False
    # Sentence glue without space: ``gotowa.Jestes`` is prose, not a hostname.
    if (
        start >= 2
        and text[start - 1] == "."
        and text[start - 2].isalpha()
        and not any(marker in host for marker in ("/", "?", "#", "://"))
    ):
        return False
    # Bare domain or domain label adjacency: example.org or label inside it.
    if _DOMAINISH_RE.fullmatch(host) or _DOMAINISH_RE.search(host):
        # Avoid treating ordinary Polish abbreviations like "m.in." as domains
        # when the match is a free-standing sentence word equal to the host.
        if host == text[start:end]:
            return False
        return True
    # Adjacent URL punctuation glued without spaces (rare after tokenization).
    if start > 0 and text[start - 1] in {"/", "?", "#"}:
        return True
    if end < len(text) and text[end] in {"/", "?", "#"}:
        return True
    return False


def _is_mixed_case_identifier_context(text: str, start: int, end: int) -> bool:
    """True when the match is glued into a code-like identifier host token.

    Sentence-case, all-caps, and free-standing mixed-case *forms* of the typo
    itself remain eligible; only host tokens with identifier punctuation or
    digits attached to the match are treated as identifiers.
    """
    left, right = _host_token_span(text, start, end)
    if left == start and right == end:
        return False
    host = text[left:right]
    # Missing space after sentence end: ``gotowa.Jestes`` is prose, not code.
    if re.fullmatch(r"[\w]+\.[\w]+", host, flags=re.UNICODE) and not any(
        marker in host for marker in ("/", "?", "#", "@", "_", "-")
    ):
        # Two alphabetic segments joined by a single period without URL markers.
        left_part, right_part = host.split(".", 1)
        if left_part.isalpha() and right_part.isalpha():
            return False
    # Digits or underscores anywhere in the host token → identifier-like.
    if any(ch.isdigit() or ch == "_" for ch in host):
        return True
    # Hyphenated multi-segment host that is not a domain/path already handled.
    if "-" in host and not _DOMAINISH_RE.search(host):
        return True
    # Internal host characters other than letters (still non-space).
    for index, ch in enumerate(host):
        absolute = left + index
        if start <= absolute < end:
            continue
        if ch in _HOST_TOKEN_CHARS or ch.isdigit():
            return True
    return False


def should_abstain_literal_context(
    text: str,
    start: int,
    end: int,
    *,
    quoted_position: bool | None = None,
    ignore_wrapped_mention: bool = False,
    allow_sentence_question: bool = False,
) -> bool:
    """Return True when a closed literal match must not emit a suggestion.

    Fail-closed: any recognized non-prose context abstains. Unrecognized
    ambiguous host shapes that look like addresses or quotes also abstain.
    """
    if start < 0 or end > len(text) or start >= end:
        return True
    if not ignore_wrapped_mention and _is_wrapped_mention(text, start, end):
        return True
    if quoted_position is None:
        quoted_position = _is_quoted_position(text, start)
    if quoted_position:
        return True
    if _is_email_context(text, start, end):
        return True
    if _is_url_or_domain_context(text, start, end) and not (
        allow_sentence_question
        and end < len(text)
        and text[end] == "?"
        and (
            end + 1 == len(text)
            or text[end + 1].isspace()
            or text[end + 1] in _HOST_EDGE_TRIM
        )
    ):
        return True
    if _is_mixed_case_identifier_context(text, start, end):
        return True
    return False


def _is_wrapped_mention(text: str, start: int, end: int) -> bool:
    if start <= 0 or end >= len(text):
        return False
    left = text[start - 1]
    right = text[end]
    if (left, right) in _MENTION_WRAPPERS:
        return True
    # Code-like mentions: `token` or `token()`.
    if left == "`":
        rest = text[end:]
        return rest.startswith("`") or rest.startswith("()`")
    return False


_CO_QUOTE_WRAPPERS: Final = (
    ('"', '"'),
    ("'", "'"),
    ("`", "`"),
    ("„", "”"),
    ("“", "”"),
    ("‘", "’"),
    ("‚", "’"),
    ("«", "»"),
    ("‹", "›"),
    ("<", ">"),
    ("「", "」"),
    ("『", "』"),
    ("〈", "〉"),
    ("《", "》"),
)
_CO_SAFE_BOUNDARY_CHARACTERS: Final = frozenset(
    ".,;:!?…()[]{}<>-–—'\"`„”“«»‘’‹›「」『』〈〉《》"
)
_CO_EXTENDED_HOST_TOKEN_CHARS: Final = frozenset("./:@?#%&+~_-=\\.$()[]{}|^")
_CO_MENTION_TRAILING_PUNCTUATION: Final = frozenset(".,;:!?…")
_CO_CUE_LOOKBEHIND: Final = 256


class _CoQuoteFrame:
    __slots__ = ("opening", "closing", "opening_index", "closing_index", "valid")

    def __init__(self, opening: str, closing: str, opening_index: int) -> None:
        self.opening = opening
        self.closing = closing
        self.opening_index = opening_index
        self.closing_index: int | None = None
        self.valid = True


class _CoMatchQuoteContext:
    __slots__ = ("frames", "uncertain")

    def __init__(self, frames: tuple[_CoQuoteFrame, ...], uncertain: bool) -> None:
        self.frames = frames
        self.uncertain = uncertain


class _CoPreparedContext:
    __slots__ = ("matches",)

    def __init__(self, matches: dict[int, _CoMatchQuoteContext]) -> None:
        self.matches = matches

    def for_start(self, start: int) -> _CoMatchQuoteContext | None:
        return self.matches.get(start)


def _prepare_co_context(text: str, starts: tuple[int, ...]) -> _CoPreparedContext:
    pairs = dict(_CO_QUOTE_WRAPPERS)
    closing_characters = {
        closing for opening, closing in _CO_QUOTE_WRAPPERS if opening != closing
    }
    target_starts = set(starts)
    contexts: dict[int, _CoMatchQuoteContext] = {}
    stack: list[_CoQuoteFrame] = []
    uncertain = False

    for index, character in enumerate(text):
        if index in target_starts:
            contexts[index] = _CoMatchQuoteContext(tuple(stack), uncertain)

        if (
            character == "'"
            and index > 0
            and index + 1 < len(text)
            and text[index - 1].isalnum()
            and text[index + 1].isalnum()
        ):
            continue

        closing = pairs.get(character)
        if closing is not None:
            if closing == character and stack and stack[-1].closing == character:
                stack.pop().closing_index = index
            else:
                stack.append(_CoQuoteFrame(character, closing, index))
            continue

        if character in closing_characters:
            if stack and stack[-1].closing == character:
                stack.pop().closing_index = index
            else:
                for frame in stack:
                    frame.valid = False
                stack.clear()
                uncertain = True

    return _CoPreparedContext(contexts)


def _co_quote_is_dialogue(text: str, frame: _CoQuoteFrame) -> bool:
    if frame.opening == "`":
        return False
    return bool(
        _DIALOGUE_QUOTE_CUE_RE.search(
            text[max(0, frame.opening_index - _CO_CUE_LOOKBEHIND) : frame.opening_index]
        )
    )


def _co_quote_is_metalinguistic(text: str, frame: _CoQuoteFrame) -> bool:
    return bool(
        _METALINGUISTIC_QUOTE_CUE_RE.search(
            text[max(0, frame.opening_index - _CO_CUE_LOOKBEHIND) : frame.opening_index]
        )
    )


def _is_co_wrapped_mention(text: str, start: int, end: int) -> bool:
    if start <= 0 or end >= len(text):
        return False
    left = text[start - 1]
    for opening, closing in _CO_QUOTE_WRAPPERS:
        if left != opening:
            continue
        closing_start = end
        while (
            closing_start < len(text)
            and text[closing_start] in _CO_MENTION_TRAILING_PUNCTUATION
        ):
            closing_start += 1
        if closing_start < len(text) and text[closing_start] == closing:
            return True
    return False


def _is_co_unicode_extension_context(text: str, start: int, end: int) -> bool:
    return any(
        character
        and (
            unicodedata.category(character).startswith(("M", "Cf"))
            or (
                unicodedata.category(character).startswith("P")
                and character not in _CO_SAFE_BOUNDARY_CHARACTERS
            )
        )
        for character in (
            text[start - 1] if start > 0 else "",
            text[end] if end < len(text) else "",
        )
    )


def _is_co_extended_identifier_context(text: str, start: int, end: int) -> bool:
    left, right = _host_token_span(text, start, end)
    return any(
        character in _CO_EXTENDED_HOST_TOKEN_CHARS
        for character in text[left:start] + text[end:right]
    )


def _is_co_bare_metalinguistic_context(text: str, start: int) -> bool:
    return bool(
        _METALINGUISTIC_QUOTE_CUE_RE.search(
            text[max(0, start - _CO_CUE_LOOKBEHIND) : start]
        )
    )


@lru_cache(maxsize=32)
def _closed_literal_lookup(
    rules: tuple[_CasePatternRule, ...],
) -> dict[str, tuple[_CasePatternRule, str]]:
    """Build the immutable-per-registry surface lookup once."""

    lookup: dict[str, tuple[_CasePatternRule, str]] = {}
    for rule in rules:
        for typed, corrected in rule._surface_map().items():
            key = typed.lower()
            if key in lookup:
                raise ValueError(f"duplicate closed literal typed form: {typed}")
            lookup[key] = (rule, corrected)
    return lookup


@lru_cache(maxsize=32)
def _closed_literal_pattern(rules: tuple[_CasePatternRule, ...]) -> re.Pattern[str]:
    """Compile one exact mixed-case matcher for the registry's closed surfaces."""

    lookup = _closed_literal_lookup(rules)
    alternatives = sorted(
        (_explicit_case_pattern(surface) for surface in lookup),
        key=len,
        reverse=True,
    )
    return re.compile(rf"(?<!\w)(?:{'|'.join(alternatives)})(?!\w)")


@lru_cache(maxsize=32)
def _closed_literal_empty_buckets(
    rules: tuple[_CasePatternRule, ...],
) -> MappingProxyType[Source, tuple[Finding, ...]]:
    """Cache an immutable ordered empty-source mapping."""

    return MappingProxyType({rule.source: () for rule in rules})


def _explicit_case_pattern(surface: str) -> str:
    parts: list[str] = []
    for char in surface:
        lower = char.lower()
        upper = char.upper()
        if len(lower) == len(upper) == 1 and lower != upper:
            variants = lower + upper + _LOWER_COMPATIBILITY_VARIANTS.get(lower, "")
            parts.append(f"[{re.escape(variants)}]")
        else:
            parts.append(re.escape(char))
    return "".join(parts)


def collect_closed_literal_findings(
    text: str, rules: tuple[_CasePatternRule, ...]
) -> Mapping[Source, tuple[Finding, ...]]:
    """Scan ``text`` once and bucket findings by closed-literal rule source.

    Behavior is identical to invoking each rule's historical per-pattern
    ``find`` independently: context abstention, case mapping, confidence,
    source identity, and per-source left-to-right order are preserved.

    A rule may own one typed form (``_typed``/``_corrected``) or a closed
    multi-surface map (``_surfaces``: typed → corrected).
    """
    if not rules:
        return {}
    lookup = _closed_literal_lookup(rules)
    pattern = _closed_literal_pattern(rules)
    empty_buckets = _closed_literal_empty_buckets(rules)
    matches = tuple(pattern.finditer(text))
    prepared_contexts = {
        id(rule): rule._prepare_context(
            text,
            tuple(
                match.start()
                for match in matches
                if lookup.get(match.group().lower(), (None, ""))[0] is rule
            ),
        )
        for rule in rules
    }
    buckets: dict[Source, tuple[Finding, ...] | list[Finding]] | None = None
    for match in matches:
        observed = match.group()
        entry = lookup.get(observed.lower())
        if entry is None:
            continue
        matched_rule, corrected = entry
        start = match.start()
        end = match.end()
        if matched_rule._should_abstain_context(
            text, start, end, prepared_contexts[id(matched_rule)]
        ):
            continue
        candidate = matched_rule._candidate(observed, corrected)
        if candidate is None or candidate == observed:
            continue
        finding = Finding.create(
            category=matched_rule._CATEGORY,
            severity=matched_rule._severity(),
            message=matched_rule._message(observed),
            explanation=matched_rule._explanation(observed, candidate),
            original=observed,
            suggestion=candidate,
            start=start,
            end=end,
            confidence=matched_rule._confidence,
            source=matched_rule.source,
        )
        if buckets is None:
            buckets = cast(
                dict[Source, tuple[Finding, ...] | list[Finding]],
                empty_buckets.copy(),
            )
        current = buckets[matched_rule.source]
        if isinstance(current, tuple):
            buckets[matched_rule.source] = [finding]
        else:
            current.append(finding)
    if buckets is None:
        return empty_buckets
    for source, items in buckets.items():
        if isinstance(items, list):
            buckets[source] = tuple(items)
    return cast(dict[Source, tuple[Finding, ...]], buckets)


class _CasePatternRule:
    """Simple word-level spelling replacement rule."""

    _CATEGORY = Category.SPELLING
    _IGNORE_WRAPPED_MENTIONS = False

    def __init__(
        self,
        source_name: str,
        typed: str,
        corrected: str,
        confidence: float,
        *,
        surfaces: dict[str, str] | None = None,
    ) -> None:
        self.source = Source(SourceKind.RULE, source_name)
        self._typed = typed
        self._corrected = corrected
        self._confidence = Confidence(confidence)
        self._surfaces = dict(surfaces) if surfaces is not None else None
        self._pattern = re.compile(rf"(?<!\w){re.escape(typed)}(?!\w)", re.IGNORECASE)

    def _surface_map(self) -> dict[str, str]:
        if self._surfaces is not None:
            return self._surfaces
        return {self._typed: self._corrected}

    def _prepare_context(self, text: str, starts: tuple[int, ...]) -> object | None:
        return None

    def _should_abstain_context(
        self, text: str, start: int, end: int, prepared_context: object | None = None
    ) -> bool:
        return should_abstain_literal_context(text, start, end)

    def _candidate(self, observed: str, replacement: str) -> str | None:
        return self._apply_case(observed, replacement)

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        # Standalone path: same single-pass token stream, filtered to this rule.
        return collect_closed_literal_findings(text, (self,)).get(self.source, ())

    def _severity(self) -> Severity:
        return Severity.SUGGESTION

    @staticmethod
    def _apply_case(observed: str, replacement: str) -> str:
        if observed.isupper():
            return replacement.upper()
        # Mixed "mostly uppercase with a lowercase diacritic" (e.g. WOGóLE /
        # WKOńCU): treat as uppercase. Do not promote ordinary camel/title
        # mixtures such as NaRaZiE.
        letters = [char for char in observed if char.isalpha()]
        if letters:
            upper = sum(1 for char in letters if char.isupper())
            lower_letters = [char for char in letters if char.islower()]
            if (
                upper > len(lower_letters)
                and lower_letters
                and all(ord(char) > 127 for char in lower_letters)
                and not (observed[:1].isupper() and observed[1:].islower())
            ):
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


class SpellingCzybyRule(TypoSpellingRule):
    """Corrects the exact fused ``czyby`` surface to ``czy by``."""

    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.czyby",
            typed="czyby",
            corrected="czy by",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        """Return the qualified action performed by this rule."""

        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        """Return the qualified implementation behavior version."""

        return "spelling-czyby/1.0"


class SpellingCoNiemiaraRule(TypoSpellingRule):
    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.co_niemiara",
            typed="coniemiara",
            corrected="co niemiara",
            confidence=0.98,
        )

    def _prepare_context(
        self, text: str, starts: tuple[int, ...]
    ) -> _CoPreparedContext:
        return _prepare_co_context(text, starts)

    def _should_abstain_context(
        self,
        text: str,
        start: int,
        end: int,
        prepared_context: object | None = None,
    ) -> bool:
        if _is_co_unicode_extension_context(text, start, end):
            return True
        if _is_co_extended_identifier_context(text, start, end):
            return True

        if isinstance(prepared_context, _CoPreparedContext):
            quote_context = prepared_context.for_start(start)
        else:
            quote_context = _prepare_co_context(text, (start,)).for_start(start)
        if quote_context is None or quote_context.uncertain:
            return (
                True
                if quote_context is not None
                else _is_co_wrapped_mention(text, start, end)
                or _is_co_bare_metalinguistic_context(text, start)
            )
        if quote_context.frames:
            if any(
                frame.closing_index is None
                or not frame.valid
                or not _co_quote_is_dialogue(text, frame)
                or _co_quote_is_metalinguistic(text, frame)
                for frame in quote_context.frames
            ):
                return True
        elif _is_co_bare_metalinguistic_context(text, start):
            return True

        observed = text[start:end]
        if (
            not quote_context.frames
            and observed[:1].isupper()
            and observed[1:].islower()
        ):
            return True

        return should_abstain_literal_context(
            text,
            start,
            end,
            quoted_position=False,
            ignore_wrapped_mention=True,
            allow_sentence_question=True,
        )

    def _candidate(self, observed: str, replacement: str) -> str | None:
        if not (observed.islower() or observed.isupper()):
            if not (observed[:1].isupper() and observed[1:].islower()):
                return None
        return self._apply_case(observed, replacement)

    @property
    def operation(self) -> str:
        return "replace.closed_literal_spacing"

    @property
    def behavior_version(self) -> str:
        return "spelling-co-niemiara/1.0"


class SpellingArcyPrefixRule:
    """Hyphenates the bounded ``arcy`` prefix before uppercase targets."""

    _CATEGORY = Category.SPELLING

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "spelling.arcy_prefix")
        self._pattern = re.compile(
            r"(?<!\w)(?P<prefix>arcy) (?P<target>[A-ZĄĆĘŁŃÓŚŹŻ]"
            r"[a-ząćęłńóśźżA-ZĄĆĘŁŃÓŚŹŻ]*)(?![\w-])"
        )
        self._confidence = Confidence(0.95)

    @property
    def operation(self) -> str:
        return "replace.prefix_hyphenation"

    @property
    def behavior_version(self) -> str:
        return "spelling-arcy-prefix/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        findings: list[Finding] = []
        context_stack: list[str] = []
        uncertain_context = False
        scanned = 0
        for match in self._pattern.finditer(text):
            while scanned < match.start("prefix"):
                character = text[scanned]
                for opening, closing in _ARCY_CONTEXT_PAIRS:
                    if character == opening:
                        if opening == closing and context_stack[-1:] == [closing]:
                            context_stack.pop()
                        else:
                            context_stack.append(closing)
                        break
                    if character == closing:
                        if context_stack[-1:] == [closing]:
                            context_stack.pop()
                        else:
                            uncertain_context = True
                        break
                else:
                    if (
                        _is_arcy_boundary_mark(character)
                        and character not in _ARCY_CONTEXT_MARKS
                    ):
                        uncertain_context = True
                scanned += 1
            start = match.start("prefix")
            end = match.end("target")
            boundary = start - 1
            wrapper_sentence_boundary = False
            while boundary >= 0 and text[boundary].isspace():
                boundary -= 1
            while boundary >= 0 and _is_arcy_sentence_closing_mark(text[boundary]):
                closing = text[boundary]
                if _is_arcy_boundary_mark(closing):
                    for opening, expected_closing in _ARCY_CONTEXT_PAIRS:
                        if expected_closing != closing:
                            continue
                        opening_index = _arcy_matching_opening_index(
                            text, boundary, opening, expected_closing
                        )
                        if opening_index is None:
                            continue
                        before_wrapper = opening_index - 1
                        while before_wrapper >= 0 and text[before_wrapper].isspace():
                            before_wrapper -= 1
                        if before_wrapper >= 0 and text[before_wrapper] in ".!?…":
                            wrapper_sentence_boundary = True
                boundary -= 1
                while boundary >= 0 and text[boundary].isspace():
                    boundary -= 1
            if (
                boundary < 0
                or text[boundary] in ".!?…"
                or wrapper_sentence_boundary
                or uncertain_context
                or any(
                    character in _ARCY_LINE_BREAKS
                    for character in text[boundary + 1 : start]
                )
            ):
                continue
            if (start > 0 and _is_arcy_boundary_mark(text[start - 1])) or (
                end < len(text) and _is_arcy_boundary_mark(text[end])
            ):
                continue
            if (boundary >= 0 and text[boundary] in ",;:") or (
                end < len(text) and text[end] in ",;:"
            ):
                continue
            if end < len(text) and unicodedata.combining(text[end]):
                continue
            if end < len(text) and _is_arcy_apostrophe_like(text[end]):
                continue
            if start > 0 and not text[start - 1].isspace():
                continue
            if (
                end + 1 < len(text)
                and text[end] in ",;:"
                and not text[end + 1].isspace()
            ):
                continue
            if should_abstain_literal_context(
                text,
                start,
                end,
                quoted_position=bool(context_stack),
            ):
                continue
            original = text[start:end]
            target = match.group("target")
            suggestion = f"arcy-{target}"
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Prefiks „arcy” przed wielką literą łączy się łącznikiem.",
                    explanation=(
                        f"Zamiast „{original}” zwykle poprawnie pisze się "
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


class SpellingWziascRule(TypoSpellingRule):
    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.wziasc",
            typed="wziasc",
            corrected="wziąć",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-wziasc/1.0"


class SpellingWogoleDiacriticRule(TypoSpellingRule):
    """Corrects the diacritic-bearing joint form ``wogóle`` → ``w ogóle``."""

    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.wogole_diacritic",
            typed="wogóle",
            corrected="w ogóle",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-wogole-diacritic/1.0"


class SpellingWziascDiacriticRule(TypoSpellingRule):
    """Corrects the diacritic-bearing form ``wziąść`` → ``wziąć`` only."""

    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.wziasc_diacritic",
            typed="wziąść",
            corrected="wziąć",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-wziasc-diacritic/1.0"


class SpellingConajmniejRule(TypoSpellingRule):
    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.conajmniej",
            typed="conajmniej",
            corrected="co najmniej",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-conajmniej/1.0"


class SpellingPoprostuRule(TypoSpellingRule):
    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.poprostu",
            typed="poprostu",
            corrected="po prostu",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-poprostu/1.0"


class SpellingPozatymRule(TypoSpellingRule):
    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.pozatym",
            typed="pozatym",
            corrected="poza tym",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-pozatym/1.0"


class SpellingPrzedewszystkimRule(TypoSpellingRule):
    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.przedewszystkim",
            typed="przedewszystkim",
            corrected="przede wszystkim",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-przedewszystkim/1.0"


class SpellingWkoncuRule(TypoSpellingRule):
    """Closed surfaces for ``w końcu`` joint errors (F2.6 identity fix).

    Source id remains ``spelling.wkoncu`` (ADR-0026). Both diacritic-bearing
    and diacritic-free joint surfaces are registered explicitly.
    """

    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.wkoncu",
            typed="wkońcu",
            corrected="w końcu",
            confidence=0.98,
            surfaces={"wkońcu": "w końcu", "wkoncu": "w końcu"},
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-wkoncu/1.0"


class SpellingSpowrotemRule(TypoSpellingRule):
    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.spowrotem",
            typed="spowrotem",
            corrected="z powrotem",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-spowrotem/1.0"


class SpellingTymbardziejRule(TypoSpellingRule):
    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.tymbardziej",
            typed="tymbardziej",
            corrected="tym bardziej",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-tymbardziej/1.0"


class SpellingNaprawdeRule(TypoSpellingRule):
    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.naprawde",
            typed="naprawde",
            corrected="naprawdę",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-naprawde/1.0"


class SpellingNieBycJointRule(TypoSpellingRule):
    """Closed ``być`` joint-spelling surfaces only."""

    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.nie_byc_joint",
            typed="niejestem",
            corrected="nie jestem",
            confidence=0.98,
            surfaces={
                "niejestem": "nie jestem",
                "niejestes": "nie jesteś",
                "niebędzie": "nie będzie",
                "niebedzie": "nie będzie",
                "niebył": "nie był",
                "niebyl": "nie był",
            },
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-nie-byc-joint/1.0"


class SpellingPoszlemRule(TypoSpellingRule):
    """Only ``poszłem`` → ``poszedłem`` (no ``przeszłem`` / ``przyszłem``)."""

    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.poszlem",
            typed="poszłem",
            corrected="poszedłem",
            confidence=0.98,
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-poszlem/1.0"


class SpellingWlanczacRule(TypoSpellingRule):
    """Literal per-surface map only — no productive ``łancz`` rewrite."""

    _IGNORE_WRAPPED_MENTIONS = True

    def __init__(self) -> None:
        super().__init__(
            source_name="spelling.wlanczac",
            typed="włanczać",
            corrected="włączać",
            confidence=0.98,
            surfaces={
                "włanczać": "włączać",
                "wlanczac": "włączać",
                "wyłanczać": "wyłączać",
                "wylanczac": "wyłączać",
            },
        )

    @property
    def operation(self) -> str:
        return "replace.common_typo"

    @property
    def behavior_version(self) -> str:
        return "spelling-wlanczac/1.0"


_WEEKDAYS_MONTHS: Final = frozenset(
    {
        "poniedziałek",
        "wtorek",
        "środa",
        "czwartek",
        "piątek",
        "sobota",
        "niedziela",
        "styczeń",
        "luty",
        "marzec",
        "kwiecień",
        "maj",
        "czerwiec",
        "lipiec",
        "sierpień",
        "wrzesień",
        "październik",
        "listopad",
        "grudzień",
    }
)
_NATIONALITY_HEADS: Final = frozenset(
    {"języka", "język", "literatury", "historii", "kultury", "narodu"}
)
_NATIONALITY_ADJECTIVES: Final = frozenset(
    {
        "polskiego",
        "polska",
        "polski",
        "angielskiego",
        "francuskiego",
        "niemieckiego",
        "rosyjskiego",
    }
)
_SENTENCE_OPENERS: Final = frozenset(
    {
        "potem",
        "później",
        "następnie",
        "jednak",
        "natomiast",
        "dlatego",
        "wtedy",
        "teraz",
        "tutaj",
        "tam",
    }
)
_SENTENCE_INITIAL_ABBREV_EXCLUSIONS: Final = frozenset(
    {
        "oprac",
        "porówn",
        "miejsc",
        "wspomn",
        "przekł",
        "właśc",
        "ewent",
        "rozdz",
        "załącz",
        "itp",
        "itd",
        "tzn",
        "np",
        "tj",
        "tzw",
        "m.in",
        "prof",
        "dr",
        "mgr",
        "ul",
        "al",
        "pl",
        "nr",
        "str",
        "tom",
        "vol",
        "rys",
        "tab",
        "zob",
        "por",
        "ww",
        "ww.",
    }
)


class SpellingMonthWeekdayLowercaseRule:
    """Lowercase calendar forms after lowercase ``w``/``we`` only."""

    _CATEGORY = Category.SPELLING

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "spelling.month_weekday_lowercase")
        self._pattern = re.compile(
            r"(?<!\w)(?P<pre>w|we) (?P<form>[A-ZĄĆĘŁŃÓŚŹŻ]"
            r"[a-ząćęłńóśźż]+)(?!\w)"
        )
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.case"

    @property
    def behavior_version(self) -> str:
        return "spelling-month-weekday-lowercase/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        findings: list[Finding] = []
        for match in self._pattern.finditer(text):
            form = match.group("form")
            if form.casefold() not in _WEEKDAYS_MONTHS:
                continue
            span_start = match.start("pre")
            span_end = match.end("form")
            if should_abstain_literal_context(text, span_start, span_end):
                continue
            # Load-bearing: abstain when the next token is uppercase
            # (holiday / multi-word proper name, e.g. w Poniedziałek Wielkanocny).
            rest = text[match.end("form") :].lstrip()
            if rest and rest[0].isupper():
                continue
            suggestion = form.casefold()
            if suggestion == form:
                continue
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message=(
                        "Nazwa dnia lub miesiąca w tej pozycji pisze się małą literą."
                    ),
                    explanation=(
                        f"Po przyimku „{match.group('pre')}” forma kalendarzowa "
                        f"„{form}” zapisuje się małą literą."
                    ),
                    original=form,
                    suggestion=suggestion,
                    start=match.start("form"),
                    end=match.end("form"),
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


class SpellingProperAdjectiveLowercaseRule:
    """Lowercase closed nationality adjectives after closed common-noun heads."""

    _CATEGORY = Category.SPELLING

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "spelling.proper_adjective_lowercase")
        self._pattern = re.compile(
            r"(?<!\w)(?P<head>[a-ząćęłńóśźż]+) (?P<adj>[A-ZĄĆĘŁŃÓŚŹŻ]"
            r"[a-ząćęłńóśźż]+)(?!\w)"
        )
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.case"

    @property
    def behavior_version(self) -> str:
        return "spelling-proper-adjective-lowercase/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        findings: list[Finding] = []
        for match in self._pattern.finditer(text):
            head = match.group("head")
            adj = match.group("adj")
            if head not in _NATIONALITY_HEADS:
                continue
            if adj.casefold() not in _NATIONALITY_ADJECTIVES:
                continue
            span_start = match.start("head")
            span_end = match.end("adj")
            if should_abstain_literal_context(text, span_start, span_end):
                continue
            suggestion = adj.casefold()
            if suggestion == adj:
                continue
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Przymiotnik narodowościowy po rzeczowniku pospolitym.",
                    explanation=(
                        f"Po rzeczowniku „{head}” forma „{adj}” zapisuje się "
                        "małą literą."
                    ),
                    original=adj,
                    suggestion=suggestion,
                    start=match.start("adj"),
                    end=match.end("adj"),
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


class SpellingSentenceInitialCapitalRule:
    """Capitalize closed sentence openers after a full stop."""

    _CATEGORY = Category.SPELLING

    def __init__(self) -> None:
        self.source = Source(SourceKind.RULE, "spelling.sentence_initial_capital")
        self._pattern = re.compile(
            r"(?P<pre>[A-Za-ząćęłńóśźżĄĆĘŁŃÓŚŹŻ]{6,})\. "
            r"(?P<open>[a-ząćęłńóśźż]+)(?!\w)"
        )
        self._confidence = Confidence(0.9)

    @property
    def operation(self) -> str:
        return "replace.case"

    @property
    def behavior_version(self) -> str:
        return "spelling-sentence-initial-capital/1.0"

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if options.categories is not None and self._CATEGORY not in options.categories:
            return ()
        findings: list[Finding] = []
        for match in self._pattern.finditer(text):
            pre = match.group("pre")
            opener = match.group("open")
            if pre.casefold() in _SENTENCE_INITIAL_ABBREV_EXCLUSIONS:
                continue
            if not pre.isalpha():
                continue
            if opener not in _SENTENCE_OPENERS:
                continue
            suggestion = opener[:1].upper() + opener[1:]
            if suggestion == opener:
                continue
            findings.append(
                Finding.create(
                    category=self._CATEGORY,
                    severity=Severity.SUGGESTION,
                    message="Początek zdania wymaga wielkiej litery.",
                    explanation=(
                        f"Po kropce forma „{opener}” w tej zamkniętej regule "
                        f"zapisuje się jako „{suggestion}”."
                    ),
                    original=opener,
                    suggestion=suggestion,
                    start=match.start("open"),
                    end=match.end("open"),
                    confidence=self._confidence,
                    source=self.source,
                )
            )
        return tuple(findings)


__all__ = [
    "SpellingCoNiemiaraRule",
    "SpellingConajmniejRule",
    "SpellingJestesRule",
    "SpellingMonthWeekdayLowercaseRule",
    "SpellingNapewnoRule",
    "SpellingNaprawdeRule",
    "SpellingNarazieRule",
    "SpellingNieBycJointRule",
    "SpellingPoprostuRule",
    "SpellingPoszlemRule",
    "SpellingPozatymRule",
    "SpellingProperAdjectiveLowercaseRule",
    "SpellingPrzedewszystkimRule",
    "SpellingSentenceInitialCapitalRule",
    "SpellingSpowrotemRule",
    "SpellingTymbardziejRule",
    "SpellingWkoncuRule",
    "SpellingWlanczacRule",
    "SpellingWogoleDiacriticRule",
    "SpellingWogoleRule",
    "SpellingWlasnieRule",
    "SpellingWziascDiacriticRule",
    "SpellingWziascRule",
    "SpellingZebyRule",
    "TypoSpellingRule",
]
