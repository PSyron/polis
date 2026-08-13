from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol

import pytest

from polis import AnalysisOptions
from polis.core import Category
from polis.core.models import Severity
from polis.rules._morfeusz import _ProviderIdentity, _QualifiedMorfeusz
from polis.rules.agreement import AgreementNominalGroupTaNowyKsiazkaRule

_NOTICE_SHA256 = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
_BEHAVIOR_VERSION = (
    "agreement-nominal-group-ta-nowy-ksiazka/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    f"{_NOTICE_SHA256}"
)
_TEXT = "Ta nowy książka."
type _Interpretation = tuple[str, str, str, list[str], list[str]]
type _AnalysisRow = tuple[int, int, _Interpretation]
type _GenerationRow = tuple[str, str, str, list[str], list[str]]
type _MalformedAnalysisRow = tuple[Literal[1], Literal[2], _Interpretation]

_TA_ANALYSES: tuple[_AnalysisRow, ...] = (
    (0, 1, ("Ta", "ta", "part", [], ["reg."])),
    (0, 1, ("Ta", "ten", "adj:sg:nom.voc:f:pos", [], [])),
)
_NOWY_ANALYSES: tuple[_AnalysisRow, ...] = (
    (0, 1, ("nowy", "nowy:S", "subst:sg:nom:m1", ["nazwa_pospolita"], [])),
    (0, 1, ("nowy", "nowy:S", "subst:sg:voc:m1", ["nazwa_pospolita"], [])),
    (0, 1, ("nowy", "nowy:A", "adj:sg:acc:m3:pos", [], [])),
    (0, 1, ("nowy", "nowy:A", "adj:sg:nom.voc:m1.m2.m3:pos", [], [])),
)
_KSIAZKA_ANALYSES: tuple[_AnalysisRow, ...] = (
    (0, 1, ("książka", "książka", "subst:sg:nom:f", ["nazwa_pospolita"], [])),
)
_NOWA_FORMS: tuple[_GenerationRow, ...] = (
    ("nową", "nowy:A", "adj:sg:acc:f:pos", [], []),
    ("nowej", "nowy:A", "adj:sg:dat:f:pos", [], []),
    ("nowej", "nowy:A", "adj:sg:gen:f:pos", [], []),
    ("nową", "nowy:A", "adj:sg:inst:f:pos", [], []),
    ("nowej", "nowy:A", "adj:sg:loc:f:pos", [], []),
    ("nowa", "nowy:A", "adj:sg:nom.voc:f:pos", [], []),
    ("nowy", "nowy:A", "adj:sg:nom.voc:m1.m2.m3:pos", [], []),
    ("nowe", "nowy:A", "adj:sg:nom.voc:n:pos", [], []),
)
_MALFORMED_ANALYSES: tuple[_MalformedAnalysisRow, ...] = (
    (1, 2, ("nowy", "nowy:A", "adj:sg:nom.voc:m1.m2.m3:pos", [], [])),
)


class _AgreementBackend(Protocol):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]: ...

    def generate(self, lemma: str) -> Sequence[_GenerationRow]: ...


class _QualifiedBackend:
    def __init__(
        self,
        *,
        ta_analyses: Sequence[_AnalysisRow] = _TA_ANALYSES,
        nowy_analyses: Sequence[_AnalysisRow] = _NOWY_ANALYSES,
        ksiazka_analyses: Sequence[_AnalysisRow] = _KSIAZKA_ANALYSES,
        nowa_forms: Sequence[_GenerationRow] = _NOWA_FORMS,
    ) -> None:
        self.ta_analyses = ta_analyses
        self.nowy_analyses = nowy_analyses
        self.ksiazka_analyses = ksiazka_analyses
        self.nowa_forms = nowa_forms
        self.calls = 0

    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        self.calls += 1
        return {
            "Ta": self.ta_analyses,
            "nowy": self.nowy_analyses,
            "książka": self.ksiazka_analyses,
        }[text]

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        self.calls += 1
        assert lemma == "nowy:A"
        return self.nowa_forms


class _FailingBackend(_QualifiedBackend):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        raise RuntimeError(text)


class _MalformedRowsBackend:
    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        del text
        return _MALFORMED_ANALYSES

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        del lemma
        return _NOWA_FORMS


