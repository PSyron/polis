from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from polis import AnalysisOptions
from polis.core import Category
from polis.rules._morfeusz import _ProviderIdentity, _QualifiedMorfeusz
from polis.rules.agreement import AgreementNominalGroupTaNowyKsiazkaRule

_NOTICE_SHA256 = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
_TEXT = "Ta czerwony książka. Ta duży książka. Czerwony książka."

type _AnalysisRow = tuple[int, int, tuple[str, str, str, list[str], list[str]]]
type _GenerationRow = tuple[str, str, str, list[str], list[str]]


def _analysis(surface: str, lemma: str, tag: str, *labels: str) -> _AnalysisRow:
    return (0, 1, (surface, lemma, tag, list(labels), []))


def _generation(form: str, lemma: str, tag: str) -> _GenerationRow:
    return (form, lemma, tag, [], [])


_ANALYSES: dict[str, tuple[_AnalysisRow, ...]] = {
    "ta": (
        _analysis("ta", "ta", "part", "reg."),
        _analysis("ta", "ten", "adj:sg:nom.voc:f:pos"),
    ),
    "to": (
        _analysis("to", "to:V", "pred"),
        _analysis("to", "to:C", "conj"),
        _analysis("to", "to:T", "part"),
        _analysis("to", "to:M", "comp"),
        _analysis("to", "ten", "adj:sg:acc:n:pos"),
        _analysis("to", "ten", "adj:sg:nom.voc:n:pos"),
        _analysis("to", "to:S", "subst:sg:nom:n:ncol", "nazwa_pospolita"),
        _analysis("to", "to:S", "subst:sg:acc:n:ncol", "nazwa_pospolita"),
    ),
    "ten": (
        _analysis("ten", "ten", "adj:sg:acc:m3:pos"),
        _analysis("ten", "ten", "adj:sg:nom.voc:m1.m2.m3:pos"),
    ),
    "czerwony": (
        _analysis("czerwony", "czerwony:S", "subst:sg:nom:m1", "nazwa_pospolita"),
        _analysis("czerwony", "czerwony:S", "subst:sg:voc:m1", "nazwa_pospolita"),
        _analysis("czerwony", "czerwony:A", "adj:sg:acc:m3:pos"),
        _analysis("czerwony", "czerwony:A", "adj:sg:nom.voc:m1.m2.m3:pos"),
    ),
    "duży": (
        _analysis("duży", "duży", "adj:sg:acc:m3:pos"),
        _analysis("duży", "duży", "adj:sg:nom.voc:m1.m2.m3:pos"),
    ),
    "nowa": (
        _analysis("nowa", "nowa", "subst:sg:nom:f", "nazwa_pospolita"),
        _analysis("nowa", "nowa", "subst:sg:voc:f", "nazwa_pospolita"),
        _analysis("nowa", "nowy:A", "adj:sg:nom.voc:f:pos"),
        _analysis("nowa", "nowy:A", "adjp:gen"),
    ),
    "książka": (_analysis("książka", "książka", "subst:sg:nom:f", "nazwa_pospolita"),),
    "okno": (
        _analysis("okno", "okno", "subst:sg:nom.acc.voc:n:ncol", "nazwa_pospolita"),
    ),
    "samochód": (
        _analysis("samochód", "samochód", "subst:sg:nom.acc:m3", "nazwa_pospolita"),
    ),
}

_FORMS: dict[str, tuple[_GenerationRow, ...]] = {
    "czerwony:A": (_generation("czerwona", "czerwony:A", "adj:sg:nom.voc:f:pos"),),
    "duży": (
        _generation("duże", "duży", "adj:sg:acc:n:pos"),
        _generation("duże", "duży", "adj:sg:nom.voc:n:pos"),
        _generation("duża", "duży", "adj:sg:nom.voc:f:pos"),
    ),
    "nowy:A": (
        _generation("nowy", "nowy:A", "adj:sg:acc:m3:pos"),
        _generation("nowy", "nowy:A", "adj:sg:nom.voc:m1.m2.m3:pos"),
    ),
}


class _Backend(Protocol):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]: ...

    def generate(self, lemma: str) -> Sequence[_GenerationRow]: ...


class _QualifiedBackend:
    def __init__(
        self,
        *,
        analyses: Mapping[str, Sequence[_AnalysisRow]] = _ANALYSES,
        forms: Mapping[str, Sequence[_GenerationRow]] = _FORMS,
    ) -> None:
        self.analyses = analyses
        self.forms = forms

    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        return tuple(
            (start, end, (text, lemma, tag, labels, qualifiers))
            for start, end, (_, lemma, tag, labels, qualifiers) in self.analyses[
                text.casefold()
            ]
        )

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        return self.forms[lemma]


