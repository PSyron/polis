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
    SyntaxMissingDestinationPrepositionRule,
)


def test_default_analyzer_reports_closed_destination_preposition_error() -> None:
    text = "Pojechałem Warszawy."

    result = Analyzer(AnalyzerConfig()).analyze(text)

    assert len(result.issues) == 1
    finding = result.issues[0]
    assert finding.category is Category.SYNTAX
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == ""
    assert finding.suggestion == "do "
    assert (finding.start, finding.end) == (11, 11)
    assert finding.confidence.value == 0.9
    assert str(finding.source) == "rule:syntax.missing_destination_preposition"


@pytest.mark.parametrize(
    "text",
    (
        "Pojechałem Warszawy.",
        "pojechałem Warszawy.",
        "POJECHAŁEM WARSZAWY.",
    ),
)
def test_rule_accepts_only_the_reviewed_sentence_casing(text: str) -> None:
    findings = SyntaxMissingDestinationPrepositionRule().find(
        text, options=AnalysisOptions()
    )

    assert len(findings) == 1
    assert findings[0].suggestion == "do "


@pytest.mark.parametrize(
    "text",
    (
        "Pojechałem do Warszawy.",
        "Pojechałem warszawy.",
        "Pojechałem Gdańska.",
        "Jadę Warszawy.",
        "Warszawy są dziś zatłoczone.",
        "Pojechałem Warszawy, ale wróciłem szybko.",
        "Pojechałem Warszawy; wróciłem szybko.",
        "Pojechałem Warszawy. Wróciłem szybko.",
        "„Pojechałem Warszawy.”",
        "Napisał: Pojechałem Warszawy.",
        "Dzisiaj pojechałem Warszawy.",
    ),
)
def test_rule_abstains_outside_the_closed_destination_sentence(text: str) -> None:
    findings = SyntaxMissingDestinationPrepositionRule().find(
        text, options=AnalysisOptions()
    )

    assert findings == ()


def test_rule_respects_category_exclusion() -> None:
    findings = SyntaxMissingDestinationPrepositionRule().find(
        "Pojechałem Warszawy.",
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    assert findings == ()


def test_registry_exposes_review_only_behavior_metadata() -> None:
    rule = SyntaxMissingDestinationPrepositionRule()
    registry = DeterministicRuleRegistry((RuleRegistration(rule=rule),))

    assert registry.source_behavior(rule.source) == SourceBehavior(
        source=rule.source,
        operation="insert.destination_preposition",
        behavior_version="syntax-missing-destination-preposition/1.0",
    )


def test_default_correction_skips_rule_until_explicit_application() -> None:
    text = "Pojechałem Warszawy."
    result = Analyzer(AnalyzerConfig()).correct(text)

    assert result.corrected_text == text
    assert result.applied_findings == ()
    assert len(result.skipped_findings) == 1
    assert result.apply_suggestions((result.skipped_findings[0].id,)) == (
        "Pojechałem do Warszawy."
    )


def test_overlapping_explicit_finding_is_rejected() -> None:
    text = "Pojechałem Warszawy."
    finding = Analyzer(AnalyzerConfig()).analyze(text).issues[0]
    overlapping = Finding.create(
        category=Category.SYNTAX,
        severity=Severity.SUGGESTION,
        message="Testowe nakładające się znalezisko.",
        explanation="Testuje odrzucenie konfliktu zakresów.",
        original="Warszawy",
        suggestion="Gdańska",
        start=11,
        end=19,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test.overlap"),
    )
    result = AnalysisResult(text, (finding, overlapping))

    with pytest.raises(CorrectionConflictError):
        result.apply((finding.id, overlapping.id))


def test_finding_json_round_trip_is_canonical_and_stable() -> None:
    result = Analyzer(AnalyzerConfig()).analyze("Pojechałem Warszawy.")

    encoded = result.to_json()
    decoded = AnalysisResult.from_json(encoded)

    assert decoded == result
    assert decoded.to_json() == encoded
    assert '"operation"' not in encoded
    assert '"behavior_version"' not in encoded


def test_cli_emits_exact_single_finding_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "polis.cli",
            "analyze",
            "--json",
            "Pojechałem Warszawy.",
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout == (
        '{"issues":[{"category":"syntax","confidence":0.9,"end":11,'
        '"explanation":"W tej zamkniętej konstrukcji brakuje przyimka '
        '„do”.","id":"finding_340cc2e394aa6468d92c1878d92c9f06",'
        '"message":"Brakuje przyimka „do” przed nazwą celu podróży.",'
        '"original":"","severity":"suggestion","source":'
        '"rule:syntax.missing_destination_preposition","start":11,'
        '"suggestion":"do "}],"options":{"categories":null,'
        '"minimum_confidence":0.0},"schema_version":1,'
        '"text":"Pojechałem Warszawy."}\n'
    )
