from __future__ import annotations

import json
import socket
import subprocess
import sys
from typing import Never

import pytest

import polis.analyzer as analyzer_module
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

_TEXT = "Oni czyta książkę."
_BEHAVIOR_VERSION = (
    "agreement-subject-verb-oni-czyta/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
type _SocketAddress = str | tuple[str, int] | tuple[str, int, int, int]


def test_default_analyzer_reports_the_approved_review_only_finding() -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    result = analyzer.analyze(_TEXT)

    # Then
    assert len(result.issues) == 1
    finding = result.issues[0]
    assert str(finding.source) == "rule:agreement.subject_verb_oni_czyta"
    assert finding.category is Category.AGREEMENT
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "czyta"
    assert finding.suggestion == "czytają"
    assert (finding.start, finding.end) == (4, 9)
    assert finding.confidence.value == 0.9


def test_default_analyzer_preserves_finding_through_json_and_explicit_apply() -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())
    finding = analyzer.analyze(_TEXT).issues[0]

    # When
    decoded = AnalysisResult.from_json(analyzer.analyze(_TEXT).to_json())
    correction = analyzer.correct(_TEXT)

    # Then
    assert decoded.issues == (finding,)
    assert correction.corrected_text == _TEXT
    assert correction.applied_findings == ()
    assert correction.skipped_findings == (finding,)
    assert correction.apply_suggestions((finding.id,)) == "Oni czytają książkę."


def test_default_analyzer_runs_offline() -> None:
    # Given
    def reject_network(
        address: _SocketAddress,
        timeout: float | None = None,
        source_address: _SocketAddress | None = None,
    ) -> Never:
        del address, timeout, source_address
        raise AssertionError("network access attempted")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)
    try:
        analyzer = Analyzer(AnalyzerConfig())

        # When
        result = analyzer.analyze(_TEXT)
    finally:
        monkeypatch.undo()

    # Then
    assert len(result.issues) == 1
    assert str(result.issues[0].source) == "rule:agreement.subject_verb_oni_czyta"


def test_default_analyzer_filters_agreement_category() -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    result = analyzer.analyze(
        _TEXT,
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    # Then
    assert result.issues == ()


def test_explicit_application_rejects_an_overlapping_finding() -> None:
    # Given
    finding = Analyzer(AnalyzerConfig()).analyze(_TEXT).issues[0]
    overlapping = Finding.create(
        category=Category.AGREEMENT,
        severity=Severity.SUGGESTION,
        message="Testowe znalezisko konfliktowe.",
        explanation="Testuje odrzucenie nakładających się zakresów.",
        original="czyta",
        suggestion="czytam",
        start=4,
        end=9,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test.overlap"),
    )
    result = AnalysisResult(_TEXT, (finding, overlapping))

    # When / Then
    with pytest.raises(CorrectionConflictError):
        result.apply((finding.id, overlapping.id))


def test_missing_provider_abstains_without_suppressing_existing_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    monkeypatch.setattr(
        analyzer_module,
        "_load_qualified_morfeusz",
        lambda: None,
        raising=False,
    )
    analyzer = Analyzer(AnalyzerConfig())

    # When
    existing = analyzer.analyze("Nie widzę samochód.")
    subject_verb = analyzer.analyze(_TEXT)

    # Then
    assert str(existing.issues[0].source) == "rule:inflection.negated_widziec"
    assert subject_verb.issues == ()


@pytest.mark.parametrize(
    "text",
    (
        pytest.param("Oni czytają książkę.", id="correct_plural"),
        pytest.param("On czyta książkę.", id="singular_subject"),
        pytest.param("One czytają książkę.", id="one_plural"),
        pytest.param("Czyta książkę.", id="elided"),
        pytest.param("Oni i one czyta książkę.", id="coordinated_subject"),
        pytest.param("Uczniowie czyta książkę.", id="unknown_subject"),
        pytest.param("Oni czyta i pisze książkę.", id="coordinated_predicate"),
        pytest.param("oni czyta książkę.", id="lowercase_subject"),
    ),
)
def test_default_analyzer_abstains_for_eight_named_close_negative_sentences(
    text: str,
) -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    result = analyzer.analyze(text)

    # Then
    assert result.issues == ()


def test_cli_emits_the_approved_review_only_finding() -> None:
    # Given
    command = [sys.executable, "-m", "polis.cli", "analyze", "--json", _TEXT]

    # When
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(completed.stdout)

    # Then
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert len(payload["issues"]) == 1
    assert payload["issues"][0] == {
        "category": "agreement",
        "confidence": 0.9,
        "end": 9,
        "explanation": (
            "W tej zamkniętej konstrukcji podmiot „Oni” wymaga formy "
            "czasownika „czytają”."
        ),
        "id": payload["issues"][0]["id"],
        "message": "Niezgodność liczby podmiotu i czasownika.",
        "original": "czyta",
        "severity": "suggestion",
        "source": "rule:agreement.subject_verb_oni_czyta",
        "start": 4,
        "suggestion": "czytają",
    }


def test_behavior_identity_is_not_an_automatic_correction_policy_entry() -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    correction = analyzer.correct(_TEXT)
    finding = correction.skipped_findings[0]
    behavior = analyzer._registry.source_behavior(finding.source)

    # Then
    assert correction.applied_findings == ()
    assert finding.source.name == "agreement.subject_verb_oni_czyta"
    assert behavior is not None
    assert behavior.operation == "replace.subject_verb_number"
    assert behavior.behavior_version == _BEHAVIOR_VERSION