def _provider(
    backend: _Backend,
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


def test_generalized_nominal_group_emits_three_unambiguous_lemma_findings() -> None:
    rule = AgreementNominalGroupTaNowyKsiazkaRule(_provider(_QualifiedBackend()))

    findings = rule.find(_TEXT, options=AnalysisOptions())

    assert [
        (finding.original, finding.suggestion, finding.start, finding.end)
        for finding in findings
    ] == [
        ("czerwony", "czerwona", 3, 11),
        ("duży", "duża", 24, 28),
        ("Czerwony", "Czerwona", 38, 46),
    ]
    assert all(finding.category is Category.AGREEMENT for finding in findings)
    assert all(
        _TEXT[finding.start : finding.end] == finding.original for finding in findings
    )


def test_generalized_nominal_group_preserves_case_repetition_and_sentence_offsets() -> (
    None
):
    text = "TA CZERWONY KSIĄŻKA. Ta DUŻY KSIĄŻKA. Ta nowa książka."
    rule = AgreementNominalGroupTaNowyKsiazkaRule(_provider(_QualifiedBackend()))

    findings = rule.find(text, options=AnalysisOptions())

    assert [
        (finding.original, finding.suggestion, finding.start, finding.end)
        for finding in findings
    ] == [
        ("CZERWONY", "CZERWONA", 3, 11),
        ("DUŻY", "DUŻA", 24, 28),
    ]
    assert all(
        text[finding.start : finding.end] == finding.original for finding in findings
    )

    mixed_case = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(_QualifiedBackend())
    ).find("Ta cZeRwOnY książka.", options=AnalysisOptions())
    assert mixed_case == ()


def test_generalized_nominal_group_abstains_for_literals_and_unsupported_shapes() -> (
    None
):
    text = (
        "Ta czerwona książka. Napisano „Ta czerwony książka”. "
        "Stała `Ta czerwony książka`. Ta czerwony i książka. "
        "Ta czerwony książka, oraz Ta czerwony książka."
    )
    rule = AgreementNominalGroupTaNowyKsiazkaRule(_provider(_QualifiedBackend()))

    assert rule.find(text, options=AnalysisOptions()) == ()


def test_generalized_nominal_group_abstains_for_single_quote_literals() -> None:
    text = (
        "Kod = 'Ta czerwony książka'. Tekst ‘Ta czerwony książka’ i "
        "‹Ta czerwony książka›."
    )
    rule = AgreementNominalGroupTaNowyKsiazkaRule(_provider(_QualifiedBackend()))

    assert rule.find(text, options=AnalysisOptions()) == ()


def test_generalized_nominal_group_does_not_cross_sentence_punctuation() -> None:
    rule = AgreementNominalGroupTaNowyKsiazkaRule(_provider(_QualifiedBackend()))

    for separator in (".", ",", ";", "!", "?", ":"):
        text = f"Ta{separator} czerwony książka."
        assert rule.find(text, options=AnalysisOptions()) == ()
    assert rule.find("Ta.\nczerwony książka.", options=AnalysisOptions()) == ()
    for prefix in ("Ta. - ", "Ta. — ", "Ta. … ", "Ta. ... ", "Ta. ("):
        assert rule.find(f"{prefix}czerwony książka.)", options=AnalysisOptions()) == ()


def test_generalized_nominal_group_abstains_without_qualified_provider() -> None:
    rule = AgreementNominalGroupTaNowyKsiazkaRule(None)

    assert rule.find(_TEXT, options=AnalysisOptions()) == ()


def test_generalized_nominal_group_abstains_when_provider_identity_drifts() -> None:
    for kwargs in (
        {"package_version": "1.99.16"},
        {"dictionary_id": "pl.sgjp.sgjp-2026.06.02"},
        {"notice_sha256": "0" * 64},
    ):
        rule = AgreementNominalGroupTaNowyKsiazkaRule(
            _provider(_QualifiedBackend(), **kwargs)
        )

        assert rule.find(_TEXT, options=AnalysisOptions()) == ()


def test_generalized_nominal_group_abstains_on_malformed_or_unknown_analysis_rows() -> (
    None
):
    malformed: _AnalysisRow = (
        1,
        2,
        ("książka", "książka", "subst:sg:nom:f", ["nazwa_pospolita"], []),
    )
    unknown: _AnalysisRow = (
        0,
        1,
        ("czerwony", "czerwony:A", "adj:sg:nom.unknown:f:pos", [], []),
    )

    malformed_analyses = {**_ANALYSES, "książka": (malformed,)}
    unknown_analyses = {**_ANALYSES, "czerwony": (unknown,)}
    malformed_findings = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(_QualifiedBackend(analyses=malformed_analyses))
    ).find(_TEXT, options=AnalysisOptions())
    unknown_findings = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(_QualifiedBackend(analyses=unknown_analyses))
    ).find(_TEXT, options=AnalysisOptions())
    assert all(finding.original != "czerwony" for finding in malformed_findings)
    assert all(finding.original != "czerwony" for finding in unknown_findings)


