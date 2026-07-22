"""Gold-independent deterministic routing for one Polish sentence."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from polis.core import Category, Finding
from polis.segmentation import segment_sentences

from .experiment import RoutingInput

EvidenceKind = Literal[
    "government",
    "missing_reflexive",
    "subject_agreement",
    "missing_correlative",
]

_URL: Final = re.compile(r"https?://[^\s<>„”\"]+?(?=[.,;:!?]?\s|[.,;:!?]?$)", re.I)
_NUMBER: Final = re.compile(r"(?<!\w)[+-]?\d+(?:[.,]\d+)*(?!\w)")
_QUOTED: Final = re.compile(r"(?:\"[^\"]*\"|„[^”]*”|«[^»]*»)")
_CAPITALIZED: Final = re.compile(r"(?<![\w-])[A-ZĄĆĘŁŃÓŚŹŻ][\wĄĆĘŁŃÓŚŹŻąćęłńóśźż-]*")

_GOVERNMENT: Final = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\bPojechałem\s+na\s+[^\s,.!?]+",
        r"\bTęsknię\s+za\s+[^\s,.!?]+(?:\s+[^\s,.!?]+)?",
        r"\bCzekamy\s+za\s+[^\s,.!?]+",
        r"\bPrzyglądamy\s+się\s+[^\s,.!?]+(?:\s+[^\s,.!?]+)?",
        r"\bZależy\s+mi\s+od\s+[^\s,.!?]+(?:\s+[^\s,.!?]+)?",
        r"\bSkupiła\s+się\s+do\s+[^\s,.!?]+(?:\s+[^\s,.!?]+)?",
        r"\bObawiam\s+się\s+przed\s+[^\s,.!?]+",
        r"\bZapomniał\s+założyć\s+o\s+[^\s,.!?]+",
        r"\bPrzysłuchiwała\s+się\s+na\s+[^\s,.!?]+",
        r"\bWspomniał\s+na\s+temat\s+o\s+[^\s,.!?]+",
        r"\bUfam\s+w\s+[^\s,.!?]+",
        r"\bPotrzebuję\s+[^\s,.!?]+",
        r"\bZwróciła\s+uwagę\s+dla\s+[^\s,.!?]+(?:\s+[^\s,.!?]+)?",
    )
)
_MISSING_REFLEXIVE: Final = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\b[A-ZĄĆĘŁŃÓŚŹŻ][\wąćęłńóśźż-]*\s+boi\s+(?!się\b)[^.!?]+",
        r"\bNie\s+spodziewaliśmy\s+(?!się\b)[^.!?]+",
    )
)
_SUBJECT_AGREEMENT: Final = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\bżeby\s+[a-ząćęłńóśźż]+\s+[a-ząćęłńóśźż]+",
        r"\bkto\s+[a-ząćęłńóśźż]+",
    )
)
_MISSING_CORRELATIVE: Final = (
    re.compile(r"\bIm\b[^.!?]*?,\s*(?!tym\b)bardziej\b", re.I),
)


@dataclass(frozen=True, slots=True)
class SyntaxEvidenceWindow:
    kind: EvidenceKind
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    eligible: bool
    reason: str
    deterministic_punctuation: tuple[Finding, ...]
    deterministic_inflection: tuple[Finding, ...]
    protected_spans: tuple[tuple[int, int], ...]
    syntax_window: SyntaxEvidenceWindow | None


def route_sentence(routing_input: RoutingInput) -> RoutingDecision:
    """Route one sentence without access to labels, expected text, or gold edits."""

    if not isinstance(routing_input, RoutingInput):
        raise TypeError("routing_input must be a RoutingInput")
    source = routing_input.source
    punctuation = tuple(
        finding
        for finding in routing_input.deterministic_findings
        if finding.category is Category.PUNCTUATION
    )
    inflection = tuple(
        finding
        for finding in routing_input.deterministic_findings
        if finding.category is Category.INFLECTION
    )
    protected = _protected_spans(source, routing_input.entity_spans)
    sentences = segment_sentences(source)
    if len(sentences) != 1 or not source.strip():
        return RoutingDecision(
            False,
            "not_one_sentence",
            punctuation,
            inflection,
            protected,
            None,
        )

    syntax_window = _syntax_window(source)
    reason = (
        "residual_syntax_evidence"
        if syntax_window is not None
        else "no_residual_syntax_evidence"
    )
    return RoutingDecision(
        True,
        reason,
        punctuation,
        inflection,
        protected,
        syntax_window,
    )


def _syntax_window(source: str) -> SyntaxEvidenceWindow | None:
    groups: tuple[tuple[EvidenceKind, tuple[re.Pattern[str], ...]], ...] = (
        ("government", _GOVERNMENT),
        ("missing_reflexive", _MISSING_REFLEXIVE),
        ("subject_agreement", _SUBJECT_AGREEMENT),
        ("missing_correlative", _MISSING_CORRELATIVE),
    )
    matches: list[tuple[int, int, EvidenceKind]] = []
    for kind, patterns in groups:
        for pattern in patterns:
            if match := pattern.search(source):
                matches.append((match.start(), match.end(), kind))
    if not matches:
        return None
    start, end, kind = min(matches, key=lambda item: (item[0], item[1], item[2]))
    return SyntaxEvidenceWindow(kind, start, end)


def _protected_spans(
    source: str, explicit: tuple[tuple[int, int], ...]
) -> tuple[tuple[int, int], ...]:
    spans = list(explicit)
    for pattern in (_URL, _NUMBER, _QUOTED, _CAPITALIZED):
        spans.extend((match.start(), match.end()) for match in pattern.finditer(source))
    for start, end in spans:
        if start < 0 or end <= start or end > len(source):
            raise ValueError("protected span is outside the sentence")
    return _merge_spans(spans)


def _merge_spans(spans: list[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(set(spans)):
        if merged and start <= merged[-1][1]:
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return tuple(merged)


__all__ = [
    "RoutingDecision",
    "SyntaxEvidenceWindow",
    "route_sentence",
]
