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
from polis.rules.spelling import SpellingNarazieRule


def test_narazie_emits_exact_contract_with_case_and_unicode_offsets() -> None:
    text = "ŻÓŁĆ: NARAZIE; Narazie, narazie."
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
            "rule:spelling.narazie",
            "NARAZIE",
            "NA RAZIE",
            6,
            13,
            0.98,
        ),
        (
            Category.SPELLING,
            Severity.SUGGESTION,
            "rule:spelling.narazie",
            "Narazie",
            "Na razie",
            15,
            22,
            0.98,
        ),
        (
            Category.SPELLING,
            Severity.SUGGESTION,
            "rule:spelling.narazie",
            "narazie",
            "na razie",
            24,
            31,
            0.98,
        ),
    ]
    assert all(text[item.start : item.end] == item.original for item in result.issues)
    assert analyzer._registry.source_behavior(
        result.issues[0].source
    ) == SourceBehavior(
        source=result.issues[0].source,
        operation="replace.common_typo",
        behavior_version="spelling-narazie/1.0",
    )


@pytest.mark.parametrize(
    ("typed", "corrected"),
    (
        ("narazie", "na razie"),
        ("Narazie", "Na razie"),
        ("NARAZIE", "NA RAZIE"),
        ("naRaZiE", "na razie"),
        ("NaRaZiE", "Na razie"),
    ),
)
def test_narazie_uses_existing_case_contract(typed: str, corrected: str) -> None:
    findings = SpellingNarazieRule().find(typed, options=AnalysisOptions())

    assert tuple(item.suggestion for item in findings) == (corrected,)


@pytest.mark.parametrize(
    "text",
    (
        "Na razie zostaję w domu.",
        "naraziex xnarazie przednaraziepo",
        "na-razie na\nrazie na\r\nrazie",
        "Forma „narazie” widnieje w cytowanym komentarzu.",
        "Pole `narazie` zachowujemy dla zgodności formatu.",
    ),
)
def test_narazie_abstains_for_close_negatives_and_mentions(text: str) -> None:
    result = Analyzer(AnalyzerConfig()).analyze(
        text,
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    assert result.issues == ()


def test_narazie_respects_category_filtering() -> None:
    result = Analyzer(AnalyzerConfig()).analyze(
        "Narazie zostaję w domu.",
        options=AnalysisOptions(categories={Category.SYNTAX}),
    )

    assert result.issues == ()


def test_narazie_json_is_stable_and_explicit_application_is_exact() -> None:
    text = "Narazie czekam, ale narazie nie wychodzę."
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
        "Na razie czekam, ale na razie nie wychodzę."
    )


def test_narazie_explicit_application_rejects_overlap() -> None:
    text = "Narazie zostaję w domu."
    finding = Analyzer(AnalyzerConfig()).analyze(text).issues[0]
    overlapping = Finding.create(
        category=Category.SPELLING,
        severity=Severity.SUGGESTION,
        message="Testowe znalezisko konfliktowe.",
        explanation="Testuje odrzucenie nakładających się zakresów.",
        original="Narazie",
        suggestion="Na razie",
        start=0,
        end=7,
        confidence=Confidence(0.98),
        source=Source.parse("rule:test.overlap"),
    )
    result = AnalysisResult(text, (finding, overlapping))

    with pytest.raises(CorrectionConflictError):
        result.apply((finding.id, overlapping.id))


def test_narazie_v2_cases_change_expected_errors_to_matches_without_alarms() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V2)
    cases = tuple(case for case in dataset.cases if case.id.startswith("v2_narazie_"))
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
            if str(finding.source) == "rule:spelling.narazie"
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


def test_cli_json_reports_exact_narazie_finding() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "polis.cli",
            "analyze",
            "--json",
            "Narazie zostaję w domu.",
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
            "end": 7,
            "explanation": "Zamiast 'Narazie' zwykle poprawnie pisze się 'Na razie'.",
            "id": "finding_33f81d27837fae7fd92eae097f48b1ed",
            "message": "Wygląda jak częsty błąd ortograficzny: Narazie.",
            "original": "Narazie",
            "severity": "suggestion",
            "source": "rule:spelling.narazie",
            "start": 0,
            "suggestion": "Na razie",
        }
    ]


def test_rules_package_exports_narazie_without_root_export() -> None:
    assert rules.SpellingNarazieRule is SpellingNarazieRule
    assert not hasattr(polis, "SpellingNarazieRule")


def test_registry_can_compose_narazie_as_spelling_rule() -> None:
    rule = SpellingNarazieRule()
    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=rule, categories=frozenset({Category.SPELLING})),)
    )

    assert registry.find("narazie", options=AnalysisOptions()) == rule.find(
        "narazie", options=AnalysisOptions()
    )
