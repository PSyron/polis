"""Bounded generated parity checks for the deterministic analysis pipeline."""

from __future__ import annotations

import asyncio

from tests.generative import (
    MAX_CASES,
    UNICODE_FAMILIES,
    SyntheticTextCase,
    assert_structural_invariant,
    generate_unicode_text_cases,
)

from polis.analysis.pipeline import analyze_text, analyze_text_async
from polis.core import AnalysisOptions, Category, Confidence, Finding, Severity, Source

_RULE_SOURCE = Source.parse("rule:generated-parity")


class GeneratedRegistry:
    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        del options
        if not text:
            return ()
        return (
            Finding.create(
                category=Category.SPELLING,
                severity=Severity.SUGGESTION,
                message="Generated deterministic finding.",
                explanation="Generated parity fixture.",
                original=text[:1],
                suggestion=None,
                start=0,
                end=1,
                confidence=Confidence(0.9),
                source=_RULE_SOURCE,
            ),
        )


def test_generated_sync_and_async_results_are_equal() -> None:
    for case in generate_unicode_text_cases():
        _assert_generated_parity(case)


def test_generated_pipeline_replay_is_deterministic_and_bounded() -> None:
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
        tuple(_signature(case) for case in first_run)
        == tuple(_signature(case) for case in repeated_run),
        invariant="pipeline.replay.identical_signatures",
        replay=replay,
    )


def _assert_generated_parity(case: SyntheticTextCase) -> None:
    sync_result, async_result = _results(case.text)
    assert_structural_invariant(
        sync_result == async_result,
        invariant="pipeline.sync_async.equal",
        replay=case.replay,
    )
    for finding in sync_result:
        assert_structural_invariant(
            finding.original == case.text[finding.start : finding.end],
            invariant="pipeline.finding.original_slice",
            replay=case.replay,
        )


def _results(text: str) -> tuple[tuple[Finding, ...], tuple[Finding, ...]]:
    sync_result = analyze_text(text, registry=GeneratedRegistry())
    async_result = asyncio.run(analyze_text_async(text, registry=GeneratedRegistry()))
    return sync_result, async_result


def _signature(case: SyntheticTextCase) -> tuple[tuple[object, ...], ...]:
    sync_result, async_result = _results(case.text)
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
