"""Suggestion collision detection and safe application."""

from __future__ import annotations

from collections.abc import Iterable

from polis.core import Finding


class _UnorderedInputError(ValueError):
    """Raised by internal helpers for invalid conflict-check input."""


def validate_non_conflicting_corrections(findings: Iterable[Finding]) -> None:
    """Raise ``ValueError`` if selected findings contain any conflict."""

    if not isinstance(findings, Iterable):
        raise TypeError("selected findings must be an iterable of Finding")
    if isinstance(findings, (str, bytes)):
        raise TypeError("selected findings must be an iterable of Finding")

    items = tuple(_as_finding_iterable(findings))
    for index, first in enumerate(items):
        for second in items[index + 1 :]:
            if findings_conflict(first, second):
                first_id = first.id
                second_id = second.id
                raise ValueError(
                    f"conflicting findings selected: {first_id} and {second_id}"
                )


def findings_conflict(first: Finding, second: Finding) -> bool:
    """Return True if two findings cannot be applied together."""

    if not isinstance(first, Finding):
        raise TypeError("first finding must be a Finding")
    if not isinstance(second, Finding):
        raise TypeError("second finding must be a Finding")

    first_is_insertion = first.start == first.end
    second_is_insertion = second.start == second.end

    if not first_is_insertion and not second_is_insertion:
        return _overlapping_ranges(first.start, first.end, second.start, second.end)

    if first_is_insertion and second_is_insertion:
        return bool(first.start == second.start)

    insertion, replacement = (first, second) if first_is_insertion else (second, first)
    return bool(replacement.start <= insertion.start <= replacement.end)


def sort_findings_for_application(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    """Sort findings for right-to-left replacement without index drift."""

    if not isinstance(findings, Iterable):
        raise TypeError("findings must be an iterable of Finding")
    if isinstance(findings, (str, bytes)):
        raise TypeError("findings must be an iterable of Finding")

    normalized = []
    for finding in findings:
        if not isinstance(finding, Finding):
            raise TypeError("every selected finding must be a Finding")
        normalized.append(finding)

    return tuple(sorted(normalized, key=lambda item: item.start, reverse=True))


def _as_finding_iterable(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    return tuple(finding for finding in findings)


def _overlapping_ranges(start1: int, end1: int, start2: int, end2: int) -> bool:
    """Return True when two non-empty intervals overlap."""

    return max(start1, start2) < min(end1, end2)


__all__ = [
    "findings_conflict",
    "sort_findings_for_application",
    "validate_non_conflicting_corrections",
]
