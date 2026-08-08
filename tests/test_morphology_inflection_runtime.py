from __future__ import annotations

import json
import socket
import subprocess
import sys

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
from polis.rules._morfeusz_negated_widziec import (
    _load_qualified_negated_widziec_morphology,
    _NegatedWidziecMorphology,
    _ProviderIdentity,
)

_NOTICE_SHA256 = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
type _AnalysisRow = tuple[
    int,
    int,
    tuple[str, str, str, list[str], list[str]],
]
type _GenerationRow = tuple[str, str, str, list[str], list[str]]


class _QualifiedBackend:
    def analyse(self, text: str) -> list[_AnalysisRow]:
        rows: dict[str, list[_AnalysisRow]] = {
            "czerwony": [
                (
                    0,
                    1,
                    (
                        "czerwony",
                        "czerwony:A",
                        "adj:sg:nom.voc:m1.m2.m3:pos",
                        [],
                        [],
                    ),
                )
            ],
            "samochód": [
                (0, 1, ("samochód", "samochód", "subst:sg:nom.acc:m3", [], []))
            ],
        }
        return rows[text]

    def generate(self, lemma: str) -> list[_GenerationRow]:
        rows: dict[str, list[_GenerationRow]] = {
            "czerwony:A": [
                (
                    "czerwonego",
                    "czerwony:A",
                    "adj:sg:gen:m1.m2.m3.n:pos",
                    [],
                    [],
                )
            ],
            "samochód": [("samochodu", "samochód", "subst:sg:gen:m3", [], [])],
        }
        return rows[lemma]


def _provider() -> _NegatedWidziecMorphology:
    return _NegatedWidziecMorphology(
        backend=_QualifiedBackend(),
        identity=_ProviderIdentity(
            package_version="1.99.15",
            dictionary_id="pl.sgjp.sgjp-2026.06.01",
            dictionary_notice_sha256=_NOTICE_SHA256,
        ),
    )


def _install_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        analyzer_module,
        "_load_qualified_negated_widziec_morphology",
        _provider,
    )


def test_default_analyzer_emits_one_public_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    _install_provider(monkeypatch)
    analyzer = Analyzer(AnalyzerConfig())

    # When
    result = analyzer.analyze("Nie widzę czerwony samochód.")

    # Then
    assert len(result.issues) == 1
    assert str(result.issues[0].source) == (
        "rule:inflection.negated_widziec_nominal_group"
    )


def test_default_analyzer_respects_inflection_category_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    _install_provider(monkeypatch)
    analyzer = Analyzer(AnalyzerConfig())

    # When
    included = analyzer.analyze(
        "Nie widzę czerwony samochód.",
        options=AnalysisOptions(categories={Category.INFLECTION}),
    )
    excluded = analyzer.analyze(
        "Nie widzę czerwony samochód.",
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    # Then
    assert len(included.issues) == 1
    assert excluded.issues == ()


def test_finding_round_trip_keeps_public_schema_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    _install_provider(monkeypatch)
    result = Analyzer(AnalyzerConfig()).analyze("Nie widzę czerwony samochód.")

    # When
    encoded = result.to_json()
    decoded = AnalysisResult.from_json(encoded)

    # Then
    assert decoded == result
    assert '"schema_version":1' in encoded
    assert '"operation"' not in encoded
    assert '"behavior_version"' not in encoded


def test_correction_skips_until_explicit_application(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    _install_provider(monkeypatch)
    text = "Nie widzę czerwony samochód."

    # When
    result = Analyzer(AnalyzerConfig()).correct(text)

    # Then
    assert result.corrected_text == text
    assert result.applied_findings == ()
    assert len(result.skipped_findings) == 1
    assert result.apply_suggestions((result.skipped_findings[0].id,)) == (
        "Nie widzę czerwonego samochodu."
    )


def test_overlapping_explicit_findings_still_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    _install_provider(monkeypatch)
    text = "Nie widzę czerwony samochód."
    finding = Analyzer(AnalyzerConfig()).analyze(text).issues[0]
    overlapping = Finding.create(
        category=Category.INFLECTION,
        severity=Severity.SUGGESTION,
        message="Testowe znalezisko konfliktowe.",
        explanation="Testuje odrzucenie nakładających się zakresów.",
        original="samochód",
        suggestion="auta",
        start=19,
        end=27,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test.overlap"),
    )
    result = AnalysisResult(text, (finding, overlapping))

    # When / Then
    with pytest.raises(CorrectionConflictError):
        result.apply((finding.id, overlapping.id))


def test_missing_provider_preserves_other_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    monkeypatch.setattr(
        analyzer_module,
        "_load_qualified_negated_widziec_morphology",
        lambda: None,
    )
    analyzer = Analyzer(AnalyzerConfig())

    # When
    old_result = analyzer.analyze("Nie widzę samochód.")
    new_result = analyzer.analyze("Nie widzę czerwony samochód.")

    # Then
    assert str(old_result.issues[0].source) == "rule:inflection.negated_widziec"
    assert new_result.issues == ()


def test_real_provider_stays_offline_from_analyzer_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    def reject_network(*_arguments: object, **_keywords: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    monkeypatch.setattr(socket.socket, "connect_ex", reject_network)
    monkeypatch.setattr(socket, "create_connection", reject_network)

    # When
    result = Analyzer(AnalyzerConfig()).analyze("Nie widzę czerwony samochód.")

    # Then
    assert len(result.issues) == 1
    assert result.issues[0].suggestion == "czerwonego samochodu"


def test_loader_abstains_when_provider_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    def missing_module(_name: str) -> None:
        raise ModuleNotFoundError

    monkeypatch.setattr(
        "polis.rules._morfeusz_negated_widziec.importlib.import_module",
        missing_module,
    )

    # When
    provider = _load_qualified_negated_widziec_morphology()

    # Then
    assert provider is None


def test_cli_emits_exact_review_only_finding() -> None:
    # Given
    command = [
        sys.executable,
        "-m",
        "polis.cli",
        "analyze",
        "--json",
        "Nie widzę czerwony samochód.",
    ]

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
    assert payload["schema_version"] == 1
    assert len(payload["issues"]) == 1
    issue = payload["issues"][0]
    assert issue["category"] == "inflection"
    assert issue["confidence"] == 0.9
    assert issue["end"] == 27
    assert issue["original"] == "czerwony samochód"
    assert issue["severity"] == "suggestion"
    assert issue["source"] == "rule:inflection.negated_widziec_nominal_group"
    assert issue["start"] == 10
    assert issue["suggestion"] == "czerwonego samochodu"
    assert "operation" not in issue
    assert "behavior_version" not in issue
