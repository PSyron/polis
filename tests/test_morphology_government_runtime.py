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

_TEXT = "Potrzebuję pomoc."
_BEHAVIOR_VERSION = (
    "inflection-government-potrzebowac-pomoc/2.0+"
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
    assert str(finding.source) == "rule:inflection.government_potrzebowac_pomoc"
    assert finding.category is Category.INFLECTION
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "pomoc"
    assert finding.suggestion == "pomocy"
    assert (finding.start, finding.end) == (11, 16)
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
    assert correction.apply_suggestions((finding.id,)) == "Potrzebuję pomocy."


def test_default_analyzer_runs_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    def reject_network(
        address: _SocketAddress,
        timeout: float | None = None,
        source_address: _SocketAddress | None = None,
    ) -> Never:
        del address, timeout, source_address
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)

    analyzer = Analyzer(AnalyzerConfig())

    # When
    result = analyzer.analyze(_TEXT)

    # Then
    assert len(result.issues) == 1
    assert str(result.issues[0].source) == (
        "rule:inflection.government_potrzebowac_pomoc"
    )


def test_default_analyzer_filters_inflection_category() -> None:
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
        category=Category.INFLECTION,
        severity=Severity.SUGGESTION,
        message="Testowe znalezisko konfliktowe.",
        explanation="Testuje odrzucenie nakładających się zakresów.",
        original="pomoc",
        suggestion="wsparcie",
        start=11,
        end=16,
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
    government = analyzer.analyze(_TEXT)

    # Then
    assert str(existing.issues[0].source) == "rule:inflection.negated_widziec"
    assert government.issues == ()


@pytest.mark.parametrize(
    ("text", "source"),
    (
        (
            "Nie widzę czerwony samochód.",
            "rule:inflection.negated_widziec_nominal_group",
        ),
        ("Te duże okno jest otwarte.", "rule:agreement.nominal_group_te_duze_okno"),
        ("Oni czyta książkę.", "rule:agreement.subject_verb_oni_czyta"),
    ),
)
def test_existing_morphology_rules_remain_available(
    text: str,
    source: str,
) -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    result = analyzer.analyze(text)

    # Then
    assert len(result.issues) == 1
    assert str(result.issues[0].source) == source


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
        "category": "inflection",
        "confidence": 0.9,
        "end": 16,
        "explanation": (
            "W tej zamkniętej konstrukcji czasownik „Potrzebuję” wymaga formy "
            "dopełniacza „pomocy”."
        ),
        "id": payload["issues"][0]["id"],
        "message": "Niepoprawna forma dopełnienia po czasowniku „potrzebować”.",
        "original": "pomoc",
        "severity": "suggestion",
        "source": "rule:inflection.government_potrzebowac_pomoc",
        "start": 11,
        "suggestion": "pomocy",
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
    assert finding.source.name == "inflection.government_potrzebowac_pomoc"
    assert behavior is not None
    assert behavior.operation == "replace.governed_form"
    assert behavior.behavior_version == _BEHAVIOR_VERSION
