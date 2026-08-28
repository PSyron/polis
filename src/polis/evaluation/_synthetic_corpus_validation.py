from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from random import Random
from typing import Protocol


class _SplitItem(Protocol):
    source_case_id: str
    correct_text: str


@dataclass(frozen=True, slots=True)
class SourceDisjointSplit[ItemT: _SplitItem]:
    development: tuple[ItemT, ...]
    test: tuple[ItemT, ...]


def validate_single_edit(
    incorrect_text: str,
    correct_text: str,
    *,
    start: int,
    end: int,
    original: str,
    suggestion: str,
) -> bool:
    if start < 0 or end < start or end > len(incorrect_text):
        return False
    if incorrect_text[start:end] != original or original == suggestion:
        return False
    repaired = incorrect_text[:start] + suggestion + incorrect_text[end:]
    return repaired == correct_text


def assert_source_disjoint(
    development: Sequence[_SplitItem], test: Sequence[_SplitItem]
) -> None:
    development_sources = {item.source_case_id for item in development}
    test_sources = {item.source_case_id for item in test}
    if development_sources & test_sources:
        raise ValueError("source-disjoint split leakage by source_case_id")
    development_texts = {item.correct_text for item in development}
    test_texts = {item.correct_text for item in test}
    if development_texts & test_texts:
        raise ValueError("source-disjoint split leakage by correct_text")


def split_source_disjoint[ItemT: _SplitItem](
    pairs: Sequence[ItemT], *, development_ratio: float, seed: int
) -> SourceDisjointSplit[ItemT]:
    if not 0 < development_ratio < 1:
        raise ValueError("development_ratio must be between zero and one")
    if len(pairs) < 2:
        raise ValueError("at least two pairs are required for a split")

    groups = _connected_groups(pairs)
    if len(groups) < 2:
        raise ValueError("at least two source groups are required for a split")

    target = min(max(1, round(len(pairs) * development_ratio)), len(pairs) - 1)
    order = sorted(
        groups,
        key=lambda group: min(
            (pairs[index].source_case_id, pairs[index].correct_text) for index in group
        ),
    )
    Random(seed).shuffle(order)

    development_indexes: list[int] = []
    for group in order:
        if not development_indexes or (
            len(development_indexes) < target
            and len(development_indexes) + len(group) <= target
        ):
            development_indexes.extend(group)
    if len(development_indexes) == len(pairs):
        development_indexes = development_indexes[: -len(order[-1])]
    development = set(development_indexes)
    result = SourceDisjointSplit(
        development=tuple(
            pairs[index] for index in range(len(pairs)) if index in development
        ),
        test=tuple(
            pairs[index] for index in range(len(pairs)) if index not in development
        ),
    )
    assert_source_disjoint(result.development, result.test)
    return result


def _connected_groups[ItemT: _SplitItem](
    pairs: Sequence[ItemT],
) -> tuple[tuple[int, ...], ...]:
    parents = list(range(len(pairs)))
    by_source: dict[str, int] = {}
    by_text: dict[str, int] = {}
    for index, pair in enumerate(pairs):
        _join_seen(parents, by_source, pair.source_case_id, index)
        _join_seen(parents, by_text, pair.correct_text, index)
    groups: dict[int, list[int]] = {}
    for index in range(len(pairs)):
        groups.setdefault(_root(parents, index), []).append(index)
    return tuple(tuple(indexes) for indexes in groups.values())


def _join_seen(
    parents: list[int], seen: dict[str, int], value: str, index: int
) -> None:
    previous = seen.setdefault(value, index)
    _union(parents, previous, index)


def _union(parents: list[int], left: int, right: int) -> None:
    left_root = _root(parents, left)
    right_root = _root(parents, right)
    if left_root != right_root:
        parents[right_root] = left_root


def _root(parents: list[int], index: int) -> int:
    while parents[index] != index:
        parents[index] = parents[parents[index]]
        index = parents[index]
    return index
