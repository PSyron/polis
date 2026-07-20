"""Deterministic finding normalization, deduplication, and prioritization."""

from __future__ import annotations

from collections.abc import Iterable

from polis.core import AnalysisOptions, Finding


def normalize_findings(
    findings: Iterable[Finding], *, options: AnalysisOptions
) -> tuple[Finding, ...]:
    """Normalize, filter, deduplicate, and order analyzer findings deterministically."""

    return prioritize_findings(
        deduplicate_findings(filter_findings(findings, options=options))
    )


def filter_findings(
    findings: Iterable[Finding], *, options: AnalysisOptions
) -> tuple[Finding, ...]:
    """Filter findings by option categories and confidence threshold."""

    if not isinstance(findings, Iterable):
        raise TypeError("findings must be an iterable of Finding")
    if isinstance(findings, (str, bytes)):
        raise TypeError("findings must be an iterable of Finding")

    minimum_confidence = options.minimum_confidence.value
    filtered: list[Finding] = []

    for finding in findings:
        if not isinstance(finding, Finding):
            raise TypeError("every finding must be a Finding")
        if finding.confidence.value < minimum_confidence:
            continue
        if (
            options.categories is not None
            and finding.category not in options.categories
        ):
            continue
        filtered.append(finding)

    return tuple(filtered)


def deduplicate_findings(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    """Collapse equivalent findings and keep the preferred representative."""

    if not isinstance(findings, Iterable):
        raise TypeError("findings must be an iterable of Finding")
    if isinstance(findings, (str, bytes)):
        raise TypeError("findings must be an iterable of Finding")

    best_by_id: dict[str, Finding] = {}

    for finding in findings:
        if not isinstance(finding, Finding):
            raise TypeError("every finding must be a Finding")
        current = best_by_id.get(finding.id)
        if current is None or _is_preferred_finding(finding, current):
            best_by_id[finding.id] = finding

    return tuple(best_by_id.values())


def prioritize_findings(findings: Iterable[Finding]) -> tuple[Finding, ...]:
    """Sort findings into deterministic canonical order."""

    if not isinstance(findings, Iterable):
        raise TypeError("findings must be an iterable of Finding")
    if isinstance(findings, (str, bytes)):
        raise TypeError("findings must be an iterable of Finding")

    normalized = []
    for finding in findings:
        if not isinstance(finding, Finding):
            raise TypeError("every finding must be a Finding")
        normalized.append(finding)

    return tuple(
        sorted(
            normalized,
            key=lambda finding: (
                finding.start,
                finding.end,
                -finding.confidence.value,
                finding.category.value,
                str(finding.source),
                finding.id,
            ),
        )
    )


def _is_preferred_finding(new: Finding, existing: Finding) -> bool:
    """Return whether ``new`` should replace ``existing`` as representative."""

    if new.confidence.value != existing.confidence.value:
        return bool(new.confidence.value > existing.confidence.value)
    if new.message != existing.message:
        return bool(new.message < existing.message)
    return bool(new.id < existing.id)


__all__ = [
    "deduplicate_findings",
    "filter_findings",
    "normalize_findings",
    "prioritize_findings",
]
