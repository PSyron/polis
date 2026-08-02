"""Bounded generated parity checks for the analysis pipeline."""

from __future__ import annotations

import asyncio

import pytest
from tests.generative import (
    MAX_CASES,
    UNICODE_FAMILIES,
    Replay,
    SyntheticTextCase,
    assert_structural_invariant,
    generate_unicode_text_cases,
)

from polis.analysis.pipeline import analyze_text, analyze_text_async
from polis.core import (
    AnalysisOptions,
    AnalysisTimeoutError,
    BackendUnavailableError,
    Category,
    Confidence,
    Finding,
    InvalidBackendResponseError,
    PolisError,
    Severity,
    Source,
)
from polis.segmentation import segment_sentences

_UNSAFE_BACKEND_SENTINEL = "generated-backend-private"
_OPERATION = "generated.analysis"
_BACKEND_NAME = "generated-backend"
_RULE_SOURCE = Source.parse("rule:generated-parity")
_BACKEND_SOURCE = Source.parse("llm:generated-parity")


class GeneratedRegistry:
    """Return one stable generated deterministic finding for each source."""

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        del options
        return (_rule_finding(),)


class GeneratedBackend:
    """Return reverse-ordered local findings or one controlled failure."""

    name = _BACKEND_NAME

    def __init__(self, error_type: type[PolisError] | None = None) -> None:
        self._error_type = error_type

    async def generate_findings(
        self,
        text: str,
        *,
        policy: object | None = None,
        clock: object | None = None,
        sleep: object = asyncio.sleep,
        operation: str = "analysis.llm.generate",
    ) -> tuple[Finding, ...]:
        del policy, clock, sleep, operation
        if self._error_type is not None:
            raise self._error_type(
                f"{_UNSAFE_BACKEND_SENTINEL}: {text}",
                code="unsafe.generated",
                retryable=False,
                context={"unsafe": f"{_UNSAFE_BACKEND_SENTINEL}: {text}"},
            )
        return tuple(reversed(_local_findings(text)))


def test_generated_sync_and_async_success_results_are_equal() -> None:
    """Catch a pipeline entry point diverging from its async authority."""
    for case in generate_unicode_text_cases():
        _assert_generated_success_parity(case)


def test_generated_pipeline_replay_is_deterministic_and_bounded() -> None:
    """Catch parity coverage changing for a fixed #123 generator run."""
    first_run = generate_unicode_text_cases()
    repeated_run = generate_unicode_text_cases()
    replay = repeated_run[-1].replay

    assert_structural_invariant(
        1 <= len(first_run) == len(repeated_run) <= MAX_CASES,
        invariant="pipeline.replay.bounded_budget",
        replay=replay,
    )
    assert_structural_invariant(
        tuple(case.replay for case in first_run)
        == tuple(case.replay for case in repeated_run),
        invariant="pipeline.replay.identical_cases",
        replay=replay,
    )
    assert_structural_invariant(
        frozenset().union(*(case.families for case in first_run)) == UNICODE_FAMILIES,
        invariant="pipeline.replay.family_coverage",
        replay=replay,
    )
    assert_structural_invariant(
        tuple(_success_signature(case) for case in first_run)
        == tuple(_success_signature(case) for case in repeated_run),
        invariant="pipeline.replay.identical_signatures",
        replay=replay,
    )


@pytest.mark.parametrize(
    ("error_type", "code", "retryable"),
    (
        (BackendUnavailableError, "backend.unavailable", True),
        (AnalysisTimeoutError, "analysis.timeout", True),
        (InvalidBackendResponseError, "backend.invalid_response", False),
    ),
)
def test_generated_sync_and_async_controlled_failures_are_equal(
    error_type: type[PolisError], code: str, retryable: bool
) -> None:
    """Catch a controlled backend failure translated differently by one entry point."""
    for case in generate_unicode_text_cases():
        if not case.text:
            continue
        registry = GeneratedRegistry()
        backend = GeneratedBackend(error_type)
        sync_error = _capture_sync_error(
            case.text,
            registry=registry,
            backend=backend,
        )
        async_error = _capture_async_error(
            case.text,
            registry=registry,
            backend=backend,
        )
        _assert_failure_parity(
            case.replay,
            case.text,
            sync_error,
            async_error,
            error_type=error_type,
            code=code,
            retryable=retryable,
        )


def _assert_generated_success_parity(case: SyntheticTextCase) -> None:
    sync_result, async_result = _pipeline_results(case.text)
    expected = _expected_findings(case.text)

    assert_structural_invariant(
        sync_result == async_result,
        invariant="pipeline.sync_async.equal",
        replay=case.replay,
    )
    assert_structural_invariant(
        sync_result == expected,
        invariant="pipeline.canonical_order",
        replay=case.replay,
    )
    for finding in sync_result:
        assert_structural_invariant(
            0 <= finding.start <= finding.end <= len(case.text),
            invariant="pipeline.finding.bounds",
            replay=case.replay,
        )
        assert_structural_invariant(
            finding.original == case.text[finding.start : finding.end],
            invariant="pipeline.finding.original_slice",
            replay=case.replay,
        )

    _assert_fragment_translations(case.replay, case.text, sync_result)


def _pipeline_results(text: str) -> tuple[tuple[Finding, ...], tuple[Finding, ...]]:
    registry = GeneratedRegistry()
    backend = GeneratedBackend()
    sync_result = analyze_text(
        text,
        registry=registry,
        local_backend=backend,
        operation=_OPERATION,
    )
    async_result = asyncio.run(
        analyze_text_async(
            text,
            registry=registry,
            local_backend=backend,
            operation=_OPERATION,
        )
    )
    return sync_result, async_result


