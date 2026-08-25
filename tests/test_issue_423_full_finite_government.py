from __future__ import annotations

from collections.abc import Sequence

import pytest

from polis import AnalysisOptions, Analyzer, AnalyzerConfig
from polis.rules._morfeusz import _ProviderIdentity, _QualifiedMorfeusz
from polis.rules.government import _GENERALIZED_SPECS, _GeneralizedGovernmentRule

type _AnalysisRow = tuple[int, int, tuple[str, str, str, list[str], list[str]]]
type _GenerationRow = tuple[str, str, str, list[str], list[str]]


_CASES = (
    ("rule:inflection.government_szukac_klucz", "Szukam telefon.", "telefonu"),
    ("rule:inflection.government_szukac_klucz", "Szukamy telefon.", "telefonu"),
    ("rule:inflection.government_szukac_klucz", "Szuka telefon.", "telefonu"),
    ("rule:inflection.government_szukac_klucz", "Szukają telefon.", "telefonu"),
    ("rule:inflection.government_szukac_klucz", "Szukali telefon.", "telefonu"),
    ("rule:inflection.government_uzywac_telefon", "Używam telefon.", "telefonu"),
    ("rule:inflection.government_uzywac_telefon", "Używamy telefon.", "telefonu"),
    ("rule:inflection.government_uzywac_telefon", "Używa telefon.", "telefonu"),
    ("rule:inflection.government_uzywac_telefon", "Używają telefon.", "telefonu"),
    ("rule:inflection.government_uzywac_telefon", "Używali telefon.", "telefonu"),
    ("rule:inflection.government_ufac_lekarz", "Ufam lekarz.", "lekarzowi"),
    ("rule:inflection.government_ufac_lekarz", "Ufamy lekarz.", "lekarzowi"),
    ("rule:inflection.government_ufac_lekarz", "Ufa lekarz.", "lekarzowi"),
    ("rule:inflection.government_ufac_lekarz", "Ufają lekarz.", "lekarzowi"),
    ("rule:inflection.government_ufac_lekarz", "Ufali lekarz.", "lekarzowi"),
    (
        "rule:inflection.government_interesowac_sie_historia",
        "Interesuję się historia.",
        "historią",
    ),
    (
        "rule:inflection.government_interesowac_sie_historia",
        "Interesujemy się historia.",
        "historią",
    ),
    (
        "rule:inflection.government_interesowac_sie_historia",
        "Interesuje się historia.",
        "historią",
    ),
    (
        "rule:inflection.government_interesowac_sie_historia",
        "Interesują się historia.",
        "historią",
    ),
    (
        "rule:inflection.government_interesowac_sie_historia",
        "Interesowali się historia.",
        "historią",
    ),
)


@pytest.mark.parametrize(("source", "text", "suggestion"), _CASES)
def test_full_finite_government_paradigm_emits_the_same_suggestion(
    source: str, text: str, suggestion: str
) -> None:
    findings = [
        finding
        for finding in Analyzer(AnalyzerConfig()).analyze(text).issues
        if str(finding.source) == source
    ]

    assert len(findings) == 1
    assert findings[0].suggestion == suggestion


def test_preposition_do_keeps_the_existing_parity() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    singular = analyzer.analyze("Idę do sklep.").issues
    plural = analyzer.analyze("Idziemy do sklep.").issues

    assert [
        (str(item.source), item.original, item.suggestion, item.start, item.end)
        for item in singular
        if str(item.source) == "rule:inflection.government_do_sklep"
    ] == [("rule:inflection.government_do_sklep", "sklep", "sklepu", 7, 12)]
    assert [
        (str(item.source), item.original, item.suggestion, item.start, item.end)
        for item in plural
        if str(item.source) == "rule:inflection.government_do_sklep"
    ] == [("rule:inflection.government_do_sklep", "sklep", "sklepu", 11, 16)]


class _WrongLemmaBackend:
    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        if text.casefold() == "szukamy":
            return [(0, 1, (text, "inny_leksem", "fin:pl:pri:imperf", [], []))]
        if text == "telefon":
            return [
                (
                    0,
                    1,
                    (text, "telefon", "subst:sg:nom.acc:m3", ["nazwa_pospolita"], []),
                )
            ]
        raise AssertionError(text)

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        assert lemma == "telefon"
        return [
            (
                "telefonu",
                "telefon",
                "subst:sg:gen:m3",
                ["nazwa_pospolita"],
                [],
            )
        ]


def test_surface_match_with_another_lemma_abstains() -> None:
    provider = _QualifiedMorfeusz(
        backend=_WrongLemmaBackend(),
        identity=_ProviderIdentity(
            package_version="1.99.15",
            dictionary_id="pl.sgjp.sgjp-2026.06.01",
            dictionary_notice_sha256=(
                "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
            ),
        ),
    )
    rule = _GeneralizedGovernmentRule(provider, _GENERALIZED_SPECS[0])

    assert rule.find("Szukamy telefon.", options=AnalysisOptions()) == ()


@pytest.mark.parametrize(
    "text",
    (
        "Szukający telefon.",
        "Szukanie telefon.",
        "Szukaj telefon.",
    ),
)
def test_non_finite_government_forms_abstain(text: str) -> None:
    assert not any(
        str(item.source) == "rule:inflection.government_szukac_klucz"
        for item in Analyzer(AnalyzerConfig()).analyze(text).issues
    )
