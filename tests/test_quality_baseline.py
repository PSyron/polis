"""Tests for the baseline quality gate computation."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from polis.analysis.pipeline import analyze_text
from polis.core import (
    AnalysisOptions,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)
from polis.evaluation import (
    BaselineResult,
    QualityCounts,
    evaluate_baseline,
    load_dataset,
    validate_dataset,
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


def _finding(
    *,
    original: str,
    suggestion: str,
    start: int = 0,
    category: Category = Category.SPELLING,
    source: Source | None = None,
) -> Finding:
    return Finding.create(
        category=category,
        severity=Severity.ERROR,
        message="Test finding.",
        explanation="Test finding used to verify metric semantics.",
        original=original,
        suggestion=suggestion,
        start=start,
        end=start + len(original),
        confidence=Confidence(1.0),
        source=source or Source(SourceKind.RULE, "test"),
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
        correct_cases=8,
    )
    assert baseline.aggregate.exact_edit_precision == pytest.approx(1.0)
    assert baseline.aggregate.exact_edit_recall == pytest.approx(2 / 9)
    assert baseline.aggregate.exact_edit_f1 == pytest.approx(4 / 11)
    assert baseline.aggregate.span_accuracy == pytest.approx(2 / 9)
    assert baseline.aggregate.correction_accuracy == pytest.approx(1.0)
    assert baseline.aggregate.false_discovery_proportion == pytest.approx(0.0)
    assert baseline.aggregate.correct_sentence_false_alarm_rate == pytest.approx(0.0)

    assert baseline.by_category[Category.AGREEMENT] == QualityCounts(
        expected_findings=2,
        predicted_findings=1,
        true_positives=1,
        false_positives=0,
        false_negatives=1,
        span_matches=1,
        correction_matches=1,
        correct_cases=8,
    )
    assert baseline.by_category[Category.SYNTAX] == QualityCounts(
        expected_findings=2,
        predicted_findings=1,
        true_positives=1,
        false_positives=0,
        false_negatives=1,
        span_matches=1,
        correction_matches=1,
        correct_cases=8,
    )
    assert baseline.by_category[Category.SPELLING] == QualityCounts(
        expected_findings=1,
        predicted_findings=0,
        true_positives=0,
        false_positives=0,
        false_negatives=1,
        span_matches=0,
        correction_matches=0,
        correct_cases=8,
    )
    assert baseline.by_category[Category.INFLECTION] == QualityCounts(
        expected_findings=1,
        predicted_findings=0,
        true_positives=0,
        false_positives=0,
        false_negatives=1,
        span_matches=0,
        correction_matches=0,
        correct_cases=8,
    )
    assert baseline.by_category[Category.PUNCTUATION] == QualityCounts(
        expected_findings=2,
        predicted_findings=0,
        true_positives=0,
        false_positives=0,
        false_negatives=2,
        span_matches=0,
        correction_matches=0,
        correct_cases=8,
    )
    assert baseline.by_category[Category.STYLE] == QualityCounts(
        expected_findings=1,
        predicted_findings=0,
        true_positives=0,
        false_positives=0,
        false_negatives=1,
        span_matches=0,
        correction_matches=0,
        correct_cases=8,
    )

    assert baseline.by_source[SourceKind.RULE] == QualityCounts(
        expected_findings=9,
        predicted_findings=2,
        true_positives=2,
        false_positives=0,
        false_negatives=7,
        span_matches=2,
        correction_matches=2,
        correct_cases=8,
    )
    assert baseline.by_source[SourceKind.LLM] == QualityCounts(
        expected_findings=9,
        predicted_findings=0,
        true_positives=0,
        false_positives=0,
        false_negatives=9,
        span_matches=0,
        correction_matches=0,
        correct_cases=8,
    )


def test_quality_baseline_documents_llm_variance_for_complete_evaluations() -> None:
    rules_only = _evaluate(local_backend=False, run_reference="rules-only")
    with_llm = _evaluate(local_backend=True, run_reference="rules+llm")

    assert rules_only.aggregate == with_llm.aggregate
    assert rules_only.by_source[SourceKind.LLM] == with_llm.by_source[SourceKind.LLM]
    assert rules_only.by_source[SourceKind.RULE] == with_llm.by_source[SourceKind.RULE]


def test_wrong_replacement_at_gold_span_is_both_false_positive_and_negative() -> None:
    raw = json.loads(
        Path("src/polis/evaluation/datasets/v1/cases.json").read_text(encoding="utf-8")
    )
    raw["cases"] = [case for case in raw["cases"] if case["id"] == "spelling_na_pewno"]
    dataset = validate_dataset(raw)
    wrong = _finding(original="napewno", suggestion="na-pewno", start=8)

    result = evaluate_baseline(
        dataset=dataset,
        analyzer=lambda _text: (wrong,),
        run_label="wrong-replacement",
        run_reference="test",
        configuration="fake",
    )

    assert result.aggregate == QualityCounts(
        expected_findings=1,
        predicted_findings=1,
        false_positives=1,
        false_negatives=1,
        span_matches=1,
    )
    assert result.aggregate.exact_edit_precision == pytest.approx(0.0)
    assert result.aggregate.exact_edit_recall == pytest.approx(0.0)


def test_multiple_findings_on_correct_sentence_count_as_one_false_alarm() -> None:
    raw = json.loads(
        Path("src/polis/evaluation/datasets/v1/cases.json").read_text(encoding="utf-8")
    )
    raw["cases"] = [case for case in raw["cases"] if case["outcome"] == "correct"][:1]
    dataset = validate_dataset(raw)
    first = _finding(original="To", suggestion="Te")
    second = _finding(original="zdanie", suggestion="zdania", start=3)

    result = evaluate_baseline(
        dataset=dataset,
        analyzer=lambda _text: (first, second),
        run_label="correct-alarm",
        run_reference="test",
        configuration="fake",
    )

    assert result.aggregate.correct_cases == 1
    assert result.aggregate.alarmed_correct_cases == 1
    assert result.aggregate.false_positives == 2
    assert result.aggregate.false_discovery_proportion == pytest.approx(1.0)
    assert result.aggregate.correct_sentence_false_alarm_rate == pytest.approx(1.0)


def test_zero_denominators_are_explicitly_undefined() -> None:
    counts = QualityCounts()

    assert counts.exact_edit_precision is None
    assert counts.exact_edit_recall is None
    assert counts.exact_edit_f1 is None
    assert counts.span_accuracy is None
    assert counts.correction_accuracy is None
    assert counts.false_discovery_proportion is None
    assert counts.correct_sentence_false_alarm_rate is None


def test_custom_dataset_reports_actual_source_and_canonical_content_hash(
    tmp_path: Path,
) -> None:
    raw = json.loads(
        Path("src/polis/evaluation/datasets/v1/cases.json").read_text(encoding="utf-8")
    )
    raw["id"] = "custom_quality_dataset"
    custom_path = tmp_path / "custom.json"
    custom_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    first_dataset = load_dataset(custom_path)
    first = evaluate_baseline(
        dataset=first_dataset,
        analyzer=lambda _text: (),
        run_label="custom",
        run_reference="test",
        configuration="fake",
    )

    custom_path.write_text(
        json.dumps(raw, ensure_ascii=False, indent=4, sort_keys=True), encoding="utf-8"
    )
    reformatted = evaluate_baseline(
        dataset=load_dataset(custom_path),
        analyzer=lambda _text: (),
        run_label="custom",
        run_reference="test",
        configuration="fake",
    )
    raw["cases"][0]["provenance"]["notes"] += " Canonical content changed."
    custom_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    changed_dataset = load_dataset(custom_path)

    assert first.dataset_id == "custom_quality_dataset"
    assert first.dataset_source == str(custom_path)
    assert first.dataset_hash == first_dataset.canonical_hash
    assert reformatted.dataset_hash == first.dataset_hash
    assert changed_dataset.canonical_hash != first.dataset_hash
