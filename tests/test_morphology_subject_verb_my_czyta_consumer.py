from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol

import pytest

from polis import AnalysisOptions
from polis.core import Category
from polis.core.models import Severity
from polis.rules._morfeusz import _ProviderIdentity, _QualifiedMorfeusz
from polis.rules.subject_verb import AgreementSubjectVerbMyCzytaRule

_NOTICE_SHA256 = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
_BEHAVIOR_VERSION = (
    "agreement-subject-verb-my-czyta/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    f"{_NOTICE_SHA256}"
)
_TEXT = "My czyta książkę."
type _Interpretation = tuple[str, str, str, list[str], list[str]]
type _AnalysisRow = tuple[int, int, _Interpretation]
type _GenerationRow = tuple[str, str, str, list[str], list[str]]
type _MalformedAnalysisRow = tuple[Literal[1], Literal[2], _Interpretation]

_MY_ANALYSES: tuple[_AnalysisRow, ...] = (
    (0, 1, ("My", "my", "ppron12:pl:voc:m1.m2.m3.f.n:pri", [], [])),
    (0, 1, ("My", "my", "ppron12:pl:nom:m1.m2.m3.f.n:pri", [], [])),
)
_CZYTA_ANALYSES: tuple[_AnalysisRow, ...] = (
    (0, 1, ("czyta", "czytać", "fin:sg:ter:imperf", [], [])),
)
_CZYTAMY_FORMS: tuple[_GenerationRow, ...] = (
    ("czytam", "czytać", "fin:sg:pri:imperf", [], []),
    ("czytasz", "czytać", "fin:sg:sec:imperf", [], []),
    ("czyta", "czytać", "fin:sg:ter:imperf", [], []),
    ("czytamy", "czytać", "fin:pl:pri:imperf", [], []),
    ("czytacie", "czytać", "fin:pl:sec:imperf", [], []),
    ("czytają", "czytać", "fin:pl:ter:imperf", [], []),
)
_MALFORMED_ANALYSES: tuple[_MalformedAnalysisRow, ...] = (
    (1, 2, ("My", "my", "ppron12:pl:nom:m1.m2.m3.f.n:pri", [], [])),
)


class _SubjectVerbBackend(Protocol):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]: ...

    def generate(self, lemma: str) -> Sequence[_GenerationRow]: ...


class _QualifiedBackend:
    def __init__(
        self,
        *,
        my_analyses: Sequence[_AnalysisRow] = _MY_ANALYSES,
        czyta_analyses: Sequence[_AnalysisRow] = _CZYTA_ANALYSES,
        czytamy_forms: Sequence[_GenerationRow] = _CZYTAMY_FORMS,
    ) -> None:
        self.my_analyses = my_analyses
        self.czyta_analyses = czyta_analyses
        self.czytamy_forms = czytamy_forms
        self.calls = 0

    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        self.calls += 1
        return {"My": self.my_analyses, "czyta": self.czyta_analyses}[text]

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        self.calls += 1
        assert lemma == "czytać"
        return self.czytamy_forms


class _FailingBackend(_QualifiedBackend):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        raise RuntimeError(text)


class _MalformedRowsBackend:
    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        del text
        return _MALFORMED_ANALYSES

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        del lemma
        return _CZYTAMY_FORMS


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


def test_subject_verb_my_czyta_emits_exact_review_only_finding() -> None:
    rule = AgreementSubjectVerbMyCzytaRule(_provider(_QualifiedBackend()))

    findings = rule.find(_TEXT, options=AnalysisOptions())

    assert len(findings) == 1
    finding = findings[0]
    assert str(finding.source) == "rule:agreement.subject_verb_my_czyta"
    assert finding.category is Category.AGREEMENT
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "czyta"
    assert finding.suggestion == "czytamy"
    assert (finding.start, finding.end) == (3, 8)
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
    identity = {
        "package_version": "1.99.15",
        "dictionary_id": "pl.sgjp.sgjp-2026.06.01",
        "notice_sha256": _NOTICE_SHA256,
    }
    identity[identity_field] = drifted_value
    rule = AgreementSubjectVerbMyCzytaRule(_provider(_QualifiedBackend(), **identity))

    assert rule.find(_TEXT, options=AnalysisOptions()) == ()


