"""Hybrid analysis pipeline for deterministic analyzers and optional LLM findings."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import cast

from polis.analysis import normalize_findings
from polis.core import (
    AnalysisOptions,
    AnalysisTimeoutError,
    BackendUnavailableError,
    Finding,
    InvalidBackendResponseError,
    PolisError,
)
from polis.core.protocols import LocalFindingBackend, MonotonicClock, RuleRegistry
from polis.segmentation import Sentence, segment_sentences

OperationSleep = Callable[[float], Awaitable[None]]


async def analyze_text_async(
    text: str,
    *,
    registry: RuleRegistry,
    local_backend: LocalFindingBackend | None,
    options: AnalysisOptions | None = None,
    backend_policy: object | None = None,
    backend_clock: MonotonicClock | None = None,
    backend_sleep: OperationSleep = asyncio.sleep,
    segmenter: Callable[[str], tuple[Sentence, ...]] = segment_sentences,
    ignore_backend_failures: bool = False,
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
            backend_error: PolisError | None = None
            try:
                generated = await local_backend.generate_findings(
                    fragment.text,
                    policy=backend_policy,
                    clock=backend_clock,
                    sleep=backend_sleep,
                    operation=f"{operation}.llm",
                )
            except (
                BackendUnavailableError,
                AnalysisTimeoutError,
                InvalidBackendResponseError,
            ) as exc:
                if ignore_backend_failures:
                    continue
                backend_error = _canonical_backend_error(
                    exc,
                    operation=f"{operation}.llm",
                    backend=local_backend.name,
                )

            if backend_error is not None:
                raise backend_error

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
    local_backend: LocalFindingBackend | None,
    options: AnalysisOptions | None = None,
    backend_policy: object | None = None,
    backend_clock: MonotonicClock | None = None,
    backend_sleep: OperationSleep = asyncio.sleep,
    segmenter: Callable[[str], tuple[Sentence, ...]] = segment_sentences,
    ignore_backend_failures: bool = False,
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


def _canonical_backend_error(
    error: PolisError,
    *,
    operation: str,
    backend: str,
) -> PolisError:
    """Return an ADR-0003-safe public error for one backend failure."""

    context = {"operation": operation, "backend": backend}
    if isinstance(error, BackendUnavailableError):
        return BackendUnavailableError(
            "configured backend is unavailable",
            code="backend.unavailable",
            retryable=True,
            context=context,
        )
    if isinstance(error, AnalysisTimeoutError):
        return AnalysisTimeoutError(
            "configured analysis deadline expired",
            code="analysis.timeout",
            retryable=True,
            context=context,
        )
    return InvalidBackendResponseError(
        "configured backend returned an invalid response",
        code="backend.invalid_response",
        retryable=False,
        context=context,
    )


__all__ = [
    "analyze_text",
    "analyze_text_async",
    "_translate_fragment_offset",
]
