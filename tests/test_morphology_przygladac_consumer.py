from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import pytest

from polis import AnalysisOptions
from polis.core import Category
from polis.core.models import Severity
from polis.rules._morfeusz import _ProviderIdentity, _QualifiedMorfeusz
from polis.rules.przygladac import InflectionPrzygladacSieNowyBudynekRule

_NOTICE = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
_BEHAVIOR = (
    "inflection-przygladac-sie-nowy-budynek/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    f"{_NOTICE}"
)
_TEXT = "Przyglądam się nowy budynek."
type _Interp = tuple[str, str, str, list[str], list[str]]
type _ARow = tuple[int, int, _Interp]
type _GRow = tuple[str, str, str, list[str], list[str]]

_PRZYGLADAM: tuple[_ARow, ...] = (
    (0, 1, ("przyglądam", "przyglądać", "fin:sg:pri:imperf", [], [])),
)
_NOWY: tuple[_ARow, ...] = (
    (0, 1, ("nowy", "nowy:S", "subst:sg:nom:m1", ["nazwa_pospolita"], [])),
    (0, 1, ("nowy", "nowy:A", "adj:sg:acc:m3:pos", [], [])),
    (0, 1, ("nowy", "nowy:A", "adj:sg:nom.voc:m1.m2.m3:pos", [], [])),
)
_BUDYNEK: tuple[_ARow, ...] = (
    (0, 1, ("budynek", "budynek", "subst:sg:nom.acc:m3", ["nazwa_pospolita"], [])),
)
_NOWEMU: tuple[_GRow, ...] = (
    ("nowemu", "nowy:A", "adj:sg:dat:m1.m2.m3.n:pos", [], []),
)
_BUDYNKOWI: tuple[_GRow, ...] = (
    ("budynkowi", "budynek", "subst:sg:dat:m3", ["nazwa_pospolita"], []),
)


class _Backend(Protocol):
    def analyse(self, text: str) -> Sequence[_ARow]: ...
    def generate(self, lemma: str) -> Sequence[_GRow]: ...


class _QualifiedBackend:
    def __init__(
        self,
        *,
        przygladam: Sequence[_ARow] = _PRZYGLADAM,
        nowy: Sequence[_ARow] = _NOWY,
        budynek: Sequence[_ARow] = _BUDYNEK,
        nowemu: Sequence[_GRow] = _NOWEMU,
        budynkowi: Sequence[_GRow] = _BUDYNKOWI,
    ) -> None:
        self.przygladam = przygladam
        self.nowy = nowy
        self.budynek = budynek
        self.nowemu = nowemu
        self.budynkowi = budynkowi
        self.calls = 0

    def analyse(self, text: str) -> Sequence[_ARow]:
        self.calls += 1
        return {
            "przyglądam": self.przygladam,
            "nowy": self.nowy,
            "budynek": self.budynek,
        }[text]

    def generate(self, lemma: str) -> Sequence[_GRow]:
        self.calls += 1
        if lemma == "nowy:A":
            return self.nowemu
        if lemma == "budynek":
            return self.budynkowi
        raise AssertionError(lemma)


def _provider(backend: _Backend, **identity: str) -> _QualifiedMorfeusz:
    return _QualifiedMorfeusz(
        backend=backend,
        identity=_ProviderIdentity(
            package_version=identity.get("package_version", "1.99.15"),
            dictionary_id=identity.get("dictionary_id", "pl.sgjp.sgjp-2026.06.01"),
            dictionary_notice_sha256=identity.get("notice_sha256", _NOTICE),
        ),
    )


def test_emits_exact_atomic_span_review_only_finding() -> None:
    rule = InflectionPrzygladacSieNowyBudynekRule(_provider(_QualifiedBackend()))
    findings = rule.find(_TEXT, options=AnalysisOptions())
    assert len(findings) == 1
    f = findings[0]
    assert str(f.source) == "rule:inflection.przygladac_sie_nowy_budynek"
    assert f.category is Category.INFLECTION
    assert f.severity is Severity.SUGGESTION
    assert f.original == "nowy budynek"
    assert f.suggestion == "nowemu budynkowi"
    assert (f.start, f.end) == (15, 27)
    assert f.confidence.value == 0.9
    assert rule.operation == "replace.governed_nominal_group"
    assert rule.behavior_version == _BEHAVIOR


@pytest.mark.parametrize(
    "text",
    (
        "Przyglądam się nowemu budynkowi.",
        "Przyglądam się odnowie budynku.",
        "Cytat „przyglądam się nowy budynek” zapisano w notatce.",
        "Nazwa `przygladac_sie_nowy_budynek` opisuje przypadek.",
    ),
)
def test_abstains_for_close_negatives_and_mentions(text: str) -> None:
    backend = _QualifiedBackend()
    rule = InflectionPrzygladacSieNowyBudynekRule(_provider(backend))
    assert rule.find(text, options=AnalysisOptions()) == ()
    assert backend.calls == 0


def test_abstains_without_provider_and_on_category_filter() -> None:
    assert (
        InflectionPrzygladacSieNowyBudynekRule(None).find(
            _TEXT, options=AnalysisOptions()
        )
        == ()
    )
    backend = _QualifiedBackend()
    rule = InflectionPrzygladacSieNowyBudynekRule(_provider(backend))
    assert (
        rule.find(_TEXT, options=AnalysisOptions(categories={Category.SPELLING})) == ()
    )
    assert backend.calls == 0


def test_emits_repeated_and_unicode_prefix_offsets() -> None:
    rule = InflectionPrzygladacSieNowyBudynekRule(_provider(_QualifiedBackend()))
    text = "ŻANETA: PRZYGLĄDAM SIĘ NOWY BUDYNEK. Przyglądam się nowy budynek."
    findings = rule.find(text, options=AnalysisOptions())
    assert [(f.original, f.suggestion, f.start, f.end) for f in findings] == [
        ("NOWY BUDYNEK", "NOWEMU BUDYNKOWI", 23, 35),
        ("nowy budynek", "nowemu budynkowi", 52, 64),
    ]
