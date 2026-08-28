"""Fail-closed morphology boundary for initial subordinate clauses."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from polis.rules._morfeusz import (
    _KNOWN_TAG_PREFIXES,
    _AnalysisRow,
    _qualified_identity,
    _QualifiedMorfeusz,
)

_FINITE_PREDICATE_TAGS: Final = frozenset({"fin", "imps", "impt", "praet", "winien"})
_PROVIDER_TAG_PREFIXES: Final = _KNOWN_TAG_PREFIXES | {"aglt", "interp"}
_UNSAFE_BOUNDARY_TOKENS: Final = frozenset(
    {"i", "oraz", "albo", "ani", "czy", "lub", "to"}
)
_QUOTE_MARKERS: Final = frozenset({'"', "`", "«", "»", "„", "“", "”"})


@dataclass(frozen=True, slots=True)
class _TokenAnalysis:
    lemma: str
    tag: str
    labels: tuple[str, ...]
    qualifiers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ProviderToken:
    surface: str
    char_start: int
    char_end: int
    analyses: tuple[_TokenAnalysis, ...]


def initial_subordinate_comma_position(
    text: str,
    provider: _QualifiedMorfeusz | None,
    conjunctions: frozenset[str],
) -> int | None:
    """Return the minimal insertion offset for one qualified clause boundary."""

    if (
        provider is None
        or provider.identity != _qualified_identity()
        or any(marker in text for marker in _QUOTE_MARKERS)
    ):
        return None
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return None
    surfaces = text.split(maxsplit=1)
    if not surfaces or surfaces[0].casefold() not in conjunctions:
        return None
    try:
        tokens = _parse_provider_tokens(text, provider.backend.analyse(text))
    except (KeyError, OSError, RuntimeError, TypeError, ValueError):
        return None
    if not tokens or tokens[0].surface.casefold() not in conjunctions:
        return None
    if not any(
        analysis.tag.partition(":")[0] == "comp" for analysis in tokens[0].analyses
    ):
        return None

    finite_indexes = _finite_predicate_indexes(tokens)
    if finite_indexes is None or len(finite_indexes) < 2:
        return None
    first_finite, second_finite = finite_indexes[:2]
    boundary_tokens = tokens[first_finite + 1 : second_finite]
    if any(
        token.surface.casefold() in _UNSAFE_BOUNDARY_TOKENS
        or any(
            analysis.tag.partition(":")[0] == "interp" for analysis in token.analyses
        )
        for token in boundary_tokens
    ):
        return None

    boundary = tokens[second_finite].char_start
    while boundary > 0 and text[boundary - 1].isspace():
        boundary -= 1
    if boundary < tokens[first_finite].char_end:
        return None
    return boundary


def _finite_predicate_indexes(
    tokens: tuple[_ProviderToken, ...],
) -> tuple[int, ...] | None:
    indexes: list[int] = []
    for index, token in enumerate(tokens[1:], start=1):
        finite = tuple(
            analysis
            for analysis in token.analyses
            if analysis.tag.partition(":")[0] in _FINITE_PREDICATE_TAGS
        )
        nonfinite = tuple(
            analysis for analysis in token.analyses if analysis not in finite
        )
        if len({analysis.lemma for analysis in finite}) > 1 or (
            finite and any(analysis.labels != ("nazwisko",) for analysis in nonfinite)
        ):
            return None
        if finite:
            indexes.append(index)
            if len(indexes) == 2:
                return tuple(indexes)
    return tuple(indexes)


def _parse_provider_tokens(
    text: str, rows: Sequence[_AnalysisRow]
) -> tuple[_ProviderToken, ...] | None:
    if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
        return None
    grouped: dict[tuple[int, int], tuple[str, list[_TokenAnalysis]]] = {}
    for row in rows:
        parsed = _parse_provider_row(row)
        if parsed is None:
            return None
        edge, surface, analysis = parsed
        current = grouped.get(edge)
        if current is None:
            grouped[edge] = (surface, [analysis])
            continue
        if current[0] != surface or analysis in current[1]:
            return None
        current[1].append(analysis)

    edges = tuple(sorted(grouped))
    if edges != tuple((index, index + 1) for index in range(len(edges))):
        return None

    cursor = 0
    tokens: list[_ProviderToken] = []
    for edge in edges:
        surface, analyses = grouped[edge]
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        char_start = cursor
        if not text.startswith(surface, char_start):
            return None
        cursor += len(surface)
        tokens.append(
            _ProviderToken(
                surface=surface,
                char_start=char_start,
                char_end=cursor,
                analyses=tuple(
                    sorted(analyses, key=lambda item: (item.lemma, item.tag))
                ),
            )
        )
    if text[cursor:].strip():
        return None
    return tuple(tokens)


def _parse_provider_row(
    row: _AnalysisRow,
) -> tuple[tuple[int, int], str, _TokenAnalysis] | None:
    if not isinstance(row, tuple) or len(row) != 3:
        return None
    start, end, interpretation = row
    if (
        type(start) is not int
        or type(end) is not int
        or not isinstance(interpretation, tuple)
        or len(interpretation) != 5
    ):
        return None
    surface, lemma, tag, labels, qualifiers = interpretation
    if (
        end != start + 1
        or not isinstance(surface, str)
        or not surface
        or not isinstance(lemma, str)
        or not lemma
        or not isinstance(tag, str)
        or tag.partition(":")[0] not in _PROVIDER_TAG_PREFIXES
        or not isinstance(labels, list)
        or not all(isinstance(label, str) for label in labels)
        or not isinstance(qualifiers, list)
        or not all(isinstance(qualifier, str) for qualifier in qualifiers)
    ):
        return None
    return (
        (start, end),
        surface,
        _TokenAnalysis(lemma, tag, tuple(labels), tuple(qualifiers)),
    )
