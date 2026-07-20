"""Tests for the baseline quality gate computation."""

from __future__ import annotations

from collections.abc import Callable
from typing import cast

import pytest

from polis.analysis.pipeline import analyze_text
from polis.core import AnalysisOptions, Category, Finding, SourceKind
from polis.evaluation import (
    BaselineResult,
    QualityCounts,
    evaluate_baseline,
    load_dataset,
)
from polis.llm import MockHeuristicBackend, create_default_local_backend
from polis.rules import (
    DeterministicRuleRegistry,
    RuleRegistration,
    SyntaxCommaSpacingRule,
    SyntaxListSpacingRule,
    SyntaxQuoteSpacingRule,
)
from polis.rules.agreement import AgreementCopulaRule
from polis.rules.spelling import (
    SpellingJestesRule,
    SpellingWlasnieRule,
    SpellingZebyRule,
)


def _analysis_pipeline_config(
    local_backend: bool,
) -> tuple[DeterministicRuleRegistry, MockHeuristicBackend | None]:
    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(rule=SpellingZebyRule(), categories={Category.SPELLING}),
            RuleRegistration(
                rule=SpellingWlasnieRule(), categories={Category.SPELLING}
            ),
            RuleRegistration(rule=SpellingJestesRule(), categories={Category.SPELLING}),
            RuleRegistration(
                rule=AgreementCopulaRule(), categories={Category.AGREEMENT}
            ),
            RuleRegistration(
                rule=SyntaxListSpacingRule(), categories={Category.SYNTAX}
            ),
            RuleRegistration(
                rule=SyntaxCommaSpacingRule(), categories={Category.PUNCTUATION}
            ),
            RuleRegistration(
                rule=SyntaxQuoteSpacingRule(), categories={Category.PUNCTUATION}
            ),
        )
    )
    backend = create_default_local_backend() if local_backend else None
    return registry, backend


def _make_analyzer(local_backend: bool) -> Callable[[str], tuple[Finding, ...]]:
    registry, backend = _analysis_pipeline_config(local_backend)

    def _analyze(text: str) -> tuple[Finding, ...]:
        return cast(
            "tuple[Finding, ...]",
            analyze_text(
                text,
                registry=registry,
                local_backend=backend,
                options=AnalysisOptions(),
            ),
        )

    return _analyze


def _evaluate(local_backend: bool, run_reference: str) -> BaselineResult:
    dataset = load_dataset()
    return evaluate_baseline(
        dataset=dataset,
        analyzer=_make_analyzer(local_backend=local_backend),
        run_label="m3-02-baseline",
        run_reference=run_reference,
        configuration="rule+syntax+agreement+mock-spelling",
    )


def test_quality_baseline_is_deterministic_when_repeated() -> None:
    first = _evaluate(local_backend=False, run_reference="det-1")
    second = _evaluate(local_backend=False, run_reference="det-2")

    assert first.aggregate == second.aggregate
    assert first.by_category == second.by_category
    assert first.by_source == second.by_source


def test_quality_baseline_reports_expected_metrics_and_gate_targets() -> None:
    baseline = _evaluate(local_backend=False, run_reference="rules-only")

    assert baseline.aggregate == QualityCounts(
        expected_findings=9,
        predicted_findings=2,
        true_positives=2,
        false_positives=0,
        false_negatives=7,
        span_matches=2,
        correction_matches=2,
    )
    assert baseline.aggregate.precision == pytest.approx(1.0)
    assert baseline.aggregate.recall == pytest.approx(2 / 9)
    assert baseline.aggregate.f1 == pytest.approx(4 / 11)
    assert baseline.aggregate.span_accuracy == pytest.approx(2 / 9)
    assert baseline.aggregate.correction_accuracy == pytest.approx(1.0)
    assert baseline.aggregate.false_positive_rate == pytest.approx(0.0)

    assert baseline.by_category[Category.AGREEMENT] == QualityCounts(
        expected_findings=2,
        predicted_findings=1,
        true_positives=1,
        false_positives=0,
        false_negatives=1,
        span_matches=1,
        correction_matches=1,
    )
    assert baseline.by_category[Category.SYNTAX] == QualityCounts(
        expected_findings=2,
        predicted_findings=1,
        true_positives=1,
        false_positives=0,
        false_negatives=1,
        span_matches=1,
        correction_matches=1,
    )
    assert baseline.by_category[Category.SPELLING] == QualityCounts(
        expected_findings=1,
        predicted_findings=0,
        true_positives=0,
        false_positives=0,
        false_negatives=1,
        span_matches=0,
        correction_matches=0,
    )
    assert baseline.by_category[Category.INFLECTION] == QualityCounts(
        expected_findings=1,
        predicted_findings=0,
        true_positives=0,
        false_positives=0,
        false_negatives=1,
        span_matches=0,
        correction_matches=0,
    )
    assert baseline.by_category[Category.PUNCTUATION] == QualityCounts(
        expected_findings=2,
        predicted_findings=0,
        true_positives=0,
        false_positives=0,
        false_negatives=2,
        span_matches=0,
        correction_matches=0,
    )
    assert baseline.by_category[Category.STYLE] == QualityCounts(
        expected_findings=1,
        predicted_findings=0,
        true_positives=0,
        false_positives=0,
        false_negatives=1,
        span_matches=0,
        correction_matches=0,
    )

    assert baseline.by_source[SourceKind.RULE] == QualityCounts(
        expected_findings=9,
        predicted_findings=2,
        true_positives=2,
        false_positives=0,
        false_negatives=7,
        span_matches=2,
        correction_matches=2,
    )
    assert baseline.by_source[SourceKind.LLM] == QualityCounts(
        expected_findings=9,
        predicted_findings=0,
        true_positives=0,
        false_positives=0,
        false_negatives=9,
        span_matches=0,
        correction_matches=0,
    )


def test_quality_baseline_documents_llm_variance_for_complete_evaluations() -> None:
    rules_only = _evaluate(local_backend=False, run_reference="rules-only")
    with_llm = _evaluate(local_backend=True, run_reference="rules+llm")

    assert rules_only.aggregate == with_llm.aggregate
    assert rules_only.by_source[SourceKind.LLM] == with_llm.by_source[SourceKind.LLM]
    assert rules_only.by_source[SourceKind.RULE] == with_llm.by_source[SourceKind.RULE]
