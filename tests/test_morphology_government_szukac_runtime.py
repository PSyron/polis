from __future__ import annotations

import json
import subprocess
import sys

import pytest

import polis
import polis.analyzer as analyzer_module
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
from polis.evaluation.quality_dataset import (
    QualityDatasetVersion,
    load_quality_dataset,
)
from polis.rules import DeterministicRuleRegistry, RuleRegistration
from polis.rules.government import InflectionGovernmentSzukacKluczRule

_TEXT = "Szukam klucz."
_BEHAVIOR = (
    "inflection-government-szukac-klucz/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)


def test_default_analyzer_reports_approved_finding() -> None:
    result = Analyzer(AnalyzerConfig()).analyze(_TEXT)
    assert len(result.issues) == 1
    finding = result.issues[0]
    assert str(finding.source) == "rule:inflection.government_szukac_klucz"
    assert finding.category is Category.INFLECTION
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "klucz"
    assert finding.suggestion == "klucza"
    assert (finding.start, finding.end) == (7, 12)
    assert finding.confidence.value == 0.9


def test_json_explicit_apply_and_review_only_correct() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    finding = analyzer.analyze(_TEXT).issues[0]
    decoded = AnalysisResult.from_json(analyzer.analyze(_TEXT).to_json())
    correction = analyzer.correct(_TEXT)
    assert decoded.issues == (finding,)
    assert correction.corrected_text == _TEXT
    assert correction.applied_findings == ()
    assert correction.skipped_findings == (finding,)
    assert correction.apply_suggestions((finding.id,)) == "Szukam klucza."


def test_conflict_and_missing_provider() -> None:
    finding = Analyzer(AnalyzerConfig()).analyze(_TEXT).issues[0]
    overlapping = Finding.create(
        category=Category.INFLECTION,
        severity=Severity.SUGGESTION,
        message="overlap",
        explanation="overlap",
        original="klucz",
        suggestion="klucza",
        start=7,
        end=12,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test.overlap"),
    )
    with pytest.raises(CorrectionConflictError):
        AnalysisResult(_TEXT, (finding, overlapping)).apply(
            (finding.id, overlapping.id)
        )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(
        analyzer_module, "_load_qualified_morfeusz", lambda: None, raising=False
    )
    try:
        analyzer = Analyzer(AnalyzerConfig())
        existing = analyzer.analyze("Nie widzę samochód.")
        current = analyzer.analyze(_TEXT)
    finally:
        monkeypatch.undo()
    assert str(existing.issues[0].source) == "rule:inflection.negated_widziec"
    assert current.issues == ()


def test_cli_and_behavior_identity() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "polis.cli", "analyze", "--json", _TEXT],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert payload["issues"][0]["source"] == "rule:inflection.government_szukac_klucz"
    assert payload["issues"][0]["original"] == "klucz"
    assert payload["issues"][0]["suggestion"] == "klucza"
    analyzer = Analyzer(AnalyzerConfig())
    correction = analyzer.correct(_TEXT)
    finding = correction.skipped_findings[0]
    behavior = analyzer._registry.source_behavior(finding.source)
    assert correction.applied_findings == ()
    assert behavior is not None
    assert behavior.operation == "replace.governed_form"
    assert behavior.behavior_version == _BEHAVIOR


def test_v2_cases() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V2)
    cases = tuple(
        case for case in dataset.cases if case.id.startswith("v2_szukac_klucz_")
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
            if str(finding.source) == "rule:inflection.government_szukac_klucz"
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
    assert len(cases) == 8
    assert observed == expected


def test_exports_and_registry_compose() -> None:
    assert (
        rules.InflectionGovernmentSzukacKluczRule is InflectionGovernmentSzukacKluczRule
    )
    assert not hasattr(polis, "InflectionGovernmentSzukacKluczRule")
    morphology = analyzer_module._load_qualified_morfeusz()
    rule = InflectionGovernmentSzukacKluczRule(morphology)
    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=rule, categories=frozenset({Category.INFLECTION})),)
    )
    assert registry.find(_TEXT, options=AnalysisOptions()) == rule.find(
        _TEXT, options=AnalysisOptions()
    )
