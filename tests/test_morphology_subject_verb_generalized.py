from __future__ import annotations

from collections.abc import Sequence

import pytest

import polis.analyzer as analyzer_module
from polis import Analyzer, AnalyzerConfig, Finding
from polis.core import Category
from polis.core.models import Severity
from polis.rules import (
    AgreementSubjectVerbPresentRule,
    DeterministicRuleRegistry,
    RuleRegistration,
)
from polis.rules._morfeusz import (
    _AnalysisRow,
    _GenerationRow,
    _load_qualified_morfeusz,
    _ProviderIdentity,
    _QualifiedMorfeusz,
    _QualifiedMorfeuszBackend,
)
from polis.rules.subject_verb import present_replacement

_SOURCE = "rule:agreement.subject_verb_present"
_BEHAVIOR_VERSION = (
    "agreement-subject-verb-present/1.8+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)

_POSITIVES = (
    ("Ja pracuje codziennie.", ("pracuje", "pracuję", 3, 10)),
    ("TY PISZĘ KSIĄŻKĘ.", ("PISZĘ", "PISZESZ", 3, 8)),
    ("On robią obiad.", ("robią", "robi", 3, 8)),
    ("Ona piszą list.", ("piszą", "pisze", 4, 9)),
    ("Ono pracują.", ("pracują", "pracuje", 4, 11)),
    ("My pracuje codziennie.", ("pracuje", "pracujemy", 3, 10)),
    ("Wy robią zadanie.", ("robią", "robicie", 3, 8)),
    ("Oni piszę list.", ("piszę", "piszą", 4, 9)),
    ("Oni czyta książkę!", ("czyta", "czytają", 4, 9)),
    ("Oni mieszka w Warszawie.", ("mieszka", "mieszkają", 4, 11)),
    ("One robię.", ("robię", "robią", 4, 9)),
    ("My, nie pracuje.", ("pracuje", "pracujemy", 8, 15)),
    ("Ja nie pracują.", ("pracują", "pracuję", 7, 14)),
)

_REPEATED = "Ona piszą. Ona piszą."

_HARD_NEGATIVES = (
    "Ja pracuję codziennie.",
    "Ty piszesz książkę.",
    "On robi obiad.",
    "Ona pisze list.",
    "Ono pracuje.",
    "My pracujemy codziennie.",
    "Wy robicie zadanie.",
    "Oni piszą list.",
    "One robią.",
    "Pracuje codziennie.",
    "My i ty pracuje.",
    "Dzieci pracuje codziennie.",
    "Ja pracowałem wczoraj.",
    "Ja pracowałbym wczoraj.",
    "Ty pracuj natychmiast.",
    "Napisano „Ja pracuje codziennie.”",
    "Napisano `Oni piszę list.`",
    "Oni mieszka.",
    "Oni lubi.",
    "My lubi.",
    "Oni lubi kawę.",
    "On mieszka w Warszawie.",
    "On lubi kawę.",
    "On pracuje i pisze list.",
    "On pracuje, a Ona piszą.",
    "On pracuje, ale Ona piszą.",
    "On pracuje, lecz Ona piszą.",
    "On pracuje, natomiast Ona piszą.",
    "On pracuje; Ona piszą.",
)


def _source_findings(text: str) -> tuple[Finding, ...]:
    analyzer = Analyzer(AnalyzerConfig())
    return tuple(
        finding
        for finding in analyzer.analyze(text).issues
        if str(finding.source) == _SOURCE
    )


def test_public_subject_verb_evidence_has_exact_positive_delta() -> None:
    observed: list[tuple[str, str, str, int, int]] = []

    for text, expected in _POSITIVES:
        findings = _source_findings(text)
        assert len(findings) == 1
        finding = findings[0]
        assert text[finding.start : finding.end] == finding.original
        actual = (
            finding.original,
            finding.suggestion,
            finding.start,
            finding.end,
        )
        assert actual == expected
        observed.append((text, *actual))

    repeated = _source_findings(_REPEATED)
    assert len(repeated) == 2
    assert [(finding.start, finding.end) for finding in repeated] == [
        (4, 9),
        (15, 20),
    ]
    assert len(observed) == 13


def test_public_subject_verb_evidence_has_zero_hard_negative_false_alarms() -> None:
    false_alarms = {text: _source_findings(text) for text in _HARD_NEGATIVES}

    assert len(_HARD_NEGATIVES) >= 16
    assert all(not findings for findings in false_alarms.values())


@pytest.mark.parametrize("text", ("Oni czyta książkę?", "Oni czyta książkę dziś."))
def test_generalized_rule_does_not_hide_extended_legacy_phrases(
    text: str,
) -> None:
    findings = _source_findings(text)

    assert len(findings) == 1
    assert findings[0].original == "czyta"
    assert findings[0].suggestion == "czytają"
    assert (findings[0].start, findings[0].end) == (4, 9)


def test_decomposed_unicode_token_abstains() -> None:
    assert not _source_findings("Ja pracuje\u0328.")


@pytest.mark.parametrize("text", ("Ona pISZĄ.", "OnI pracuje.", "oNI pracuje."))
def test_mixed_case_tokens_abstain(text: str) -> None:
    assert not _source_findings(text)


def test_finding_metadata_and_explicit_apply_are_exact() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    finding = _source_findings("Ja pracuje.")[0]

    behavior = next(
        item for item in analyzer.source_identity_snapshot if item.source == _SOURCE
    )
    correction = analyzer.correct("Ja pracuje.")

    assert finding.category is Category.AGREEMENT
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "pracuje"
    assert finding.suggestion == "pracuję"
    assert (finding.start, finding.end) == (3, 10)
    assert finding.confidence.value == 0.9
    assert behavior.operation == "replace.subject_verb_person_number"
    assert behavior.behavior_version == _BEHAVIOR_VERSION
    assert correction.applied_findings == ()
    assert correction.skipped_findings == (finding,)
    assert correction.apply_suggestions((finding.id,)) == "Ja pracuję."


def test_public_analyzer_handles_byc_auxiliary_generation_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    qualified = _load_qualified_morfeusz()
    assert qualified is not None
    assert (
        present_replacement(
            qualified,
            subject="Ja",
            verb="jest",
            continuation=" w domu.",
        )
        == "jestem"
    )
    default_issues = Analyzer(AnalyzerConfig()).analyze("Ja jest w domu.").issues
    assert [
        (str(issue.source), issue.original, issue.suggestion, issue.start, issue.end)
        for issue in default_issues
    ] == [("rule:agreement.copula_ja", "jest", "jestem", 3, 7)]
    monkeypatch.setattr(
        analyzer_module,
        "_make_default_registry",
        lambda _morphology: DeterministicRuleRegistry(
            (RuleRegistration(rule=AgreementSubjectVerbPresentRule(qualified)),)
        ),
    )

    issues = Analyzer(AnalyzerConfig()).analyze("Ty jesteśmy w domu.").issues

    assert len(issues) == 1
    finding = issues[0]
    assert str(finding.source) == _SOURCE
    assert (finding.original, finding.suggestion) == ("jesteśmy", "jesteś")
    assert (finding.start, finding.end) == (3, 11)


class _FaultBackend:
    def __init__(self, backend: _QualifiedMorfeuszBackend, fault: str) -> None:
        self._backend = backend
        self._fault = fault

    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        if self._fault == "analysis" and text == "Ja":
            return ((0, 1, ("Ja", "", "", [], [])),)
        rows = tuple(self._backend.analyse(text))
        if self._fault == "unknown_analysis" and text == "pracuje":
            return (*rows, (0, 1, (text, "pracować", "ign:unknown", [], [])))
        return rows

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        if self._fault == "generation":
            return (("", lemma, "fin:sg:pri:imperf", [], []),)
        rows = tuple(self._backend.generate(lemma))
        if self._fault == "unknown_generation":
            return (*rows, ("nieznana", lemma, "ign:unknown", [], []))
        return rows


@pytest.mark.parametrize(
    "fault",
    ("identity", "analysis", "generation", "unknown_analysis", "unknown_generation"),
)
def test_provider_identity_and_row_or_form_drift_abstain(
    monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    qualified = _load_qualified_morfeusz()
    assert qualified is not None
    if fault == "identity":
        identity = _ProviderIdentity(
            "drifted",
            qualified.identity.dictionary_id,
            qualified.identity.dictionary_notice_sha256,
        )
        provider = _QualifiedMorfeusz(qualified.backend, identity)
    else:
        provider = _QualifiedMorfeusz(
            _FaultBackend(qualified.backend, fault), qualified.identity
        )
    monkeypatch.setattr(analyzer_module, "_load_qualified_morfeusz", lambda: provider)

    assert _source_findings("Ja pracuje.") == ()


class _MalformedKnownTagBackend:
    def __init__(self, backend: _QualifiedMorfeuszBackend, *, tag: str) -> None:
        self._backend = backend
        self._tag = tag

    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        rows = tuple(self._backend.analyse(text))
        if text == "mieszka":
            return (*rows, (0, 1, (text, "mieszkać", self._tag, [], [])))
        return rows

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        rows = tuple(self._backend.generate(lemma))
        return (*rows, ("nieznana", lemma, self._tag, [], []))


@pytest.mark.parametrize(
    "tag",
    (
        "subst",
        "subst:broken",
        "fin",
        "adv:malformed",
        "ger:malformed",
        "ger:broken",
        "pact:broken",
        "impt:broken",
        "aglt:broken",
        "bedzie:broken",
    ),
)
def test_malformed_known_provider_tags_abstain(
    monkeypatch: pytest.MonkeyPatch, tag: str
) -> None:
    qualified = _load_qualified_morfeusz()
    assert qualified is not None
    provider = _QualifiedMorfeusz(
        _MalformedKnownTagBackend(qualified.backend, tag=tag), qualified.identity
    )
    monkeypatch.setattr(analyzer_module, "_load_qualified_morfeusz", lambda: provider)

    assert _source_findings("Oni mieszka w Warszawie.") == ()


def test_missing_provider_abstains_without_changing_default_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(analyzer_module, "_load_qualified_morfeusz", lambda: None)

    assert _source_findings("Ja pracuje.") == ()
