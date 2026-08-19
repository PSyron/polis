from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final

import pytest

from polis import Analyzer, AnalyzerConfig
from polis.core import AnalysisOptions
from polis.rules._morfeusz import (
    _AnalysisRow,
    _CanonicalMorfeuszBackend,
    _GenerationRow,
    _load_qualified_morfeusz,
    _ProviderIdentity,
    _QualifiedMorfeusz,
)
from polis.rules.government import (
    InflectionGovernmentPotrzebowacPomocRule,
    InflectionGovernmentSzukacKluczRule,
)

_CASES = (
    (
        "Szukam samochód.",
        "rule:inflection.government_szukac_klucz",
        "samochód",
        "samochodu",
        7,
        15,
    ),
    (
        "szukam bilet.",
        "rule:inflection.government_szukac_klucz",
        "bilet",
        "biletu",
        7,
        12,
    ),
    (
        "Używam nowy telefon.",
        "rule:inflection.government_uzywac_telefon",
        "nowy telefon",
        "nowego telefonu",
        7,
        19,
    ),
    (
        "Ufam nowy lekarz.",
        "rule:inflection.government_ufac_lekarz",
        "nowy lekarz",
        "nowemu lekarzowi",
        5,
        16,
    ),
    (
        "Interesuję się polska historia.",
        "rule:inflection.government_interesowac_sie_historia",
        "polska historia",
        "polską historią",
        15,
        30,
    ),
    (
        "Idę do duży sklep.",
        "rule:inflection.government_do_sklep",
        "duży sklep",
        "dużego sklepu",
        7,
        17,
    ),
)

_GENERALIZED_SOURCES: Final = frozenset(
    {
        "rule:inflection.government_szukac_klucz",
        "rule:inflection.government_uzywac_telefon",
        "rule:inflection.government_ufac_lekarz",
        "rule:inflection.government_interesowac_sie_historia",
        "rule:inflection.government_do_sklep",
    }
)

_PUBLIC_POSITIVES = (
    "Szukam samochód.",
    "szukam bilet.",
    "SZUKAM SAMOCHÓD.",
    "Używam nowy telefon.",
    "Używam stary telefon.",
    "Ufam nowy lekarz.",
    "Interesuję się polska historia.",
    "Idę do duży sklep.",
)

_PUBLIC_HARD_NEGATIVES = (
    "Szukam samochodu.",
    "Używam nowego telefonu.",
    "Ufam nowemu lekarzowi.",
    "Interesuję się polską historią.",
    "Idę do dużego sklepu.",
    "Szukam samochód, bilet.",
    "Szukam klucz, bilet.",
    "Szukam klucz, oraz bilet.",
    "Szukam samochód i Ufam lekarz.",
    "Napisano „Szukam samochód.”",
    "Napisano `Szukam samochód.`",
    "Napisano „Idę do duży sklep.”",
    "Szukam Warszawa.",
    "Interesuję polska historia.",
    "Ufam się nowy lekarz.",
    "Szukam ten samochód.",
    "Szukam samochód.txt",
    "Ufam lekarz oraz pielęgniarka.",
    "Ufam lekarzu.",
    "Szukam samochód...",
    "Używam nowy telefon...",
    "Ufam nowy lekarz...",
    "Interesuję się polska historia...",
    "Idę do duży sklep...",
    "Szukam samochód…",
    "Pierwsze zdanie. Ufam nowemu lekarzowi.",
    "Używam nowy.",
    "Używam nowa telefon.",
    "Szukam samochód?!",
    "Szukam samochód i znowu szukam samochód.",
    "Szukam samochód i znów szukam samochód.",
)

_NOTICE = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"


class _GovernmentBackend:
    def __init__(
        self,
        *,
        analyses: Mapping[str, Sequence[_AnalysisRow]] | None = None,
        generated: Mapping[str, Sequence[_GenerationRow]] | None = None,
    ) -> None:
        self.analyses = analyses or {
            "Szukam": ((0, 1, ("Szukam", "szukać", "fin:sg:pri:imperf", [], [])),),
            "samochód": (
                (
                    0,
                    1,
                    (
                        "samochód",
                        "samochód",
                        "subst:sg:nom.acc:m3",
                        ["nazwa_pospolita"],
                        [],
                    ),
                ),
            ),
        }
        self.generated = generated or {
            "samochód": (
                (
                    "samochodu",
                    "samochód",
                    "subst:sg:gen:m3",
                    ["nazwa_pospolita"],
                    [],
                ),
            )
        }

    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        return self.analyses[text]

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        return self.generated[lemma]


