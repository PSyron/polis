from __future__ import annotations

import hashlib
import warnings
from collections.abc import Sequence

import pytest

import polis.rules._morfeusz as morfeusz_module
import polis.rules.government as government_module
import polis.rules.subject_verb as subject_verb_module
from polis import (
    Analyzer,
    AnalyzerConfig,
    MorphologyProviderIdentity,
    MorphologyStatus,
)

_PACKAGE_VERSION = "1.99.15"
_DICTIONARY_ID = "pl.sgjp.sgjp-2026.06.01"
_NOTICE = "Polis test-only Morfeusz notice."
_NOTICE_SHA256 = hashlib.sha256(_NOTICE.encode("utf-8")).hexdigest()
type _AnalysisRow = tuple[int, int, tuple[str, str, str, list[str], list[str]]]
type _GenerationRow = tuple[str, str, str, list[str], list[str]]
type _Finding = tuple[str, str, str | None, int, int]
type _Findings = tuple[tuple[str, str, str | None, int, int], ...]


def _analysis_row(
    surface: str,
    lemma: str,
    tag: str,
    labels: tuple[str, ...] = (),
    qualifiers: tuple[str, ...] = (),
) -> _AnalysisRow:
    return (0, 1, (surface, lemma, tag, list(labels), list(qualifiers)))


def _generation_row(form: str, lemma: str, tag: str) -> _GenerationRow:
    return (form, lemma, tag, [], [])


def _finding(
    source: str,
    original: str,
    suggestion: str | None,
    start: int,
    end: int,
) -> _Finding:
    return (source, original, suggestion, start, end)


class _FakeMorfeuszBackend:
    def __init__(self, dictionary_id: str) -> None:
        self._dictionary_id = dictionary_id

    def dict_id(self) -> str:
        return self._dictionary_id

    def dict_copyright(self) -> str:
        return _NOTICE

    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        rows: dict[str, tuple[_AnalysisRow, ...]] = {
            "Ta": (
                _analysis_row("Ta", "ta", "part", qualifiers=("reg.",)),
                _analysis_row("Ta", "ten", "adj:sg:nom.voc:f:pos"),
            ),
            "nowy": (
                _analysis_row(
                    "nowy", "nowy:S", "subst:sg:nom:m1", ("nazwa_pospolita",)
                ),
                _analysis_row("nowy", "nowy:A", "adj:sg:acc:m3:pos"),
                _analysis_row("nowy", "nowy:A", "adj:sg:nom.voc:m1.m2.m3:pos"),
            ),
            "książka": (
                _analysis_row(
                    "książka", "książka", "subst:sg:nom:f", ("nazwa_pospolita",)
                ),
            ),
            "Oni": (
                _analysis_row("Oni", "on:A", "adj:pl:nom.voc:m1:pos", (), ("daw.",)),
                _analysis_row(
                    "Oni",
                    "on:S",
                    "ppron3:pl:nom:m1:ter:akc.nakc:praep.npraep",
                ),
            ),
            "czyta": (_analysis_row("czyta", "czytać", "fin:sg:ter:imperf"),),
            "czerwony": (
                _analysis_row(
                    "czerwony",
                    "czerwony:A",
                    "adj:sg:nom.voc:m1.m2.m3:pos",
                ),
                _analysis_row("czerwony", "czerwony:S", "subst:sg:nom:m1"),
            ),
            "samochód": (_analysis_row("samochód", "samochód", "subst:sg:nom.acc:m3"),),
        }
        return rows[text]

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        rows: dict[str, tuple[_GenerationRow, ...]] = {
            "nowy:A": (_generation_row("nowa", "nowy:A", "adj:sg:nom.voc:f:pos"),),
            "czytać": (_generation_row("czytają", "czytać", "fin:pl:ter:imperf"),),
            "czerwony:A": (
                _generation_row(
                    "czerwonego",
                    "czerwony:A",
                    "adj:sg:gen:m1.m2.m3.n:pos",
                ),
            ),
            "samochód": (_generation_row("samochodu", "samochód", "subst:sg:gen:m3"),),
        }
        return rows[lemma]


_FakeMorfeusz = type("Morfeusz", (_FakeMorfeuszBackend,), {"__module__": "morfeusz2"})


class _FakeMorfeuszModule:
    def __init__(self, backend: _FakeMorfeuszBackend) -> None:
        self._backend = backend

    def Morfeusz(self) -> _FakeMorfeuszBackend:
        return self._backend


