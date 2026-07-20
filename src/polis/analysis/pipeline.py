"""Hybrid analysis pipeline for deterministic analyzers and optional LLM findings."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Protocol, cast

from polis.analysis import normalize_findings
from polis.core import AnalysisOptions, Finding, PolisError
from polis.core.protocols import RuleRegistry
from polis.segmentation import Sentence, segment_sentences

OperationSleep = Callable[[float], Awaitable[None]]


class _LLMBackend(Protocol):
    """Minimal LLM backend interface used by the analysis pipeline."""

    name: str

    async def generate_findings(
        self,
        text: str,
        *,
        policy: object | None = None,
        clock: object | None = None,
        sleep: OperationSleep | None = None,
        operation: str = "analysis.llm.generate",
    ) -> tuple[Finding, ...]: ...


async def analyze_text_async(
    text: str,
    *,
    registry: RuleRegistry,
    local_backend: _LLMBackend | None,
    options: AnalysisOptions | None = None,
    backend_policy: object | None = None,
    backend_clock: object | None = None,
    backend_sleep: OperationSleep = asyncio.sleep,
    segmenter: Callable[[str], tuple[Sentence, ...]] = segment_sentences,
    ignore_backend_failures: bool = True,
    operation: str = "analysis.run",
) -> tuple[Finding, ...]:
    """Run deterministic analyzers and optional backend findings on ``text``."""

    if options is None:
        options = AnalysisOptions()

    deterministic_findings = registry.find(text, options=options)
    llm_findings: list[Finding] = []

    if local_backend is not None:
        for fragment in segmenter(text):
            if not fragment.text:
                continue
            try:
                generated = await local_backend.generate_findings(
                    fragment.text,
                    policy=backend_policy,
                    clock=backend_clock,
                    sleep=backend_sleep,
                    operation=f"{operation}.llm",
                )
            except PolisError:
                if ignore_backend_failures:
                    continue
                raise

            for finding in generated:
                llm_findings.append(
                    _translate_fragment_offset(
                        finding,
                        offset=fragment.start,
                    )
                )

    return cast(
        "tuple[Finding, ...]",
        normalize_findings(
            (*deterministic_findings, *tuple(llm_findings)),
            options=options,
        ),
    )


def analyze_text(
    text: str,
    *,
    registry: RuleRegistry,
    local_backend: _LLMBackend | None,
    options: AnalysisOptions | None = None,
    backend_policy: object | None = None,
    backend_clock: object | None = None,
    backend_sleep: OperationSleep = asyncio.sleep,
    segmenter: Callable[[str], tuple[Sentence, ...]] = segment_sentences,
    ignore_backend_failures: bool = True,
    operation: str = "analysis.run",
) -> tuple[Finding, ...]:
    """Synchronous wrapper over :func:`analyze_text_async`."""

    return asyncio.run(
        analyze_text_async(
            text,
            registry=registry,
            local_backend=local_backend,
            options=options,
            backend_policy=backend_policy,
            backend_clock=backend_clock,
            backend_sleep=backend_sleep,
            segmenter=segmenter,
            ignore_backend_failures=ignore_backend_failures,
            operation=operation,
        )
    )


def _translate_fragment_offset(finding: Finding, *, offset: int) -> Finding:
    """Translate one finding from a fragment space into original text offsets."""

    if offset == 0:
        return finding

    return Finding.create(
        category=finding.category,
        severity=finding.severity,
        message=finding.message,
        explanation=finding.explanation,
        original=finding.original,
        suggestion=finding.suggestion,
        start=finding.start + offset,
        end=finding.end + offset,
        confidence=finding.confidence,
        source=finding.source,
    )


__all__ = [
    "_LLMBackend",
    "analyze_text",
    "analyze_text_async",
    "_translate_fragment_offset",
]