def _provider(backend: _GovernmentBackend) -> _QualifiedMorfeusz:
    return _QualifiedMorfeusz(
        backend=backend,
        identity=_ProviderIdentity(
            package_version="1.99.15",
            dictionary_id="pl.sgjp.sgjp-2026.06.01",
            dictionary_notice_sha256=_NOTICE,
        ),
    )


def test_generalized_government_finds_new_complement_lemmas_exactly() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    for text, source, original, suggestion, start, end in _CASES:
        findings = tuple(
            finding
            for finding in analyzer.analyze(text).issues
            if str(finding.source) == source
        )

        assert len(findings) == 1
        finding = findings[0]
        assert (finding.original, finding.suggestion) == (original, suggestion)
        assert (finding.start, finding.end) == (start, end)
        assert text[start:end] == original


def test_generalized_government_remains_review_only_until_explicit_apply() -> None:
    text = "Ufam nowy lekarz."
    analyzer = Analyzer(AnalyzerConfig())

    finding = analyzer.analyze(text).issues[0]
    correction = analyzer.correct(text)

    assert correction.corrected_text == text
    assert correction.applied_findings == ()
    assert correction.skipped_findings == (finding,)
    assert correction.apply_suggestions((finding.id,)) == "Ufam nowemu lekarzowi."


def test_generalized_government_handles_repetition_and_sentences() -> None:
    text = "Szukam samochód. Używam nowy telefon. Szukam samochód."
    analyzer = Analyzer(AnalyzerConfig())

    findings = tuple(
        finding
        for finding in analyzer.analyze(text).issues
        if "government_" in str(finding.source)
    )

    assert [
        (
            str(finding.source),
            finding.original,
            finding.suggestion,
            finding.start,
            finding.end,
        )
        for finding in findings
    ] == [
        (
            "rule:inflection.government_szukac_klucz",
            "samochód",
            "samochodu",
            7,
            15,
        ),
        (
            "rule:inflection.government_uzywac_telefon",
            "nowy telefon",
            "nowego telefonu",
            24,
            36,
        ),
        (
            "rule:inflection.government_szukac_klucz",
            "samochód",
            "samochodu",
            45,
            53,
        ),
    ]


def test_legacy_literal_government_keeps_nonterminal_surface_compatibility() -> None:
    findings = tuple(
        finding
        for finding in Analyzer(AnalyzerConfig()).analyze("Szukam klucz, teraz.").issues
        if str(finding.source) == "rule:inflection.government_szukac_klucz"
    )

    assert len(findings) == 1
    assert (
        findings[0].original,
        findings[0].suggestion,
        findings[0].start,
        findings[0].end,
    ) == ("klucz", "klucza", 7, 12)


def test_generalized_government_preserves_casing_and_minimal_spans() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    cases = (
        ("SZUKAM SAMOCHÓD.", "SAMOCHÓD", "SAMOCHODU", 7, 15),
        ("Ufam Nowy lekarz.", "Nowy lekarz", "Nowemu lekarzowi", 5, 16),
    )
    for text, original, suggestion, start, end in cases:
        findings = tuple(
            finding
            for finding in analyzer.analyze(text).issues
            if str(finding.source) in _GENERALIZED_SOURCES
        )
        assert [
            (finding.original, finding.suggestion, finding.start, finding.end)
            for finding in findings
        ] == [(original, suggestion, start, end)]


def test_generalized_government_public_evidence_has_exact_delta() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    positives = {
        text: tuple(
            finding
            for finding in analyzer.analyze(text).issues
            if str(finding.source) in _GENERALIZED_SOURCES
        )
        for text in _PUBLIC_POSITIVES
    }
    hard_negatives = {
        text: tuple(
            finding
            for finding in analyzer.analyze(text).issues
            if str(finding.source) in _GENERALIZED_SOURCES
        )
        for text in _PUBLIC_HARD_NEGATIVES
    }

    assert all(len(findings) == 1 for findings in positives.values())
    assert all(not findings for findings in hard_negatives.values())


def test_generalized_government_abstains_on_vocative_and_competing_pos() -> None:
    analyzer = Analyzer(AnalyzerConfig())

    assert not {
        str(finding.source)
        for finding in analyzer.analyze("Ufam lekarzu.").issues
        if str(finding.source) in _GENERALIZED_SOURCES
    }

    analyses = {
        "Szukam": _GovernmentBackend().analyses["Szukam"],
        "samochód": (
            *_GovernmentBackend().analyses["samochód"],
            (
                0,
                1,
                (
                    "samochód",
                    "samochód",
                    "adj:sg:nom.acc:m3:pos",
                    [],
                    [],
                ),
            ),
        ),
    }
    rule = InflectionGovernmentSzukacKluczRule(
        _provider(_GovernmentBackend(analyses=analyses))
    )

    assert rule.find("Szukam samochód.", options=AnalysisOptions()) == ()