def test_generalized_nominal_group_abstains_on_ambiguous_lemmas_and_forms() -> None:
    alternate_lemma: _AnalysisRow = (
        0,
        1,
        ("czerwony", "czerwień:A", "adj:sg:acc:m3:pos", [], []),
    )
    alternate_form = _generation("czerwonka", "czerwony:A", "adj:sg:nom.voc:f:pos")
    ambiguous_analyses = {
        **_ANALYSES,
        "czerwony": (*_ANALYSES["czerwony"], alternate_lemma),
    }
    ambiguous_forms = {
        **_FORMS,
        "czerwony:A": (*_FORMS["czerwony:A"], alternate_form),
    }
    ambiguous_lemma_findings = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(_QualifiedBackend(analyses=ambiguous_analyses))
    ).find(_TEXT, options=AnalysisOptions())
    ambiguous_form_findings = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(_QualifiedBackend(forms=ambiguous_forms))
    ).find(_TEXT, options=AnalysisOptions())
    assert all(finding.original != "czerwony" for finding in ambiguous_lemma_findings)
    assert all(finding.original != "czerwony" for finding in ambiguous_form_findings)


def test_generalized_nominal_group_abstains_on_unknown_analysis_tag() -> None:
    unknown_tag: _AnalysisRow = (
        0,
        1,
        ("czerwony", "czerwony:A", "mystery:sg:nom:f", [], []),
    )
    analyses = {**_ANALYSES, "czerwony": (*_ANALYSES["czerwony"], unknown_tag)}

    findings = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(_QualifiedBackend(analyses=analyses))
    ).find(_TEXT, options=AnalysisOptions())

    assert all(finding.original != "czerwony" for finding in findings)


def test_generalized_nominal_group_abstains_on_malformed_provider_boundaries() -> None:
    empty_lemma: _AnalysisRow = (
        0,
        1,
        ("czerwony", "", "adj:sg:nom.voc:m1.m2.m3:pos", [], []),
    )
    boolean_offset: _AnalysisRow = (
        True,
        1,
        ("czerwony", "czerwony:A", "adj:sg:nom.voc:m1.m2.m3:pos", [], []),
    )
    unknown_noun_suffix: _AnalysisRow = (
        0,
        1,
        ("książka", "książka", "subst:sg:nom:f:unknown", ["nazwa_pospolita"], []),
    )

    for analyses in (
        {**_ANALYSES, "czerwony": (empty_lemma,)},
        {**_ANALYSES, "czerwony": (boolean_offset,)},
        {**_ANALYSES, "książka": (unknown_noun_suffix,)},
    ):
        findings = AgreementNominalGroupTaNowyKsiazkaRule(
            _provider(_QualifiedBackend(analyses=analyses))
        ).find("Czerwony książka.", options=AnalysisOptions())
        assert findings == ()


def test_generalized_nominal_group_abstains_on_ambiguous_case_without_context() -> None:
    analyses = {
        **_ANALYSES,
        "książka": (
            _analysis(
                "książka",
                "książka",
                "subst:sg:nom.voc:f",
                "nazwa_pospolita",
            ),
        ),
    }

    findings = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(_QualifiedBackend(analyses=analyses))
    ).find("Czerwony książka.", options=AnalysisOptions())

    assert findings == ()


def test_generalized_nominal_group_abstains_on_ambiguous_case_with_demonstrative() -> (
    None
):
    findings = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(_QualifiedBackend())
    ).find("To duży okno.", options=AnalysisOptions())

    assert findings == ()


def test_generalized_nominal_group_abstains_on_generated_row_drift() -> None:
    empty_form: _GenerationRow = ("", "czerwony:A", "adj:sg:nom.voc:f:pos", [], [])
    malformed_form: _GenerationRow = ("czerwona", "czerwony:A", "adj:sg:f:pos", [], [])
    unknown_form: _GenerationRow = (
        "czerwona",
        "czerwony:A",
        "mystery:sg:nom:f",
        [],
        [],
    )
    empty_findings = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(
            _QualifiedBackend(
                forms={**_FORMS, "czerwony:A": (empty_form,)},
            )
        )
    ).find(_TEXT, options=AnalysisOptions())
    malformed_findings = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(
            _QualifiedBackend(
                forms={**_FORMS, "czerwony:A": (malformed_form,)},
            )
        )
    ).find(_TEXT, options=AnalysisOptions())
    unknown_findings = AgreementNominalGroupTaNowyKsiazkaRule(
        _provider(
            _QualifiedBackend(
                forms={**_FORMS, "czerwony:A": (unknown_form,)},
            )
        )
    ).find(_TEXT, options=AnalysisOptions())

    assert all(finding.original != "czerwony" for finding in empty_findings)
    assert all(finding.original != "czerwony" for finding in malformed_findings)
    assert all(finding.original != "czerwony" for finding in unknown_findings)
