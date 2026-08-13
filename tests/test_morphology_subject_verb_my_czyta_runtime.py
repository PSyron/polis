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
from polis.rules.subject_verb import AgreementSubjectVerbMyCzytaRule

_TEXT = "My czyta książkę."
_BEHAVIOR_VERSION = (
    "agreement-subject-verb-my-czyta/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
type _SocketAddress = str | tuple[str, int] | tuple[str, int, int, int]


def test_default_analyzer_reports_the_approved_review_only_finding() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    result = analyzer.analyze(_TEXT)

    assert len(result.issues) == 1
    finding = result.issues[0]
    assert str(finding.source) == "rule:agreement.subject_verb_my_czyta"
    assert finding.category is Category.AGREEMENT
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "czyta"
    assert finding.suggestion == "czytamy"
    assert (finding.start, finding.end) == (3, 8)
    assert finding.confidence.value == 0.9


def test_default_analyzer_preserves_finding_through_json_and_explicit_apply() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    finding = analyzer.analyze(_TEXT).issues[0]

    decoded = AnalysisResult.from_json(analyzer.analyze(_TEXT).to_json())
    correction = analyzer.correct(_TEXT)

    assert decoded.issues == (finding,)
    assert correction.corrected_text == _TEXT
    assert correction.applied_findings == ()
    assert correction.skipped_findings == (finding,)
    assert correction.apply_suggestions((finding.id,)) == "My czytamy książkę."


def test_default_analyzer_runs_offline() -> None:
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
        result = analyzer.analyze(_TEXT)
    finally:
        monkeypatch.undo()

    assert len(result.issues) == 1
    assert str(result.issues[0].source) == "rule:agreement.subject_verb_my_czyta"


def test_default_analyzer_filters_agreement_category() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    result = analyzer.analyze(
        _TEXT,
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    assert result.issues == ()


def test_explicit_application_rejects_an_overlapping_finding() -> None:
    finding = Analyzer(AnalyzerConfig()).analyze(_TEXT).issues[0]
    overlapping = Finding.create(
        category=Category.AGREEMENT,
        severity=Severity.SUGGESTION,
        message="Testowe znalezisko konfliktowe.",
        explanation="Testuje odrzucenie nakładających się zakresów.",
        original="czyta",
        suggestion="czytam",
        start=3,
        end=8,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test.overlap"),
    )
    result = AnalysisResult(_TEXT, (finding, overlapping))

    with pytest.raises(CorrectionConflictError):
        result.apply((finding.id, overlapping.id))


def test_missing_provider_abstains_without_suppressing_existing_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        analyzer_module,
        "_load_qualified_morfeusz",
        lambda: None,
        raising=False,
    )
    analyzer = Analyzer(AnalyzerConfig())

    existing = analyzer.analyze("Nie widzę samochód.")
    subject_verb = analyzer.analyze(_TEXT)

    assert str(existing.issues[0].source) == "rule:inflection.negated_widziec"
    assert subject_verb.issues == ()


@pytest.mark.parametrize(
    "text",
    (
        "My czytamy książkę.",
        "On czyta książkę.",
        "Cytat „My czyta książkę” jest przedmiotem rozmowy.",
        "Klucz `my_czyta` wskazuje wariant testowy.",
        "Czytanka dla dzieci leży na biurku.",
        "My czytamy książkę. Potem omawiamy rozdział.",
    ),
)
def test_default_analyzer_abstains_for_close_negatives(text: str) -> None:
    analyzer = Analyzer(AnalyzerConfig())

    result = analyzer.analyze(
        text,
        options=AnalysisOptions(categories={Category.AGREEMENT}),
    )

    assert all(
        str(item.source) != "rule:agreement.subject_verb_my_czyta"
        for item in result.issues
    )


def test_cli_emits_the_approved_review_only_finding() -> None:
    command = [sys.executable, "-m", "polis.cli", "analyze", "--json", _TEXT]

    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    payload = json.loads(completed.stdout)

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert len(payload["issues"]) == 1
    assert payload["issues"][0] == {
        "category": "agreement",
        "confidence": 0.9,
        "end": 8,
        "explanation": (
            "W tej zamkniętej konstrukcji podmiot „My” wymaga formy "
            "czasownika „czytamy”."
        ),
        "id": payload["issues"][0]["id"],
        "message": "Niezgodność liczby podmiotu i czasownika.",
        "original": "czyta",
        "severity": "suggestion",
        "source": "rule:agreement.subject_verb_my_czyta",
        "start": 3,
        "suggestion": "czytamy",
    }


def test_behavior_identity_is_not_an_automatic_correction_policy_entry() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    correction = analyzer.correct(_TEXT)
    finding = correction.skipped_findings[0]
    behavior = analyzer._registry.source_behavior(finding.source)

    assert correction.applied_findings == ()
    assert finding.source.name == "agreement.subject_verb_my_czyta"
    assert behavior is not None
    assert behavior.operation == "replace.subject_verb_number"
    assert behavior.behavior_version == _BEHAVIOR_VERSION


def test_v2_cases_change_expected_errors_to_matches_without_alarms() -> None:
    dataset = load_quality_dataset(version=QualityDatasetVersion.V2)
    cases = tuple(case for case in dataset.cases if case.id.startswith("v2_my_czyta_"))
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
            if str(finding.source) == "rule:agreement.subject_verb_my_czyta"
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
    assert rules.AgreementSubjectVerbMyCzytaRule is AgreementSubjectVerbMyCzytaRule
    assert not hasattr(polis, "AgreementSubjectVerbMyCzytaRule")


def test_registry_can_compose_source_as_agreement_rule() -> None:
    morphology = analyzer_module._load_qualified_morfeusz()
    rule = AgreementSubjectVerbMyCzytaRule(morphology)
    registry = DeterministicRuleRegistry(
        (RuleRegistration(rule=rule, categories=frozenset({Category.AGREEMENT})),)
    )

    assert registry.find(_TEXT, options=AnalysisOptions()) == rule.find(
        _TEXT, options=AnalysisOptions()
    )
