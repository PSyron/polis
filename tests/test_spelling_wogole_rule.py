from __future__ import annotations

import json
import subprocess
import sys

import pytest

import polis
import polis.rules as rules
from polis import (
    AnalysisResult,
    Analyzer,
    AnalyzerConfig,
    CorrectionConflictError,
    Finding,
)
from polis.core import AnalysisOptions, Category, Confidence, Severity, Source
from polis.correction.policy import SourceBehavior
from polis.evaluation.quality_dataset import (
    QualityDatasetVersion,
    load_quality_dataset,
)
from polis.rules import DeterministicRuleRegistry, RuleRegistration
from polis.rules.spelling import SpellingWogoleRule


def test_wogole_emits_exact_contract_with_case_and_unicode_offsets() -> None:
    text = "ŁÓDŹ: WOGOLE; Wogole, wogole."
    analyzer = Analyzer(AnalyzerConfig())

    result = analyzer.analyze(text)

    assert [
        (
            finding.category,
            finding.severity,
            str(finding.source),
            finding.original,
            finding.suggestion,
            finding.start,
            finding.end,
            finding.confidence.value,
        )
        for finding in result.issues
    ] == [
        (
            Category.SPELLING,
            Severity.SUGGESTION,
            "rule:spelling.wogole",
            "WOGOLE",
            "W OGÓLE",
            6,
            12,
            0.98,
        ),
        (
            Category.SPELLING,
            Severity.SUGGESTION,
            "rule:spelling.wogole",
            "Wogole",
            "W ogóle",
            14,
            20,
            0.98,
        ),
        (
            Category.SPELLING,
            Severity.SUGGESTION,
            "rule:spelling.wogole",
            "wogole",
            "w ogóle",
            22,
            28,
            0.98,
        ),
    ]
    assert all(text[item.start : item.end] == item.original for item in result.issues)
    assert analyzer._registry.source_behavior(
        result.issues[0].source
    ) == SourceBehavior(
        source=result.issues[0].source,
        operation="replace.common_typo",
        behavior_version="spelling-wogole/1.0",
    )


@pytest.mark.parametrize(
    ("typed", "corrected"),
    (
        ("wogole", "w ogóle"),
        ("Wogole", "W ogóle"),
        ("WOGOLE", "W OGÓLE"),
        ("woGoLe", "w ogóle"),
        ("WoGoLe", "W ogóle"),
    ),
)
def test_wogole_uses_existing_case_contract(typed: str, corrected: str) -> None:
    findings = SpellingWogoleRule().find(typed, options=AnalysisOptions())

    assert tuple(item.suggestion for item in findings) == (corrected,)


@pytest.mark.parametrize(
    "text",
    (
        "W ogóle tego nie pamiętam.",
        "wogolex xwogole przedwogolepo",
        "wo-gole wo\ngole wo\r\ngole",
        "Forma „wogole” jest omawiana jako przykład.",
        "Wartość `wogole` występuje w starym formacie danych.",
    ),
)
def test_wogole_abstains_for_close_negatives_and_mentions(text: str) -> None:
    result = Analyzer(AnalyzerConfig()).analyze(
        text,
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    assert result.issues == ()


def test_wogole_respects_category_filtering() -> None:
    result = Analyzer(AnalyzerConfig()).analyze(
        "Wogole tego nie pamiętam.",
        options=AnalysisOptions(categories={Category.SYNTAX}),
    )

    assert result.issues == ()


def test_wogole_json_is_stable_and_explicit_application_is_exact() -> None:
    text = "Wogole nie idę i wogole nie dzwonię."
    analyzer = Analyzer(AnalyzerConfig())
    result = analyzer.analyze(text)

    encoded = result.to_json()
    decoded = AnalysisResult.from_json(encoded)
    correction = analyzer.correct(text)

    assert decoded == result
    assert decoded.to_json() == encoded
    assert correction.corrected_text == text
    assert correction.applied_findings == ()
    assert correction.skipped_findings == result.issues
    assert result.apply(tuple(item.id for item in result.issues)) == (
        "W ogóle nie idę i w ogóle nie dzwonię."
    )


def test_wogole_explicit_application_rejects_overlap() -> None:
    text = "Wogole tego nie pamiętam."
    finding = Analyzer(AnalyzerConfig()).analyze(text).issues[0]
    overlapping = Finding.create(
        category=Category.SPELLING,
        severity=Severity.SUGGESTION,
        message="Testowe znalezisko konfliktowe.",
        explanation="Testuje odrzucenie nakładających się zakresów.",
        original="Wogole",
        suggestion="W ogóle",
        start=0,
        end=6,
        confidence=Confidence(0.98),
        source=Source.parse("rule:test.overlap"),
    )
    result = AnalysisResult(text, (finding, overlapping))

    with pytest.raises(CorrectionConflictError):
        result.apply((finding.id, overlapping.id))


def test_wogole_v2_cases_change_expected_errors_to_matches_without_alarms() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V2)
    cases = tuple(case for case in dataset.cases if case.id.startswith("v2_wogole_"))
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
            if str(finding.source) == "rule:spelling.wogole"
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


def test_cli_json_reports_exact_wogole_finding() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "polis.cli",
            "analyze",
            "--json",
            "Wogole tego nie pamiętam.",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    payload = json.loads(completed.stdout)
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert payload["issues"] == [
        {
            "category": "spelling",
            "confidence": 0.98,
            "end": 6,
            "explanation": "Zamiast 'Wogole' zwykle poprawnie pisze się 'W ogóle'.",
            "id": "finding_a901fabed21023c43c5bc6aba21172c5",
            "message": "Wygląda jak częsty błąd ortograficzny: Wogole.",
            "original": "Wogole",
            "severity": "suggestion",
            "source": "rule:spelling.wogole",
            "start": 0,
            "suggestion": "W ogóle",
        }
    ]


def test_rules_package_exports_wogole_without_root_export() -> None:
    assert rules.SpellingWogoleRule is SpellingWogoleRule
    assert not hasattr(polis, "SpellingWogoleRule")


def test_registry_can_compose_wogole_as_spelling_rule() -> None:
    rule = SpellingWogoleRule()
    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=rule, categories=frozenset({Category.SPELLING})),)
    )

    assert registry.find("wogole", options=AnalysisOptions()) == rule.find(
        "wogole", options=AnalysisOptions()
    )