def _provider(
    backend: _AgreementBackend,
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


def test_nominal_group_ta_nowy_ksiazka_emits_exact_review_only_finding() -> None:
    # Given
    rule = AgreementNominalGroupTaNowyKsiazkaRule(_provider(_QualifiedBackend()))

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert len(findings) == 1
    finding = findings[0]
    assert str(finding.source) == "rule:agreement.nominal_group_ta_nowy_ksiazka"
    assert finding.category is Category.AGREEMENT
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "nowy"
    assert finding.suggestion == "nowa"
    assert (finding.start, finding.end) == (3, 7)
    assert finding.confidence.value == 0.9
    assert rule.operation == "replace.adjective_gender"
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
    rule = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(_QualifiedBackend(), **identity)
    )

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    "backend",
    (
        _QualifiedBackend(ta_analyses=()),
        _MalformedRowsBackend(),
        _QualifiedBackend(nowy_analyses=((0, 1, ("nowy", "nowy:A", "ign", [], [])),)),
        _QualifiedBackend(
            nowy_analyses=(
                (0, 1, ("nowy", "nowy:A", "adj:sg:nom.voc:m1.m2.m3:pos", [], [])),
            )
        ),
        _QualifiedBackend(
            ksiazka_analyses=((0, 1, ("książka", "książka", "subst:pl:nom:f", [], [])),)
        ),
        _QualifiedBackend(nowa_forms=()),
        _QualifiedBackend(
            nowa_forms=(
                *_NOWA_FORMS,
                ("nowa-alt", "nowy:A", "adj:sg:nom.voc:f:pos", [], []),
            )
        ),
        _FailingBackend(),
    ),
)
def test_rule_abstains_on_malformed_unknown_or_non_unique_provider_output(
    backend: _AgreementBackend,
) -> None:
    # Given
    rule = AgreementNominalGroupTaNowyKsiazkaRule(_provider(backend))

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert findings == ()


def test_rule_abstains_when_a_selected_lemma_is_ambiguous() -> None:
    # Given
    alternate: _AnalysisRow = (
        0,
        1,
        ("nowy", "nowiutki:A", "adj:sg:nom.voc:m1.m2.m3:pos", [], []),
    )
    rule = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(_QualifiedBackend(nowy_analyses=(*_NOWY_ANALYSES, alternate)))
    )

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    "text",
    (
        "Ta nowa książka.",
        "Te nowy książka.",
        "Ta nowe książka.",
        "Ta nowego książka.",
        "Ta nowy książki.",
        "Ta stary książka.",
        "Ta nowy zeszyt.",
        "Napis „Ta nowy książka” omawiamy na zajęciach.",
        "Stała `ta_nowy_ksiazka` jest identyfikatorem testu.",
        "Termin „odnowy” nie tworzy grupy nominalnej z książką.",
    ),
)
def test_rule_abstains_for_close_negative_sentences(text: str) -> None:
    # Given
    backend = _QualifiedBackend()
    rule = AgreementNominalGroupTaNowyKsiazkaRule(_provider(backend))

    # When
    findings = rule.find(text, options=AnalysisOptions())

    # Then
    assert findings == ()


def test_rule_excludes_category_before_calling_provider() -> None:
    # Given
    backend = _QualifiedBackend()
    rule = AgreementNominalGroupTaNowyKsiazkaRule(_provider(backend))

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
    rule = AgreementNominalGroupTaNowyKsiazkaRule(None)

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert findings == ()


def test_rule_emits_repeated_and_unicode_prefix_offsets() -> None:
    # Given
    rule = AgreementNominalGroupTaNowyKsiazkaRule(_provider(_QualifiedBackend()))
    text = "ŻÓŁĆ: TA NOWY KSIĄŻKA LEŻY. Ta nowy książka leży."

    # When
    findings = rule.find(text, options=AnalysisOptions())

    # Then
    assert [
        (item.original, item.suggestion, item.start, item.end) for item in findings
    ] == [
        ("NOWY", "NOWA", 9, 13),
        ("nowy", "nowa", 31, 35),
    ]
    assert all(text[item.start : item.end] == item.original for item in findings)
