from __future__ import annotations

import json
import socket
import subprocess
import sys
from typing import Never

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
from polis.rules.przygladac import InflectionPrzygladacSieNowyBudynekRule

_TEXT = "Przyglądam się nowy budynek."
_BEHAVIOR = (
    "inflection-przygladac-sie-nowy-budynek/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
type _SocketAddress = str | tuple[str, int] | tuple[str, int, int, int]


def test_default_analyzer_reports_approved_finding() -> None:
    result = Analyzer(AnalyzerConfig()).analyze(_TEXT)
    assert len(result.issues) == 1
    f = result.issues[0]
    assert str(f.source) == "rule:inflection.przygladac_sie_nowy_budynek"
    assert f.category is Category.INFLECTION
    assert f.severity is Severity.SUGGESTION
    assert f.original == "nowy budynek"
    assert f.suggestion == "nowemu budynkowi"
    assert (f.start, f.end) == (15, 27)
    assert f.confidence.value == 0.9


def test_json_explicit_apply_and_review_only_correct() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    finding = analyzer.analyze(_TEXT).issues[0]
    decoded = AnalysisResult.from_json(analyzer.analyze(_TEXT).to_json())
    correction = analyzer.correct(_TEXT)
    assert decoded.issues == (finding,)
    assert correction.corrected_text == _TEXT
    assert correction.applied_findings == ()
    assert correction.skipped_findings == (finding,)
    assert (
        correction.apply_suggestions((finding.id,))
        == "Przyglądam się nowemu budynkowi."
    )


def test_offline_and_category_filter() -> None:
    def reject(
        address: _SocketAddress,
        timeout: float | None = None,
        source_address: _SocketAddress | None = None,
    ) -> Never:
        del address, timeout, source_address
        raise AssertionError("network")

    mp = pytest.MonkeyPatch()
    mp.setattr(socket.socket, "connect", reject)
    mp.setattr(socket.socket, "connect_ex", reject)
    mp.setattr(socket, "create_connection", reject)
    try:
        result = Analyzer(AnalyzerConfig()).analyze(_TEXT)
    finally:
        mp.undo()
    assert str(result.issues[0].source) == "rule:inflection.przygladac_sie_nowy_budynek"
    filtered = Analyzer(AnalyzerConfig()).analyze(
        _TEXT, options=AnalysisOptions(categories={Category.SPELLING})
    )
    assert filtered.issues == ()


def test_conflict_and_missing_provider() -> None:
    finding = Analyzer(AnalyzerConfig()).analyze(_TEXT).issues[0]
    overlapping = Finding.create(
        category=Category.INFLECTION,
        severity=Severity.SUGGESTION,
        message="overlap",
        explanation="overlap",
        original="nowy budynek",
        suggestion="nowemu budynkowi",
        start=15,
        end=27,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test.overlap"),
    )
    with pytest.raises(CorrectionConflictError):
        AnalysisResult(_TEXT, (finding, overlapping)).apply(
            (finding.id, overlapping.id)
        )
    mp = pytest.MonkeyPatch()
    mp.setattr(analyzer_module, "_load_qualified_morfeusz", lambda: None, raising=False)
    try:
        analyzer = Analyzer(AnalyzerConfig())
        existing = analyzer.analyze("Nie widzę samochód.")
        current = analyzer.analyze(_TEXT)
    finally:
        mp.undo()
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
    assert (
        payload["issues"][0]["source"] == "rule:inflection.przygladac_sie_nowy_budynek"
    )
    assert payload["issues"][0]["original"] == "nowy budynek"
    assert payload["issues"][0]["suggestion"] == "nowemu budynkowi"
    analyzer = Analyzer(AnalyzerConfig())
    correction = analyzer.correct(_TEXT)
    finding = correction.skipped_findings[0]
    behavior = analyzer._registry.source_behavior(finding.source)
    assert correction.applied_findings == ()
    assert behavior is not None
    assert behavior.operation == "replace.governed_nominal_group"
    assert behavior.behavior_version == _BEHAVIOR


def test_v2_cases() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V2)
    cases = tuple(
        case for case in dataset.cases if case.id.startswith("v2_przygladac_budynek_")
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
            if str(finding.source) == "rule:inflection.przygladac_sie_nowy_budynek"
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
        rules.InflectionPrzygladacSieNowyBudynekRule
        is InflectionPrzygladacSieNowyBudynekRule
    )
    assert not hasattr(polis, "InflectionPrzygladacSieNowyBudynekRule")
    morphology = analyzer_module._load_qualified_morfeusz()
    rule = InflectionPrzygladacSieNowyBudynekRule(morphology)
    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=rule, categories=frozenset({Category.INFLECTION})),)
    )
    assert registry.find(_TEXT, options=AnalysisOptions()) == rule.find(
        _TEXT, options=AnalysisOptions()
    )
