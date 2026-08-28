from __future__ import annotations

import json
import subprocess
import sys

import pytest

import polis
import polis.rules as rules
from polis import (
    AnalysisOptions,
    AnalysisResult,
    Analyzer,
    AnalyzerConfig,
    CorrectionConflictError,
    Finding,
)
from polis.core import Category, Confidence, Source
from polis.core.models import Severity
from polis.correction.policy import SourceBehavior
from polis.evaluation.quality_dataset import (
    QualityDatasetVersion,
    load_quality_dataset,
)
from polis.rules import DeterministicRuleRegistry, RuleRegistration
from polis.rules._morfeusz import _load_qualified_morfeusz
from polis.rules.syntax import SyntaxInitialTemporalCommaRule


@pytest.mark.parametrize(
    ("text", "offset", "applied"),
    (
        ("Gdy pada zostaję w domu.", 8, "Gdy pada, zostaję w domu."),
        ("Kiedy wrócisz zadzwoń do mnie.", 13, "Kiedy wrócisz, zadzwoń do mnie."),
        ("Kiedy pada zostaję w domu.", 10, "Kiedy pada, zostaję w domu."),
    ),
)
def test_exact_templates_emit_zero_width_review_only_insertions(
    text: str, offset: int, applied: str
) -> None:
    analyzer = Analyzer(AnalyzerConfig())
    result = analyzer.analyze(text)
    assert len(result.issues) == 1
    finding = result.issues[0]
    assert str(finding.source) == "rule:syntax.initial_temporal_comma"
    assert finding.category is Category.SYNTAX
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == ""
    assert finding.suggestion == ","
    assert (finding.start, finding.end) == (offset, offset)
    assert finding.confidence.value == 0.9
    correction = analyzer.correct(text)
    assert correction.corrected_text == text
    assert correction.applied_findings == ()
    assert correction.skipped_findings == (finding,)
    assert result.apply((finding.id,)) == applied


@pytest.mark.parametrize(
    "text",
    (
        "Kiedy pada, zostaję w domu.",
        "Kiedykolwiek pada, zostaję w domu.",
        "Cytat „Kiedy pada zostaję” omawiamy bez zmiany.",
        "Reguła `initial_temporal_comma` ma osobny identyfikator.",
        "Kiedy pada, zostaję w domu. Później czytam.",
        "Jeśli pada zostaję w domu.",
    ),
)
def test_close_negatives_and_mentions_abstain(text: str) -> None:
    result = Analyzer(AnalyzerConfig()).analyze(
        text,
        options=AnalysisOptions(categories={Category.SYNTAX}),
    )
    assert all(
        str(item.source) != "rule:syntax.initial_temporal_comma"
        for item in result.issues
    )


def test_repeated_and_unicode_prefix_offsets() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    repeated = analyzer.analyze("Kiedy pada zostaję, a kiedy wieje wracam.")
    unicode_case = analyzer.analyze("ŻÓŁĆ: KIEDY PADA ZOSTAJĘ.")
    assert [(item.start, item.end, item.suggestion) for item in repeated.issues] == [
        (10, 10, ",")
    ]
    assert unicode_case.issues == ()


def test_category_json_conflict_and_policy() -> None:
    text = "Kiedy pada zostaję w domu."
    analyzer = Analyzer(AnalyzerConfig())
    finding = analyzer.analyze(text).issues[0]
    filtered = analyzer.analyze(
        text, options=AnalysisOptions(categories={Category.SPELLING})
    )
    assert filtered.issues == ()
    decoded = AnalysisResult.from_json(analyzer.analyze(text).to_json())
    assert decoded.issues == (finding,)
    overlapping = Finding.create(
        category=Category.SYNTAX,
        severity=Severity.SUGGESTION,
        message="overlap",
        explanation="overlap",
        original="",
        suggestion=",",
        start=10,
        end=10,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test.overlap"),
    )
    with pytest.raises(CorrectionConflictError):
        AnalysisResult(text, (finding, overlapping)).apply((finding.id, overlapping.id))
    behavior = SourceBehavior(
        finding.source,
        "insert.temporal_clause_comma",
        "syntax-initial-temporal-comma/2.0",
    )
    assert analyzer._registry.source_behavior(finding.source) == behavior


def test_cli_json_and_v2_cases() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "polis.cli",
            "analyze",
            "--json",
            "Kiedy pada zostaję w domu.",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert payload["issues"][0]["source"] == "rule:syntax.initial_temporal_comma"
    assert payload["issues"][0]["start"] == 10
    assert payload["issues"][0]["end"] == 10
    assert payload["issues"][0]["suggestion"] == ","
    dataset = load_quality_dataset(version=QualityDatasetVersion.V2)
    cases = tuple(
        case
        for case in dataset.cases
        if case.id.startswith("v2_initial_temporal_comma_")
    )
    analyzer = Analyzer(AnalyzerConfig())
    observed = {
        case.id: tuple(
            (
                finding.category.value,
                finding.start,
                finding.end,
                finding.original,
                finding.suggestion,
            )
            for finding in analyzer.analyze(case.text).issues
            if str(finding.source) == "rule:syntax.initial_temporal_comma"
        )
        for case in cases
    }
    expected = {
        case.id: tuple(
            (
                finding.category,
                finding.start,
                finding.end,
                finding.original,
                finding.suggestion,
            )
            for finding in case.findings
        )
        for case in cases
    }
    expected["v2_initial_temporal_comma_repeated_occurrence"] = (
        ("syntax", 10, 10, "", ","),
    )
    expected["v2_initial_temporal_comma_unicode_casing_offset"] = ()
    assert len(cases) == 8
    assert observed == expected


def test_exports_and_registry_compose() -> None:
    assert rules.SyntaxInitialTemporalCommaRule is SyntaxInitialTemporalCommaRule
    assert not hasattr(polis, "SyntaxInitialTemporalCommaRule")
    provider = _load_qualified_morfeusz()
    assert provider is not None
    rule = SyntaxInitialTemporalCommaRule(provider)
    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=rule, categories=frozenset({Category.SYNTAX})),)
    )
    assert registry.find(
        "Kiedy pada zostaję w domu.", options=AnalysisOptions()
    ) == rule.find("Kiedy pada zostaję w domu.", options=AnalysisOptions())