def _success_signature(case: SyntheticTextCase) -> tuple[tuple[object, ...], ...]:
    sync_result, async_result = _pipeline_results(case.text)
    assert_structural_invariant(
        sync_result == async_result,
        invariant="pipeline.replay.sync_async_equal",
        replay=case.replay,
    )
    return tuple(
        (
            finding.id,
            finding.start,
            finding.end,
            finding.original,
            finding.suggestion,
            str(finding.source),
        )
        for finding in sync_result
    )


def _assert_fragment_translations(
    replay: Replay, text: str, findings: tuple[Finding, ...]
) -> None:
    actual = tuple(
        (finding.start, finding.end, finding.original, finding.suggestion)
        for finding in findings
        if finding.source == _BACKEND_SOURCE
    )
    expected = tuple(
        (
            fragment.start + finding.start,
            fragment.start + finding.end,
            finding.original,
            finding.suggestion,
        )
        for fragment in segment_sentences(text)
        for finding in _local_findings(fragment.text)
    )
    assert_structural_invariant(
        actual == expected,
        invariant="pipeline.fragment_offsets",
        replay=replay,
    )
    for start, end, original, _ in actual:
        assert_structural_invariant(
            original == text[start:end],
            invariant="pipeline.fragment_original_slice",
            replay=replay,
        )


def _assert_failure_parity(
    replay: Replay,
    text: str,
    sync_error: PolisError | None,
    async_error: PolisError | None,
    *,
    error_type: type[PolisError],
    code: str,
    retryable: bool,
) -> None:
    assert_structural_invariant(
        sync_error is not None and async_error is not None,
        invariant="pipeline.failure.raised",
        replay=replay,
    )
    if sync_error is None or async_error is None:
        return

    context = {"operation": f"{_OPERATION}.llm", "backend": _BACKEND_NAME}
    assert_structural_invariant(
        type(sync_error) is error_type and type(async_error) is error_type,
        invariant="pipeline.failure.type",
        replay=replay,
    )
    assert_structural_invariant(
        sync_error.code == code == async_error.code,
        invariant="pipeline.failure.code",
        replay=replay,
    )
    assert_structural_invariant(
        sync_error.retryable is retryable and async_error.retryable is retryable,
        invariant="pipeline.failure.retryable",
        replay=replay,
    )
    assert_structural_invariant(
        sync_error.context == context == async_error.context,
        invariant="pipeline.failure.context",
        replay=replay,
    )
    assert_structural_invariant(
        _diagnostic_is_private(sync_error, text)
        and _diagnostic_is_private(async_error, text),
        invariant="pipeline.failure.private_diagnostic",
        replay=replay,
    )


def _capture_sync_error(
    text: str, *, registry: GeneratedRegistry, backend: GeneratedBackend
) -> PolisError | None:
    try:
        analyze_text(
            text,
            registry=registry,
            local_backend=backend,
            operation=_OPERATION,
        )
    except PolisError as error:
        return error
    return None


def _capture_async_error(
    text: str, *, registry: GeneratedRegistry, backend: GeneratedBackend
) -> PolisError | None:
    try:
        asyncio.run(
            analyze_text_async(
                text,
                registry=registry,
                local_backend=backend,
                operation=_OPERATION,
            )
        )
    except PolisError as error:
        return error
    return None


def _diagnostic_is_private(error: PolisError, text: str) -> bool:
    diagnostic = f"{error} {error.context!r}"
    return _UNSAFE_BACKEND_SENTINEL not in diagnostic and (
        not text or text not in diagnostic
    )


def _expected_findings(text: str) -> tuple[Finding, ...]:
    expected = [_rule_finding()]
    for fragment in segment_sentences(text):
        for finding in _local_findings(fragment.text):
            expected.append(_translate_locally(finding, fragment.start))
    return tuple(expected)


def _rule_finding() -> Finding:
    return Finding.create(
        category=Category.SPELLING,
        severity=Severity.ERROR,
        message="Generated deterministic finding.",
        explanation="Generated pipeline parity fixture.",
        original="",
        suggestion=".",
        start=0,
        end=0,
        confidence=Confidence(0.97),
        source=_RULE_SOURCE,
    )


def _local_findings(text: str) -> tuple[Finding, ...]:
    if not text:
        return ()
    findings = [
        Finding.create(
            category=Category.PUNCTUATION,
            severity=Severity.ERROR,
            message="Generated backend finding.",
            explanation="Generated fragment-local fixture.",
            original=text[0],
            suggestion=_replacement_for(text[0]),
            start=0,
            end=1,
            confidence=Confidence(0.91),
            source=_BACKEND_SOURCE,
        )
    ]
    if len(text) > 1:
        findings.append(
            Finding.create(
                category=Category.SYNTAX,
                severity=Severity.WARNING,
                message="Generated backend tail finding.",
                explanation="Generated fragment-local tail fixture.",
                original=text[-1],
                suggestion="",
                start=len(text) - 1,
                end=len(text),
                confidence=Confidence(0.89),
                source=_BACKEND_SOURCE,
            )
        )
    return tuple(findings)


def _translate_locally(finding: Finding, offset: int) -> Finding:
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


def _replacement_for(original: str) -> str:
    return "x" if original != "x" else "y"
