from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol

import pytest
from polis.rules.subject_verb import AgreementSubjectVerbOniCzytaRule

from polis import AnalysisOptions
from polis.core import Category
from polis.core.models import Severity
from polis.rules._morfeusz import _ProviderIdentity, _QualifiedMorfeusz

_NOTICE_SHA256 = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
_BEHAVIOR_VERSION = (
    "agreement-subject-verb-oni-czyta/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    f"{_NOTICE_SHA256}"
)
_TEXT = "Oni czyta książkę."
type _Interpretation = tuple[str, str, str, list[str], list[str]]
type _AnalysisRow = tuple[int, int, _Interpretation]
type _GenerationRow = tuple[str, str, str, list[str], list[str]]
type _MalformedAnalysisRow = tuple[Literal[1], Literal[2], _Interpretation]

_ONI_ANALYSES: tuple[_AnalysisRow, ...] = (
    (0, 1, ("Oni", "on:A", "adj:pl:nom.voc:m1:pos", [], ["daw."])),
    (
        0,
        1,
        ("Oni", "on:S", "ppron3:pl:nom:m1:ter:akc.nakc:praep.npraep", [], []),
    ),
)
_CZYTA_ANALYSES: tuple[_AnalysisRow, ...] = (
    (0, 1, ("czyta", "czytać", "fin:sg:ter:imperf", [], [])),
)
_CZYTAJA_FORMS: tuple[_GenerationRow, ...] = (
    ("czytam", "czytać", "fin:sg:pri:imperf", [], []),
    ("czytasz", "czytać", "fin:sg:sec:imperf", [], []),
    ("czyta", "czytać", "fin:sg:ter:imperf", [], []),
    ("czytamy", "czytać", "fin:pl:pri:imperf", [], []),
    ("czytacie", "czytać", "fin:pl:sec:imperf", [], []),
    ("czytają", "czytać", "fin:pl:ter:imperf", [], []),
)
_MALFORMED_ANALYSES: tuple[_MalformedAnalysisRow, ...] = (
    (1, 2, ("Oni", "on:S", "ppron3:pl:nom:m1:ter:akc.nakc:praep.npraep", [], [])),
)


class _SubjectVerbBackend(Protocol):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]: ...

    def generate(self, lemma: str) -> Sequence[_GenerationRow]: ...


class _QualifiedBackend:
    def __init__(
        self,
        *,
        oni_analyses: Sequence[_AnalysisRow] = _ONI_ANALYSES,
        czyta_analyses: Sequence[_AnalysisRow] = _CZYTA_ANALYSES,
        czytaja_forms: Sequence[_GenerationRow] = _CZYTAJA_FORMS,
    ) -> None:
        self.oni_analyses = oni_analyses
        self.czyta_analyses = czyta_analyses
        self.czytaja_forms = czytaja_forms
        self.calls = 0

    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        self.calls += 1
        return {"Oni": self.oni_analyses, "czyta": self.czyta_analyses}[text]

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        self.calls += 1
        assert lemma == "czytać"
        return self.czytaja_forms


class _FailingBackend(_QualifiedBackend):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        raise RuntimeError(text)


class _MalformedRowsBackend:
    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        del text
        return _MALFORMED_ANALYSES

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        del lemma
        return _CZYTAJA_FORMS


def _provider(
    backend: _SubjectVerbBackend,
    *,
    package_version: str = "1.99.15",
    dictionary_id: str = "pl.sgjp.sgjp-2026.06.01",
    notice_sha256: str = _NOTICE_SHA256,
) -> _QualifiedMorfeusz:
    return _QualifiedMorfeusz(
        backend=backend,
        identity=_ProviderIdentity(
            package_version=package_version,
            dictionary_id=dictionary_id,
            dictionary_notice_sha256=notice_sha256,
        ),
    )


def test_subject_verb_oni_czyta_emits_exact_review_only_finding() -> None:
    # Given
    rule = AgreementSubjectVerbOniCzytaRule(_provider(_QualifiedBackend()))

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert len(findings) == 1
    finding = findings[0]
    assert str(finding.source) == "rule:agreement.subject_verb_oni_czyta"
    assert finding.category is Category.AGREEMENT
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "czyta"
    assert finding.suggestion == "czytają"
    assert (finding.start, finding.end) == (4, 9)
    assert finding.confidence.value == 0.9
    assert rule.operation == "replace.subject_verb_number"
    assert rule.behavior_version == _BEHAVIOR_VERSION


