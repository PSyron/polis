"""Deterministic analysis pipeline for the conservative v1 runtime."""

from __future__ import annotations

from typing import cast

from polis.analysis import normalize_findings
from polis.core import AnalysisOptions, Finding
from polis.core.protocols import RuleRegistry


async def analyze_text_async(
    text: str,
    *,
    registry: RuleRegistry,
    options: AnalysisOptions | None = None,
) -> tuple[Finding, ...]:
    """Run deterministic analyzers on ``text`` and normalize their findings."""

    resolved_options = options or AnalysisOptions()
    return cast(
        "tuple[Finding, ...]",
        normalize_findings(
            registry.find(text, options=resolved_options),
            options=resolved_options,
        ),
    )


def analyze_text(
    text: str,
    *,
    registry: RuleRegistry,
    options: AnalysisOptions | None = None,
) -> tuple[Finding, ...]:
    """Run the deterministic pipeline synchronously."""

    resolved_options = options or AnalysisOptions()
    return cast(
        "tuple[Finding, ...]",
        normalize_findings(
            registry.find(text, options=resolved_options),
            options=resolved_options,
        ),
    )


__all__ = ["analyze_text", "analyze_text_async"]