@pytest.mark.parametrize(
    "backend",
    (
        _QualifiedBackend(my_analyses=()),
        _MalformedRowsBackend(),
        _QualifiedBackend(my_analyses=((0, 1, ("My", "my", "ign", [], [])),)),
        _QualifiedBackend(
            my_analyses=((0, 1, ("My", "nieznany:S", "subst:pl:nom:m1", [], [])),)
        ),
        _QualifiedBackend(czyta_analyses=((0, 1, ("czyta", "czytać", "ign", [], [])),)),
        _QualifiedBackend(czyta_analyses=()),
        _QualifiedBackend(czytamy_forms=()),
        _FailingBackend(),
    ),
)
def test_rule_abstains_on_missing_malformed_unknown_or_failing_provider_output(
    backend: _SubjectVerbBackend,
) -> None:
    rule = AgreementSubjectVerbMyCzytaRule(_provider(backend))

    assert rule.find(_TEXT, options=AnalysisOptions()) == ()


@pytest.mark.parametrize(
    "backend",
    (
        _QualifiedBackend(
            my_analyses=(
                *_MY_ANALYSES,
                (
                    0,
                    1,
                    ("My", "my:alternate", "ppron12:pl:nom:m1.m2.m3.f.n:pri", [], []),
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
            czytamy_forms=(
                *_CZYTAMY_FORMS,
                ("czytamy_alt", "czytać", "fin:pl:pri:imperf", [], []),
            )
        ),
    ),
)
def test_rule_abstains_when_subject_verb_or_generation_is_non_unique(
    backend: _SubjectVerbBackend,
) -> None:
    rule = AgreementSubjectVerbMyCzytaRule(_provider(backend))

    assert rule.find(_TEXT, options=AnalysisOptions()) == ()


@pytest.mark.parametrize(
    "text",
    (
        "My czytamy książkę.",
        "On czyta książkę.",
        "My i wy czyta książkę.",
        "Czyta książkę.",
        "Uczniowie czyta książkę.",
        "My czyta i pisze książkę.",
        "my_czyta",
        "Cytat „My czyta książkę” jest przedmiotem rozmowy.",
        "Klucz `my_czyta` wskazuje wariant testowy.",
    ),
)
def test_rule_abstains_for_close_negatives_and_mentions(text: str) -> None:
    backend = _QualifiedBackend()
    rule = AgreementSubjectVerbMyCzytaRule(_provider(backend))

    findings = rule.find(text, options=AnalysisOptions())

    assert findings == ()
    assert backend.calls == 0


def test_rule_excludes_category_before_calling_provider() -> None:
    backend = _QualifiedBackend()
    rule = AgreementSubjectVerbMyCzytaRule(_provider(backend))

    findings = rule.find(
        _TEXT,
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    assert findings == ()
    assert backend.calls == 0


def test_rule_abstains_without_provider() -> None:
    rule = AgreementSubjectVerbMyCzytaRule(None)

    assert rule.find(_TEXT, options=AnalysisOptions()) == ()


def test_rule_emits_repeated_and_unicode_prefix_offsets() -> None:
    rule = AgreementSubjectVerbMyCzytaRule(_provider(_QualifiedBackend()))
    text = "ŁÓDŹ: MY CZYTA KSIĄŻKĘ. My czyta książkę."

    findings = rule.find(text, options=AnalysisOptions())

    assert [
        (item.original, item.suggestion, item.start, item.end) for item in findings
    ] == [
        ("CZYTA", "CZYTAMY", 9, 14),
        ("czyta", "czytamy", 27, 32),
    ]
    assert all(text[item.start : item.end] == item.original for item in findings)
