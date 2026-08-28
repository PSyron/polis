from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest

from polis import AnalysisOptions
from polis.core import Category
from polis.correction.policy import SourceBehavior
from polis.rules._morfeusz import (
    _AnalysisRow,
    _load_qualified_morfeusz,
    _ProviderIdentity,
    _qualified_identity,
    _QualifiedMorfeusz,
)
from polis.rules.syntax import (
    SyntaxInitialConditionalCommaRule,
    SyntaxInitialTemporalCommaRule,
)

type _ProviderRow = _AnalysisRow

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class _RowsBackend:
    rows: Sequence[_ProviderRow]

    def analyse(self, text: str) -> Sequence[_ProviderRow]:
        return self.rows

    def generate(self, lemma: str) -> Sequence[_ProviderRow]:
        return ()


@dataclass(frozen=True, slots=True)
class _ExplodingBackend:
    def analyse(self, text: str) -> Sequence[_ProviderRow]:
        raise AssertionError("provider must not be called")

    def generate(self, lemma: str) -> Sequence[_ProviderRow]:
        return ()


def _provider() -> _QualifiedMorfeusz:
    provider = _load_qualified_morfeusz()
    assert provider is not None
    return provider


@pytest.mark.parametrize(
    "rule_type",
    (SyntaxInitialConditionalCommaRule, SyntaxInitialTemporalCommaRule),
)
def test_rules_abstain_without_a_provider(rule_type: type) -> None:
    # Given
    rule = rule_type(None)

    # When
    findings = rule.find("Jeśli pada wracam.", options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    ("package_version", "dictionary_id", "notice_sha256"),
    (
        (
            "1.99.16",
            "pl.sgjp.sgjp-2026.06.01",
            "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
        ),
        (
            "1.99.15",
            "pl.sgjp.sgjp-2026.06.02",
            "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
        ),
        (
            "1.99.15",
            "pl.sgjp.sgjp-2026.06.01",
            "04a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049399",
        ),
    ),
)
def test_rule_abstains_on_provider_identity_drift(
    package_version: str, dictionary_id: str, notice_sha256: str
) -> None:
    # Given
    provider = _provider()
    drifted = _QualifiedMorfeusz(
        backend=provider.backend,
        identity=_ProviderIdentity(package_version, dictionary_id, notice_sha256),
    )
    rule = SyntaxInitialConditionalCommaRule(drifted)

    # When
    findings = rule.find("Jeśli pada wracam.", options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    "rows",
    (
        ((True, 1, ("Jeśli", "jeśli", "comp", [], [])),),
        ((0, 1, ("Jeśli", "jeśli", "unknown", [], [])),),
        ((0, 1, ("Jeśli", "jeśli", "comp", [])),),
    ),
)
def test_rule_abstains_on_malformed_provider_rows(
    rows: Sequence[_ProviderRow],
) -> None:
    # Given
    rule = SyntaxInitialConditionalCommaRule(
        _QualifiedMorfeusz(_RowsBackend(rows), _qualified_identity())
    )

    # When
    findings = rule.find("Jeśli pada wracam.", options=AnalysisOptions())

    # Then
    assert findings == ()


def test_rule_abstains_on_ambiguous_predicate_analysis() -> None:
    # Given
    provider = _provider()
    text = "Jeśli pada wracam."
    rows = tuple(provider.backend.analyse(text))
    ambiguous = (*rows, (1, 2, ("pada", "paść", "fin:sg:ter:perf", [], [])))
    rule = SyntaxInitialConditionalCommaRule(
        _QualifiedMorfeusz(_RowsBackend(ambiguous), _qualified_identity())
    )

    # When
    findings = rule.find(text, options=AnalysisOptions())

    # Then
    assert findings == ()


def test_category_filter_excludes_provider_before_analysis() -> None:
    # Given
    rule = SyntaxInitialConditionalCommaRule(
        _QualifiedMorfeusz(_ExplodingBackend(), _qualified_identity())
    )

    # When
    findings = rule.find(
        "Jeśli pada wracam.",
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    # Then
    assert findings == ()


def test_analyzer_abstains_from_lone_surrogate_without_crashing() -> None:
    # Given
    program = (
        "from polis import Analyzer, AnalyzerConfig\n"
        "text = 'Jeśli ' + chr(0xD800)\n"
        "result = Analyzer(AnalyzerConfig()).analyze(text)\n"
        "print(len(result.issues))\n"
    )

    # When
    completed = subprocess.run(
        [sys.executable, "-c", program],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    # Then
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == "0\n"


def test_non_target_initial_text_skips_provider_analysis() -> None:
    # Given
    rule = SyntaxInitialConditionalCommaRule(
        _QualifiedMorfeusz(_ExplodingBackend(), _qualified_identity())
    )

    # When
    findings = rule.find("Chociaż pada wracam.", options=AnalysisOptions())

    # Then
    assert findings == ()


def test_source_identities_bump_both_behavior_versions() -> None:
    # Given
    provider = _provider()
    conditional = SyntaxInitialConditionalCommaRule(provider)
    temporal = SyntaxInitialTemporalCommaRule(provider)

    # When
    behaviors = (
        SourceBehavior(
            conditional.source,
            conditional.operation,
            conditional.behavior_version,
        ),
        SourceBehavior(temporal.source, temporal.operation, temporal.behavior_version),
    )

    # Then
    assert behaviors == (
        SourceBehavior(
            conditional.source,
            "insert.conditional_clause_comma",
            "syntax-initial-conditional-comma/2.0",
        ),
        SourceBehavior(
            temporal.source,
            "insert.temporal_clause_comma",
            "syntax-initial-temporal-comma/2.0",
        ),
    )
