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
from polis.rules.agreement import AgreementNominalGroupTaNowyKsiazkaRule

_TEXT = "Ta nowy książka."
_BEHAVIOR_VERSION = (
    "agreement-nominal-group-ta-nowy-ksiazka/2.1+"
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
    assert str(finding.source) == "rule:agreement.nominal_group_ta_nowy_ksiazka"
    assert finding.category is Category.AGREEMENT
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "nowy"
    assert finding.suggestion == "nowa"
    assert (finding.start, finding.end) == (3, 7)
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
    assert correction.apply_suggestions((finding.id,)) == "Ta nowa książka."


def test_generalized_finding_remains_review_only_until_explicit_apply() -> None:
    text = "To duży okno."
    analyzer = Analyzer(AnalyzerConfig())
    finding = analyzer.analyze(text).issues[0]

    correction = analyzer.correct(text)

    assert correction.corrected_text == text
    assert correction.applied_findings == ()
    assert correction.skipped_findings == (finding,)
    assert correction.apply_suggestions((finding.id,)) == "To duże okno."


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
    assert (
        str(result.issues[0].source) == "rule:agreement.nominal_group_ta_nowy_ksiazka"
    )


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
        original="nowy",
        suggestion="nowe",
        start=3,
        end=7,
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
        "Ta nowa książka.",
        "Te nowy książka.",
        "Ta nowy książki.",
        "Ta czerwony Warszawa.",
        "Ta czerwony książka,",
        "Ta czerwony książka i Ten nowy samochód.",
        "Napis „Ta nowy książka” omawiamy na zajęciach.",
        "Stała `ta_nowy_ksiazka` jest identyfikatorem testu.",
        "Termin „odnowy” nie tworzy grupy nominalnej z książką.",
    ),
)
def test_rule_abstains_outside_the_approved_exact_phrase(text: str) -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    result = analyzer.analyze(text)

    # Then
    assert result.issues == ()


@pytest.mark.parametrize(
    ("text", "original", "suggestion", "start", "end"),
    (
        ("Ta czerwony książka.", "czerwony", "czerwona", 3, 11),
        ("To duży okno.", "duży", "duże", 3, 7),
        ("Ten nowa samochód.", "nowa", "nowy", 4, 8),
        ("Ta stary książka.", "stary", "stara", 3, 8),
        ("Ta nowe książka.", "nowe", "nowa", 3, 7),
    ),
)
def test_default_analyzer_reports_generalized_agreement_finding(
    text: str, original: str, suggestion: str, start: int, end: int
) -> None:
    result = Analyzer(AnalyzerConfig()).analyze(text)

    assert [
        (finding.original, finding.suggestion, finding.start, finding.end)
        for finding in result.issues
        if str(finding.source) == "rule:agreement.nominal_group_ta_nowy_ksiazka"
    ] == [(original, suggestion, start, end)]


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
        "end": 7,
        "explanation": (
            "W tej zamkniętej konstrukcji forma „nowy” nie zgadza się z "
            "rzeczownikiem „książka”; oczekiwana jest forma „nowa”."
        ),
        "id": payload["issues"][0]["id"],
        "message": "Niezgodność form w grupie nominalnej.",
        "original": "nowy",
        "severity": "suggestion",
        "source": "rule:agreement.nominal_group_ta_nowy_ksiazka",
        "start": 3,
        "suggestion": "nowa",
    }


def test_behavior_identity_is_not_an_automatic_correction_policy_entry() -> None:
    # Given
    analyzer = Analyzer(AnalyzerConfig())

    # When
    correction = analyzer.correct(_TEXT)

    # Then
    assert correction.applied_findings == ()
    assert correction.skipped_findings[0].source.name == (
        "agreement.nominal_group_ta_nowy_ksiazka"
    )
    assert _BEHAVIOR_VERSION.startswith("agreement-nominal-group-ta-nowy-ksiazka/2.1+")


def test_v2_cases_change_expected_errors_to_matches_without_alarms() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V2)
    cases = tuple(
        case for case in dataset.cases if case.id.startswith("v2_ta_nowy_ksiazka_")
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
            if str(finding.source) == "rule:agreement.nominal_group_ta_nowy_ksiazka"
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


def test_rules_package_exports_source_without_root_export() -> None:
    assert rules.AgreementNominalGroupTaNowyKsiazkaRule is (
        AgreementNominalGroupTaNowyKsiazkaRule
    )
    assert not hasattr(polis, "AgreementNominalGroupTaNowyKsiazkaRule")


def test_registry_can_compose_source_as_agreement_rule() -> None:
    morphology = analyzer_module._load_qualified_morfeusz()
    rule = AgreementNominalGroupTaNowyKsiazkaRule(morphology)
    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=rule, categories=frozenset({Category.AGREEMENT})),)
    )

    assert registry.find(_TEXT, options=AnalysisOptions()) == rule.find(
        _TEXT, options=AnalysisOptions()
    )
