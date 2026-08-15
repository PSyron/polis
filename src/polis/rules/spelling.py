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
from polis.rules.syntax import _is_quoted_position

_MENTION_WRAPPERS: Final = frozenset(
    {('"', '"'), ("`", "`"), ("„", "”"), ("“", "”"), ("«", "»")}
)

# Characters that glue a match into a larger address/identifier host token.
_HOST_TOKEN_CHARS: Final = frozenset("./:@?#%&+~_-=")
# Sentence/clause punctuation stripped from host edges so `wogole.` stays prose.
_HOST_EDGE_TRIM: Final = frozenset('.,;:!?)]}"»”\'„“«"')
_SCHEME_RE: Final = re.compile(r"(?i)\b(?:https?|ftp)://")
_DOMAINISH_RE: Final = re.compile(
    r"(?i)\b(?:www\.)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b"
)


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


def should_abstain_literal_context(text: str, start: int, end: int) -> bool:
    """Return True when a closed literal match must not emit a suggestion.

    Fail-closed: any recognized non-prose context abstains. Unrecognized
    ambiguous host shapes that look like addresses or quotes also abstain.
    """
    if start < 0 or end > len(text) or start >= end:
        return True
    if _is_wrapped_mention(text, start, end):
        return True
    if _is_quoted_position(text, start):
        return True
    if _is_email_context(text, start, end):
        return True
    if _is_url_or_domain_context(text, start, end):
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


# Shared token stream for the closed-literal family: one left-to-right pass
# over word tokens, with O(1) typed-form lookup per token (Wave 0 / #338 F0.3).
_LITERAL_TOKEN_RE: Final = re.compile(r"(?<!\w)\w+(?!\w)", re.UNICODE)


def collect_closed_literal_findings(
    text: str, rules: tuple[_CasePatternRule, ...]
) -> dict[Source, tuple[Finding, ...]]:
    """Scan ``text`` once and bucket findings by closed-literal rule source.

    Behavior is identical to invoking each rule's historical per-pattern
    ``find`` independently: context abstention, case mapping, confidence,
    source identity, and per-source left-to-right order are preserved.
    """
    if not rules:
        return {}
    lookup: dict[str, _CasePatternRule] = {}
    for rule in rules:
        key = rule._typed.lower()
        if key in lookup:
            raise ValueError(f"duplicate closed literal typed form: {rule._typed}")
        lookup[key] = rule
    buckets: dict[Source, list[Finding]] = {rule.source: [] for rule in rules}
    for match in _LITERAL_TOKEN_RE.finditer(text):
        observed = match.group()
        matched_rule = lookup.get(observed.lower())
        if matched_rule is None:
            continue
        start = match.start()
        end = match.end()
        if should_abstain_literal_context(text, start, end):
            continue
        candidate = matched_rule._apply_case(observed, matched_rule._corrected)
        if candidate == observed:
            continue
        buckets[matched_rule.source].append(
            Finding.create(
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
        )
    return {source: tuple(items) for source, items in buckets.items()}


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
        # Standalone path: same single-pass token stream, filtered to this rule.
        return collect_closed_literal_findings(text, (self,)).get(self.source, ())

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


__all__ = [
    "SpellingJestesRule",
    "SpellingNapewnoRule",
    "SpellingNarazieRule",
    "SpellingWogoleRule",
    "SpellingWlasnieRule",
    "SpellingWziascRule",
    "SpellingZebyRule",
    "TypoSpellingRule",
]