def test_generalized_government_abstains_on_same_lemma_multiple_analyses() -> None:
    analyses = {
        "Szukam": _GovernmentBackend().analyses["Szukam"],
        "samochód": (
            (
                0,
                1,
                (
                    "samochód",
                    "samochód",
                    "subst:sg:nom:m3",
                    ["nazwa_pospolita"],
                    [],
                ),
            ),
            (
                0,
                1,
                (
                    "samochód",
                    "samochód",
                    "subst:sg:acc:m3",
                    ["nazwa_pospolita"],
                    [],
                ),
            ),
        ),
    }
    rule = InflectionGovernmentSzukacKluczRule(
        _provider(_GovernmentBackend(analyses=analyses))
    )

    assert rule.find("Szukam samochód.", options=AnalysisOptions()) == ()


def test_generalized_government_abstains_on_duplicate_analysis_rows() -> None:
    analysis: _AnalysisRow = (
        0,
        1,
        (
            "samochód",
            "samochód",
            "subst:sg:nom:m3",
            ["nazwa_pospolita"],
            [],
        ),
    )
    analyses = {
        "Szukam": _GovernmentBackend().analyses["Szukam"],
        "samochód": (analysis, analysis),
    }
    rule = InflectionGovernmentSzukacKluczRule(
        _provider(_GovernmentBackend(analyses=analyses))
    )

    assert rule.find("Szukam samochód.", options=AnalysisOptions()) == ()


def test_generalized_government_abstains_on_provider_io_failure() -> None:
    class _FailingBackend(_GovernmentBackend):
        def analyse(self, text: str) -> Sequence[_AnalysisRow]:
            raise OSError("provider I/O failure")

    rule = InflectionGovernmentSzukacKluczRule(_provider(_FailingBackend()))

    assert rule.find("Szukam samochód.", options=AnalysisOptions()) == ()


def test_legacy_government_abstains_on_provider_io_failure() -> None:
    class _FailingBackend(_GovernmentBackend):
        def analyse(self, text: str) -> Sequence[_AnalysisRow]:
            raise OSError(f"provider I/O failure for {text}")

    rule = InflectionGovernmentPotrzebowacPomocRule(_provider(_FailingBackend()))

    assert rule.find("Potrzebuję pomoc.", options=AnalysisOptions()) == ()


def test_generalized_government_does_not_reuse_cached_result_after_identity_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polis.rules._morfeusz as morfeusz_module

    rule = InflectionGovernmentSzukacKluczRule(_provider(_GovernmentBackend()))

    assert len(rule.find("Szukam samochód.", options=AnalysisOptions())) == 1

    monkeypatch.setattr(
        morfeusz_module,
        "_qualified_identity",
        lambda: _ProviderIdentity(
            package_version="1.99.16",
            dictionary_id="pl.sgjp.sgjp-2026.06.02",
            dictionary_notice_sha256=_NOTICE,
        ),
    )

    assert rule.find("Szukam samochód.", options=AnalysisOptions()) == ()


def test_generalized_government_abstains_without_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import polis.analyzer as analyzer_module

    monkeypatch.setattr(analyzer_module, "_load_qualified_morfeusz", lambda: None)
    analyzer = Analyzer(AnalyzerConfig())

    for text in ("Ufam nowy lekarz.", "Szukam samochód."):
        assert not {
            str(finding.source)
            for finding in analyzer.analyze(text).issues
            if str(finding.source) in _GENERALIZED_SOURCES
        }


