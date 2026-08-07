from __future__ import annotations

import subprocess
import sys

import pytest

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
from polis.rules import (
    DeterministicRuleRegistry,
    InflectionNegatedWidziecRule,
    RuleRegistration,
)


def test_default_analyzer_reports_negated_widziec_government_error() -> None:
    # Given
    text = "Nie widzę samochód."

    # When
    result = Analyzer(AnalyzerConfig()).analyze(text)

    # Then
    assert len(result.issues) == 1
    finding = result.issues[0]
    assert finding.category is Category.INFLECTION
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "samochód"
    assert finding.suggestion == "samochodu"
    assert (finding.start, finding.end) == (10, 18)
    assert finding.confidence.value == 0.9
    assert str(finding.source) == "rule:inflection.negated_widziec"


@pytest.mark.parametrize(
    ("text", "original", "suggestion"),
    (
        ("nie widzę samochód.", "samochód", "samochodu"),
        ("NIE WIDZĘ SAMOCHÓD.", "SAMOCHÓD", "SAMOCHODU"),
    ),
)
def test_rule_preserves_approved_sentence_casing(
    text: str, original: str, suggestion: str
) -> None:
    # Given
    rule = InflectionNegatedWidziecRule()

    # When
    findings = rule.find(text, options=AnalysisOptions())

    # Then
    assert len(findings) == 1
    assert findings[0].original == original
    assert findings[0].suggestion == suggestion


@pytest.mark.parametrize(
    "text",
    (
        "Nie widzę samochodu.",
        "Widzę samochód.",
        "Nie widzę rower.",
        "Nie widzę nowy samochód.",
        "XNie widzę samochód.",
        "Nie widzę samochód, ale widzę rower.",
        "Nie widzę samochód; idę pieszo.",
        "Nie widzę samochód. Widzę rower.",
        "„Nie widzę samochód.”",
        "Zdanie Nie widzę samochód. jest błędne.",
        "Dzisiaj nie widzę samochód.",
    ),
)
def test_rule_abstains_outside_the_closed_sentence(text: str) -> None:
    # Given
    rule = InflectionNegatedWidziecRule()

    # When
    findings = rule.find(text, options=AnalysisOptions())

    # Then
    assert findings == ()


def test_rule_respects_category_exclusion() -> None:
    # Given
    rule = InflectionNegatedWidziecRule()

    # When
    findings = rule.find(
        "Nie widzę samochód.",
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    # Then
    assert findings == ()


def test_registry_exposes_review_only_behavior_metadata() -> None:
    # Given
    rule = InflectionNegatedWidziecRule()
    registry = DeterministicRuleRegistry((RuleRegistration(rule=rule),))

    # When
    behavior = registry.source_behavior(rule.source)

    # Then
    assert behavior == SourceBehavior(
        source=rule.source,
        operation="replace.negated_government_form",
        behavior_version="inflection-negated-widziec/1.0",
    )


def test_default_correction_skips_rule_until_explicit_application() -> None:
    # Given
    text = "Nie widzę samochód."
    analyzer = Analyzer(AnalyzerConfig())

    # When
    result = analyzer.correct(text)

    # Then
    assert result.corrected_text == text
    assert result.applied_findings == ()
    assert len(result.skipped_findings) == 1
    assert result.apply_suggestions((result.skipped_findings[0].id,)) == (
        "Nie widzę samochodu."
    )


def test_overlapping_explicit_finding_is_rejected() -> None:
    # Given
    text = "Nie widzę samochód."
    finding = Analyzer(AnalyzerConfig()).analyze(text).issues[0]
    overlapping = Finding.create(
        category=Category.INFLECTION,
        severity=Severity.SUGGESTION,
        message="Testowe nakładające się znalezisko.",
        explanation="Testuje odrzucenie konfliktu zakresów.",
        original="samochód.",
        suggestion="auta.",
        start=10,
        end=19,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test.overlap"),
    )
    result = AnalysisResult(text, (finding, overlapping))

    # When / Then
    with pytest.raises(CorrectionConflictError):
        result.apply((finding.id, overlapping.id))


def test_finding_json_round_trip_is_canonical_and_stable() -> None:
    # Given
    result = Analyzer(AnalyzerConfig()).analyze("Nie widzę samochód.")

    # When
    encoded = result.to_json()
    decoded = AnalysisResult.from_json(encoded)

    # Then
    assert decoded == result
    assert decoded.to_json() == encoded
    assert '"operation"' not in encoded
    assert '"behavior_version"' not in encoded


def test_cli_emits_exact_single_finding_json() -> None:
    # Given
    command = [
        sys.executable,
        "-m",
        "polis.cli",
        "analyze",
        "--json",
        "Nie widzę samochód.",
    ]

    # When
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    # Then
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout == (
        '{"issues":[{"category":"inflection","confidence":0.9,"end":18,'
        '"explanation":"W tej zamkniętej konstrukcji zaprzeczenie wymaga formy '
        '„samochodu”.","id":"finding_94b269524dd0701e5a4912c4ad964ae4",'
        '"message":"Niepoprawna forma dopełnienia po zaprzeczonym „widzieć”.",'
        '"original":"samochód","severity":"suggestion","source":'
        '"rule:inflection.negated_widziec","start":10,"suggestion":"samochodu"}],'
        '"options":{"categories":null,"minimum_confidence":0.0},'
        '"schema_version":1,"text":"Nie widzę samochód."}\n'
    )