@pytest.mark.parametrize(
    ("identity_field", "drifted_value"),
    (
        ("package_version", "1.99.16"),
        ("dictionary_id", "pl.sgjp.sgjp-2026.07.01"),
        ("notice_sha256", "0" * 64),
    ),
)
def test_rule_abstains_when_provider_identity_drifts(
    identity_field: str, drifted_value: str
) -> None:
    # Given
    identity = {
        "package_version": "1.99.15",
        "dictionary_id": "pl.sgjp.sgjp-2026.06.01",
        "notice_sha256": _NOTICE_SHA256,
    }
    identity[identity_field] = drifted_value
    rule = AgreementSubjectVerbOniCzytaRule(_provider(_QualifiedBackend(), **identity))

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    "backend",
    (
        _QualifiedBackend(oni_analyses=()),
        _MalformedRowsBackend(),
        _QualifiedBackend(oni_analyses=((0, 1, ("Oni", "on:S", "ign", [], [])),)),
        _QualifiedBackend(
            oni_analyses=((0, 1, ("Oni", "nieznany:S", "subst:pl:nom:m1", [], [])),)
        ),
        _QualifiedBackend(czyta_analyses=((0, 1, ("czyta", "czytać", "ign", [], [])),)),
        _QualifiedBackend(czyta_analyses=()),
        _QualifiedBackend(czytaja_forms=()),
        _FailingBackend(),
    ),
)
def test_rule_abstains_on_missing_malformed_unknown_or_failing_provider_output(
    backend: _SubjectVerbBackend,
) -> None:
    # Given
    rule = AgreementSubjectVerbOniCzytaRule(_provider(backend))

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    "backend",
    (
        _QualifiedBackend(
            oni_analyses=(
                *_ONI_ANALYSES,
                (
                    0,
                    1,
                    (
                        "Oni",
                        "on:alternate",
                        "ppron3:pl:nom:m1:ter:akc.nakc:praep.npraep",
                        [],
                        [],
                    ),
                ),
            )
        ),
        _QualifiedBackend(
            czyta_analyses=(
                *_CZYTA_ANALYSES,
                (0, 1, ("czyta", "czytać:alternate", "fin:sg:ter:imperf", [], [])),
            )
        ),
        _QualifiedBackend(
            czytaja_forms=(
                *_CZYTAJA_FORMS,
                ("czytają_alt", "czytać", "fin:pl:ter:imperf", [], []),
            )
        ),
    ),
)
def test_rule_abstains_when_subject_verb_or_generation_is_non_unique(
    backend: _SubjectVerbBackend,
) -> None:
    # Given
    rule = AgreementSubjectVerbOniCzytaRule(_provider(backend))

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    "text",
    (
        "Oni czytają książkę.",
        "On czyta książkę.",
        "One czytają książkę.",
        "Czyta książkę.",
        "Oni i one czyta książkę.",
        "Uczniowie czyta książkę.",
        "Oni czyta i pisze książkę.",
        "Oni czyta książkę!",
        "oni czyta książkę.",
    ),
)
def test_rule_abstains_for_nine_named_close_negative_sentences(text: str) -> None:
    # Given
    backend = _QualifiedBackend()
    rule = AgreementSubjectVerbOniCzytaRule(_provider(backend))

    # When
    findings = rule.find(text, options=AnalysisOptions())

    # Then
    assert findings == ()
    assert backend.calls == 0


def test_rule_excludes_category_before_calling_provider() -> None:
    # Given
    backend = _QualifiedBackend()
    rule = AgreementSubjectVerbOniCzytaRule(_provider(backend))

    # When
    findings = rule.find(
        _TEXT,
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    # Then
    assert findings == ()
    assert backend.calls == 0


def test_rule_abstains_without_provider() -> None:
    # Given
    rule = AgreementSubjectVerbOniCzytaRule(None)

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert findings == ()
