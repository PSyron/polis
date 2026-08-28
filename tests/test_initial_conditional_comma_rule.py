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
    RuleRegistration,
    SyntaxInitialConditionalCommaRule,
)
from polis.rules._morfeusz import _load_qualified_morfeusz, _QualifiedMorfeusz


def _provider() -> _QualifiedMorfeusz:
    provider = _load_qualified_morfeusz()
    assert provider is not None
    return provider


def test_default_analyzer_reports_closed_initial_conditional_comma_error() -> None:
    # Given
    text = "Jeśli pada zostaję w domu."

    # When
    result = Analyzer(AnalyzerConfig()).analyze(text)

    # Then
    assert len(result.issues) == 1
    finding = result.issues[0]
    assert finding.category is Category.SYNTAX
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == ""
    assert finding.suggestion == ","
    assert (finding.start, finding.end) == (10, 10)
    assert finding.confidence.value == 0.9
    assert str(finding.source) == "rule:syntax.initial_conditional_comma"


@pytest.mark.parametrize(
    "text",
    (
        "Jeśli pada zostaję w domu.",
        "jeśli pada zostaję w domu.",
        "JEŚLI PADA ZOSTAJĘ W DOMU.",
    ),
)
def test_rule_accepts_only_the_reviewed_sentence_casing(text: str) -> None:
    # Given
    rule = SyntaxInitialConditionalCommaRule(_provider())

    # When
    findings = rule.find(text, options=AnalysisOptions())

    # Then
    assert len(findings) == 1
    assert findings[0].original == ""
    assert findings[0].suggestion == ","
    assert (findings[0].start, findings[0].end) == (10, 10)


@pytest.mark.parametrize(
    "text",
    (
        "Jeśli pada, zostaję w domu.",
        "Zostaję w domu, jeśli pada.",
        "Powiedział, że jeśli pada zostaję w domu.",
        "„Jeśli pada zostaję w domu.”",
        "Zdanie „Jeśli pada zostaję w domu.” nie ma przecinka.",
        "Jeśli pada i wieje zostaję w domu.",
        "Jeśliby padało zostaję w domu.",
        "Jeśli pada zostaję w domu. Potem czytam.",
        "Jeśli chcesz to przyjdź.",
    ),
)
def test_rule_abstains_outside_the_closed_initial_conditional_sentence(
    text: str,
) -> None:
    # Given
    rule = SyntaxInitialConditionalCommaRule(_provider())

    # When
    findings = rule.find(text, options=AnalysisOptions())

    # Then
    assert findings == ()


def test_rule_respects_category_exclusion() -> None:
    # Given
    rule = SyntaxInitialConditionalCommaRule(_provider())

    # When
    findings = rule.find(
        "Jeśli pada zostaję w domu.",
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    # Then
    assert findings == ()


def test_default_analyzer_respects_category_filtering() -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    result = analyzer.analyze(
        "Jeśli pada zostaję w domu.",
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    # Then
    assert result.issues == ()


def test_registry_exposes_review_only_behavior_metadata() -> None:
    # Given
    rule = SyntaxInitialConditionalCommaRule(_provider())
    registry = DeterministicRuleRegistry((RuleRegistration(rule=rule),))

    # When
    behavior = registry.source_behavior(rule.source)

    # Then
    assert behavior == SourceBehavior(
        source=rule.source,
        operation="insert.conditional_clause_comma",
        behavior_version="syntax-initial-conditional-comma/2.0",
    )


def test_default_correction_skips_rule_until_explicit_application() -> None:
    # Given
    text = "Jeśli pada zostaję w domu."
    analyzer = Analyzer(AnalyzerConfig())

    # When
    result = analyzer.correct(text)

    # Then
    assert result.corrected_text == text
    assert result.applied_findings == ()
    assert len(result.skipped_findings) == 1
    assert result.apply_suggestions((result.skipped_findings[0].id,)) == (
        "Jeśli pada, zostaję w domu."
    )


def test_overlapping_explicit_finding_is_rejected() -> None:
    # Given
    text = "Jeśli pada zostaję w domu."
    finding = Analyzer(AnalyzerConfig()).analyze(text).issues[0]
    overlapping = Finding.create(
        category=Category.SYNTAX,
        severity=Severity.SUGGESTION,
        message="Testowe nakładające się znalezisko.",
        explanation="Testuje odrzucenie konfliktu zakresów.",
        original="a ",
        suggestion="a także ",
        start=9,
        end=11,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test.overlap"),
    )
    result = AnalysisResult(text, (finding, overlapping))

    # When / Then
    with pytest.raises(CorrectionConflictError):
        result.apply((finding.id, overlapping.id))


def test_finding_json_round_trip_is_canonical_and_stable() -> None:
    # Given
    result = Analyzer(AnalyzerConfig()).analyze("Jeśli pada zostaję w domu.")

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
        "Jeśli pada zostaję w domu.",
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
        '{"issues":[{"category":"syntax","confidence":0.9,"end":10,'
        '"explanation":"Po początkowym zdaniu warunkowym stawiamy przecinek '
        'przed zdaniem nadrzędnym.","id":"finding_f304f3a5cf8573565c2a28ba0d29e58c",'
        '"message":"Brakuje przecinka po początkowym zdaniu warunkowym.",'
        '"original":"","severity":"suggestion","source":'
        '"rule:syntax.initial_conditional_comma","start":10,"suggestion":","}],'
        '"options":{"categories":null,"minimum_confidence":0.0},'
        '"schema_version":1,"text":"Jeśli pada zostaję w domu."}\n'
    )
