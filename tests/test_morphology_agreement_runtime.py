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

_TEXT = "Te duże okno jest otwarte."
type _SocketAddress = str | tuple[str, int] | tuple[str, int, int, int]
_BEHAVIOR_VERSION = (
    "agreement-nominal-group-te-duze-okno/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)


def test_default_analyzer_reports_the_approved_review_only_finding() -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    result = analyzer.analyze(_TEXT)

    # Then
    assert len(result.issues) == 1
    finding = result.issues[0]
    assert str(finding.source) == "rule:agreement.nominal_group_te_duze_okno"
    assert finding.category is Category.AGREEMENT
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "Te"
    assert finding.suggestion == "To"
    assert (finding.start, finding.end) == (0, 2)
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
    assert correction.apply_suggestions((finding.id,)) == "To duże okno jest otwarte."


def test_rule_filters_by_category_before_the_optional_provider_is_called(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        original="Te",
        suggestion="Ta",
        start=0,
        end=2,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test.overlap"),
    )
    result = AnalysisResult(_TEXT, (finding, overlapping))

    # When / Then
    with pytest.raises(CorrectionConflictError):
        result.apply((finding.id, overlapping.id))


def test_missing_shared_provider_abstains_without_suppressing_existing_rule(
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
    nominal_group = analyzer.analyze(_TEXT)

    # Then
    assert str(existing.issues[0].source) == "rule:inflection.negated_widziec"
    assert nominal_group.issues == ()


@pytest.mark.parametrize(
    "text",
    (
        "To duże okno jest otwarte.",
        "Te duże okna są otwarte.",
        "Te duże dziecko jest gotowe.",
        "Te duży okno jest otwarte.",
        "Dzisiaj Te duże okno jest otwarte.",
        "Te duże okno jest otwarte!",
    ),
)
def test_rule_abstains_outside_the_approved_exact_sentence(text: str) -> None:
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
        "end": 2,
        "explanation": (
            "W tej zamkniętej konstrukcji forma „Te” nie zgadza się z "
            "rzeczownikiem „okno”; oczekiwana jest forma „To”."
        ),
        "id": payload["issues"][0]["id"],
        "message": "Niezgodność form w grupie nominalnej.",
        "original": "Te",
        "severity": "suggestion",
        "source": "rule:agreement.nominal_group_te_duze_okno",
        "start": 0,
        "suggestion": "To",
    }


def test_behavior_identity_is_not_an_automatic_correction_policy_entry() -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    correction = analyzer.correct(_TEXT)

    # Then
    assert correction.applied_findings == ()
    assert correction.skipped_findings[0].source.name == (
        "agreement.nominal_group_te_duze_okno"
    )
    assert _BEHAVIOR_VERSION.startswith("agreement-nominal-group-te-duze-okno/1.0+")
