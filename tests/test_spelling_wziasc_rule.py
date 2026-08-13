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
from polis.rules.spelling import SpellingWziascRule


def test_wziasc_emits_exact_contract_with_case_and_unicode_offsets() -> None:
    text = "ŁÓDŹ: WZIASC; Wziasc, wziasc."
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
            "rule:spelling.wziasc",
            "WZIASC",
            "WZIĄĆ",
            6,
            12,
            0.98,
        ),
        (
            Category.SPELLING,
            Severity.SUGGESTION,
            "rule:spelling.wziasc",
            "Wziasc",
            "Wziąć",
            14,
            20,
            0.98,
        ),
        (
            Category.SPELLING,
            Severity.SUGGESTION,
            "rule:spelling.wziasc",
            "wziasc",
            "wziąć",
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
        behavior_version="spelling-wziasc/1.0",
    )


@pytest.mark.parametrize(
    ("typed", "corrected"),
    (
        ("wziasc", "wziąć"),
        ("Wziasc", "Wziąć"),
        ("WZIASC", "WZIĄĆ"),
        ("wzIaSc", "wziąć"),
        ("WzIaSc", "Wziąć"),
    ),
)
def test_wziasc_uses_existing_case_contract(typed: str, corrected: str) -> None:
    findings = SpellingWziascRule().find(typed, options=AnalysisOptions())

    assert tuple(item.suggestion for item in findings) == (corrected,)


@pytest.mark.parametrize(
    "text",
    (
        "Chcę wziąć parasol.",
        "wziascx xwziasc przedwziascpo",
        "wzi-asc wzi\nasc wzi\r\nasc",
        "Zapis „wziasc” cytujemy bez ingerencji.",
        "Funkcja `wziasc()` pochodzi ze starego przykładu.",
    ),
)
def test_wziasc_abstains_for_close_negatives_and_mentions(text: str) -> None:
    result = Analyzer(AnalyzerConfig()).analyze(
        text,
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    assert result.issues == ()


def test_wziasc_respects_category_filtering() -> None:
    result = Analyzer(AnalyzerConfig()).analyze(
        "Chcę wziasc parasol.",
        options=AnalysisOptions(categories={Category.SYNTAX}),
    )

    assert result.issues == ()


def test_wziasc_json_is_stable_and_explicit_application_is_exact() -> None:
    text = "Muszę wziasc płaszcz i wziasc parasol."
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
        "Muszę wziąć płaszcz i wziąć parasol."
    )


def test_wziasc_explicit_application_rejects_overlap() -> None:
    text = "Chcę wziasc parasol."
    finding = Analyzer(AnalyzerConfig()).analyze(text).issues[0]
    overlapping = Finding.create(
        category=Category.SPELLING,
        severity=Severity.SUGGESTION,
        message="Testowe znalezisko konfliktowe.",
        explanation="Testuje odrzucenie nakładających się zakresów.",
        original="wziasc",
        suggestion="wziąć",
        start=5,
        end=11,
        confidence=Confidence(0.98),
        source=Source.parse("rule:test.overlap"),
    )
    result = AnalysisResult(text, (finding, overlapping))

    with pytest.raises(CorrectionConflictError):
        result.apply((finding.id, overlapping.id))


def test_wziasc_v2_cases_change_expected_errors_to_matches_without_alarms() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V2)
    cases = tuple(case for case in dataset.cases if case.id.startswith("v2_wziasc_"))
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
            if str(finding.source) == "rule:spelling.wziasc"
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


def test_cli_json_reports_exact_wziasc_finding() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "polis.cli",
            "analyze",
            "--json",
            "Chcę wziasc parasol.",
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
            "end": 11,
            "explanation": "Zamiast 'wziasc' zwykle poprawnie pisze się 'wziąć'.",
            "id": "finding_bce87853b700a39b9ae628f19b11caa6",
            "message": "Wygląda jak częsty błąd ortograficzny: wziasc.",
            "original": "wziasc",
            "severity": "suggestion",
            "source": "rule:spelling.wziasc",
            "start": 5,
            "suggestion": "wziąć",
        }
    ]


def test_rules_package_exports_wziasc_without_root_export() -> None:
    assert rules.SpellingWziascRule is SpellingWziascRule
    assert not hasattr(polis, "SpellingWziascRule")


def test_registry_can_compose_wziasc_as_spelling_rule() -> None:
    rule = SpellingWziascRule()
    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=rule, categories=frozenset({Category.SPELLING})),)
    )

    assert registry.find("wziasc", options=AnalysisOptions()) == rule.find(
        "wziasc", options=AnalysisOptions()
    )