@pytest.mark.parametrize(
    "mutation",
    (
        "malformed_analysis",
        "unknown_analysis_tag",
        "ambiguous_lemma",
        "duplicate_governor",
        "multiple_forms",
        "duplicate_forms",
    ),
)
def test_generalized_government_abstains_on_provider_drift(
    mutation: str,
) -> None:
    analyses = None
    generated = None
    if mutation == "malformed_analysis":
        analyses = {
            "Szukam": _GovernmentBackend().analyses["Szukam"],
            "samochód": ((0, 1, ("samochód", "", "subst:sg:nom.acc:m3", [], [])),),
        }
    elif mutation == "unknown_analysis_tag":
        analyses = {
            "Szukam": _GovernmentBackend().analyses["Szukam"],
            "samochód": (
                (
                    0,
                    1,
                    (
                        "samochód",
                        "samochód",
                        "mystery:sg:nom.acc:m3",
                        ["nazwa_pospolita"],
                        [],
                    ),
                ),
            ),
        }
    elif mutation == "ambiguous_lemma":
        analyses = {
            "Szukam": _GovernmentBackend().analyses["Szukam"],
            "samochód": (
                *_GovernmentBackend().analyses["samochód"],
                (
                    0,
                    1,
                    (
                        "samochód",
                        "auto",
                        "subst:sg:nom.acc:m3",
                        ["nazwa_pospolita"],
                        [],
                    ),
                ),
            ),
        }
    elif mutation == "duplicate_governor":
        analyses = {
            "Szukam": (
                *_GovernmentBackend().analyses["Szukam"],
                *_GovernmentBackend().analyses["Szukam"],
            ),
            "samochód": _GovernmentBackend().analyses["samochód"],
        }
    elif mutation == "multiple_forms":
        generated = {
            "samochód": (
                *_GovernmentBackend().generated["samochód"],
                ("samochodka", "samochód", "subst:sg:gen:m3", ["nazwa_pospolita"], []),
            )
        }
    else:
        generated = {
            "samochód": (
                *_GovernmentBackend().generated["samochód"],
                *_GovernmentBackend().generated["samochód"],
            )
        }

    rule = InflectionGovernmentSzukacKluczRule(
        _provider(_GovernmentBackend(analyses=analyses, generated=generated))
    )

    assert rule.find("Szukam samochód.", options=AnalysisOptions()) == ()


def test_qualified_loader_abstains_on_identity_io_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _IdentityFailingBackend:
        def analyse(self, text: str) -> Sequence[_AnalysisRow]:
            raise OSError(f"analysis I/O failure for {text}")

        def generate(self, lemma: str) -> Sequence[_GenerationRow]:
            raise OSError(f"generation I/O failure for {lemma}")

        def dict_id(self) -> str:
            raise OSError("identity I/O failure")

        def dict_copyright(self) -> str:
            return "unused"

    class _Module:
        @staticmethod
        def Morfeusz() -> _IdentityFailingBackend:
            return _IdentityFailingBackend()

    import polis.rules._morfeusz as morfeusz_module

    monkeypatch.setattr(
        morfeusz_module.importlib,
        "import_module",
        lambda _name: _Module(),
    )

    assert _load_qualified_morfeusz() is None


def test_canonical_adapter_does_not_hide_type_distinct_provider_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import hashlib

    import polis.rules._morfeusz as morfeusz_module

    valid: _GenerationRow = (
        "samochodu",
        "samochód",
        "subst:sg:gen:m3",
        ["nazwa_pospolita"],
        [],
    )
    malformed: _GenerationRow = (
        False,
        "samochód",
        "subst:sg:gen:m3",
        ["nazwa_pospolita"],
        [],
    )

    class _Backend(_GovernmentBackend):
        def dict_id(self) -> str:
            return "test-dictionary"

        def dict_copyright(self) -> str:
            return "test-notice"

    backend = _Backend(generated={"samochód": (valid, malformed)})
    identity = _ProviderIdentity(
        package_version="test-version",
        dictionary_id="test-dictionary",
        dictionary_notice_sha256=hashlib.sha256(b"test-notice").hexdigest(),
    )

    class _Module:
        @staticmethod
        def Morfeusz() -> _Backend:
            return backend

    monkeypatch.setattr(
        morfeusz_module.importlib,
        "import_module",
        lambda _name: _Module(),
    )
    monkeypatch.setattr(
        morfeusz_module.importlib.metadata,
        "version",
        lambda _name: "test-version",
    )
    monkeypatch.setattr(morfeusz_module, "_qualified_identity", lambda: identity)

    canonical_backend = _CanonicalMorfeuszBackend(backend)
    provider = _QualifiedMorfeusz(backend=canonical_backend, identity=identity)

    assert (
        InflectionGovernmentSzukacKluczRule(provider).find(
            "Szukam samochód.", options=AnalysisOptions()
        )
        == ()
    )


def test_canonical_adapter_preserves_duplicate_rows_for_abstention() -> None:
    backend = _GovernmentBackend(
        generated={
            "samochód": (
                *_GovernmentBackend().generated["samochód"],
                *_GovernmentBackend().generated["samochód"],
            )
        }
    )
    provider = _QualifiedMorfeusz(
        backend=_CanonicalMorfeuszBackend(backend),
        identity=_provider(backend).identity,
    )

    assert (
        InflectionGovernmentSzukacKluczRule(provider).find(
            "Szukam samochód.", options=AnalysisOptions()
        )
        == ()
    )
