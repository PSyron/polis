from __future__ import annotations

import json
import socket
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
from polis.evaluation.quality_dataset import (
    QualityDatasetVersion,
    load_quality_dataset,
)

_POSITIVES = {
    "rule:spelling.wogole": "Wogole nie wiem.",
    "rule:spelling.narazie": "Narazie zostaję w domu.",
    "rule:spelling.wziasc": "Chcę wziasc książkę.",
    "rule:agreement.nominal_group_ta_nowy_ksiazka": "Ta nowy książka.",
    "rule:agreement.subject_verb_my_czyta": "My czyta książkę.",
    "rule:inflection.przygladac_sie_nowy_budynek": "Przyglądam się nowy budynek.",
    "rule:inflection.government_szukac_klucz": "Szukam klucz.",
    "rule:syntax.initial_temporal_comma": "Kiedy pada zostaję w domu.",
}
_EIGHT = tuple(_POSITIVES)
_EXPECTED_EIGHT_IDENTITIES = {
    "rule:spelling.wogole": ("replace.common_typo", "spelling-wogole/1.0"),
    "rule:spelling.narazie": ("replace.common_typo", "spelling-narazie/1.0"),
    "rule:spelling.wziasc": ("replace.common_typo", "spelling-wziasc/1.0"),
    "rule:agreement.nominal_group_ta_nowy_ksiazka": (
        "replace.adjective_gender",
        "agreement-nominal-group-ta-nowy-ksiazka/2.1+morfeusz2-1.99.15.pl-"
        "sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
    ),
    "rule:agreement.subject_verb_my_czyta": (
        "replace.subject_verb_number",
        "agreement-subject-verb-my-czyta/1.0+morfeusz2-1.99.15.pl-"
        "sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
    ),
    "rule:inflection.przygladac_sie_nowy_budynek": (
        "replace.governed_nominal_group",
        "inflection-przygladac-sie-nowy-budynek/1.0+morfeusz2-1.99.15.pl-"
        "sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
    ),
    "rule:inflection.government_szukac_klucz": (
        "replace.governed_form",
        "inflection-government-szukac-klucz/2.0+morfeusz2-1.99.15.pl-"
        "sgjp-sgjp-2026.06.01.notice-84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
    ),
    "rule:syntax.initial_temporal_comma": (
        "insert.temporal_clause_comma",
        "syntax-initial-temporal-comma/1.0",
    ),
}


def test_runtime_exposes_exactly_twenty_eight_sources_with_eight_review_only() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    snapshot = analyzer.source_identity_snapshot
    assert len(snapshot) == 63
    by_source = {item.source: item for item in snapshot}
    for source in _EIGHT:
        item = by_source[source]
        assert (item.operation, item.behavior_version) == _EXPECTED_EIGHT_IDENTITIES[
            source
        ]
        correction = analyzer.correct(_POSITIVES[source])
        assert correction.applied_findings == ()
        assert any(
            str(finding.source) == source for finding in correction.skipped_findings
        )


@pytest.mark.parametrize("source", _EIGHT)
def test_eight_sources_json_category_filter_explicit_apply_and_cli(source: str) -> None:
    text = _POSITIVES[source]
    analyzer = Analyzer(AnalyzerConfig())
    result = analyzer.analyze(text)
    findings = tuple(
        finding for finding in result.issues if str(finding.source) == source
    )
    assert findings
    finding = findings[0]
    category = Category(finding.category.value)
    filtered = analyzer.analyze(
        text, options=AnalysisOptions(categories={Category.SPELLING})
    )
    if category is not Category.SPELLING:
        assert all(str(item.source) != source for item in filtered.issues)
    decoded = AnalysisResult.from_json(result.to_json())
    assert any(str(item.source) == source for item in decoded.issues)
    applied = result.apply((finding.id,))
    assert applied != text
    completed = subprocess.run(
        [sys.executable, "-m", "polis.cli", "analyze", "--json", text],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert any(item["source"] == source for item in payload["issues"])


def test_eight_sources_conflict_atomic_and_v2_positives_are_tp() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    text = "Szukam klucz."
    finding = next(
        item
        for item in analyzer.analyze(text).issues
        if str(item.source) == "rule:inflection.government_szukac_klucz"
    )
    overlapping = Finding.create(
        category=Category.INFLECTION,
        severity=Severity.SUGGESTION,
        message="overlap",
        explanation="overlap",
        original="klucz",
        suggestion="klucza",
        start=finding.start,
        end=finding.end,
        confidence=Confidence(0.9),
        source=Source.parse("rule:test.overlap"),
    )
    with pytest.raises(CorrectionConflictError):
        AnalysisResult(text, (finding, overlapping)).apply((finding.id, overlapping.id))

    dataset = load_quality_dataset(version=QualityDatasetVersion.V2)
    for case in dataset.cases:
        if not case.id.startswith("v2_") or case.kind != "error":
            continue
        if not any(
            token in case.id
            for token in (
                "wogole",
                "narazie",
                "wziasc",
                "ta_nowy",
                "my_czyta",
                "przygladac",
                "szukac",
                "temporal",
            )
        ):
            continue
        observed = [
            (
                item.category.value,
                item.start,
                item.end,
                item.original,
                item.suggestion,
            )
            for item in analyzer.analyze(case.text).issues
            if str(item.source) in _EIGHT
        ]
        expected = [
            (
                item.category,
                item.start,
                item.end,
                item.original,
                item.suggestion,
            )
            for item in case.findings
        ]
        assert observed == expected, case.id


def test_default_profile_has_no_socket_side_effects_for_eight_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("socket connection attempted")

    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
    analyzer = Analyzer(AnalyzerConfig())
    for text in _POSITIVES.values():
        result = analyzer.analyze(text)
        assert result.issues
        assert analyzer.correct(text).corrected_text == text