def _install_fake_morfeusz(
    monkeypatch: pytest.MonkeyPatch,
    *,
    dictionary_id: str = _DICTIONARY_ID,
) -> MorphologyProviderIdentity:
    backend = _FakeMorfeusz(dictionary_id)
    module = _FakeMorfeuszModule(backend)
    expected = MorphologyProviderIdentity(
        package_version=_PACKAGE_VERSION,
        dictionary_id=_DICTIONARY_ID,
        dictionary_notice_sha256=_NOTICE_SHA256,
    )

    def import_module(name: str) -> _FakeMorfeuszModule:
        assert name == "morfeusz2"
        return module

    def package_version(name: str) -> str:
        assert name == "morfeusz2"
        return _PACKAGE_VERSION

    monkeypatch.setattr(morfeusz_module.importlib, "import_module", import_module)
    monkeypatch.setattr(morfeusz_module.importlib.metadata, "version", package_version)

    def qualified_identity() -> morfeusz_module._ProviderIdentity:
        return morfeusz_module._ProviderIdentity(
            package_version=expected.package_version,
            dictionary_id=expected.dictionary_id,
            dictionary_notice_sha256=expected.dictionary_notice_sha256,
        )

    for consumer_module in (
        morfeusz_module,
        government_module,
        subject_verb_module,
    ):
        monkeypatch.setattr(consumer_module, "_qualified_identity", qualified_identity)
    return expected


def _findings(analyzer: Analyzer, text: str) -> _Findings:
    return tuple(
        (str(f.source), f.original, f.suggestion, f.start, f.end)
        for f in analyzer.analyze(text).issues
    )


def test_morphology_status_is_active_for_a_qualified_installed_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    expected = _install_fake_morfeusz(monkeypatch)
    analyzer = Analyzer(AnalyzerConfig())

    # When
    status = analyzer.morphology_status

    # Then
    assert isinstance(status, MorphologyStatus)
    assert status.expected_identity == expected
    assert status.state == "active"
    assert status.actual_identity == expected


def test_morphology_status_is_unavailable_without_morfeusz_and_does_not_warn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    def missing_morfeusz(name: str) -> _FakeMorfeuszModule:
        assert name == "morfeusz2"
        raise ImportError(name)

    monkeypatch.setattr(
        morfeusz_module.importlib,
        "import_module",
        missing_morfeusz,
    )

    # When
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        analyzer = Analyzer(AnalyzerConfig())
        status = analyzer.morphology_status
        analyzer.analyze("zeby")

    # Then
    assert status.state == "unavailable"
    assert status.actual_identity is None
    assert captured == []


def test_morphology_status_reports_drift_identities_and_warns_once_per_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    expected = _install_fake_morfeusz(
        monkeypatch,
        dictionary_id="pl.sgjp.sgjp-2026.07.01",
    )
    actual = MorphologyProviderIdentity(
        package_version=_PACKAGE_VERSION,
        dictionary_id="pl.sgjp.sgjp-2026.07.01",
        dictionary_notice_sha256=_NOTICE_SHA256,
    )

    # When
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        first = Analyzer(AnalyzerConfig())
        first_status = first.morphology_status
        first.analyze("zeby")
        first.analyze("zeby")
        second = Analyzer(AnalyzerConfig())
        second_status = second.morphology_status
        second.analyze("zeby")

    # Then
    assert first_status.state == second_status.state == "drifted"
    assert first_status.expected_identity == second_status.expected_identity == expected
    assert first_status.actual_identity == second_status.actual_identity == actual
    assert [warning.category for warning in captured] == [UserWarning]


@pytest.mark.parametrize(
    ("text", "expected"),
    (
        (
            "Ta nowy książka.",
            (
                _finding(
                    "rule:agreement.nominal_group_ta_nowy_ksiazka", "nowy", "nowa", 3, 7
                ),
            ),
        ),
        (
            "Oni czyta książkę.",
            (
                _finding(
                    "rule:agreement.subject_verb_oni_czyta", "czyta", "czytają", 4, 9
                ),
            ),
        ),
        (
            "Nie widzę czerwony samochód.",
            (
                _finding(
                    "rule:inflection.negated_widziec_nominal_group",
                    "czerwony samochód",
                    "czerwonego samochodu",
                    10,
                    27,
                ),
            ),
        ),
    ),
)
def test_morphology_status_observation_preserves_existing_morphology_findings(
    monkeypatch: pytest.MonkeyPatch,
    text: str,
    expected: _Findings,
) -> None:
    # Given
    _install_fake_morfeusz(monkeypatch)
    before_observation = Analyzer(AnalyzerConfig())
    after_observation = Analyzer(AnalyzerConfig())
    before = _findings(before_observation, text)

    # When
    status = after_observation.morphology_status
    after = _findings(after_observation, text)

    # Then
    assert status.state == "active"
    assert before == expected
    assert after == before
