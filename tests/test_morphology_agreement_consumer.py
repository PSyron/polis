from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol

import pytest

from polis import AnalysisOptions
from polis.core import Category
from polis.core.models import Severity
from polis.rules._morfeusz import _ProviderIdentity, _QualifiedMorfeusz
from polis.rules.agreement import AgreementNominalGroupTeDuzeOknoRule

_NOTICE_SHA256 = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
_BEHAVIOR_VERSION = (
    "agreement-nominal-group-te-duze-okno/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    f"{_NOTICE_SHA256}"
)
type _Interpretation = tuple[str, str, str, list[str], list[str]]
type _AnalysisRow = tuple[int, int, _Interpretation]
type _GenerationRow = tuple[str, str, str, list[str], list[str]]
type _MalformedAnalysisRow = tuple[Literal[1], Literal[2], _Interpretation]

_TE_ANALYSES: tuple[_AnalysisRow, ...] = (
    (0, 1, ("Te", "ten", "adj:pl:acc:m2.m3.f.n:pos", [], [])),
    (0, 1, ("Te", "ten", "adj:pl:nom.voc:m2.m3.f.n:pos", [], [])),
    (0, 1, ("Te", "ty", "ppron12:sg:voc:m1.m2.m3.f.n:sec", [], ["niepopr.,pot."])),
    (
        0,
        1,
        (
            "Te",
            "te",
            "subst:sg.pl:nom.gen.dat.acc.inst.loc.voc:n:ncol",
            ["nazwa_pospolita"],
            [],
        ),
    ),
)
_DUZE_ANALYSES: tuple[_AnalysisRow, ...] = (
    (0, 1, ("duże", "duży", "adj:pl:acc:m2.m3.f.n:pos", [], [])),
    (0, 1, ("duże", "duży", "adj:pl:nom.voc:m2.m3.f.n:pos", [], [])),
    (0, 1, ("duże", "duży", "adj:sg:acc:n:pos", [], [])),
    (0, 1, ("duże", "duży", "adj:sg:nom.voc:n:pos", [], [])),
    (0, 1, ("duże", "duha", "subst:sg:dat.loc:f", ["nazwa_pospolita"], [])),
)
_OKNO_ANALYSES: tuple[_AnalysisRow, ...] = (
    (0, 1, ("okno", "okno", "subst:sg:nom.acc.voc:n:ncol", [], [])),
)
_TO_FORMS: tuple[_GenerationRow, ...] = (
    ("tych", "ten", "adj:pl:acc:m1:pos", [], []),
    ("te", "ten", "adj:pl:acc:m2.m3.f.n:pos", [], []),
    ("tym", "ten", "adj:pl:dat:m1.m2.m3.f.n:pos", [], []),
    ("tych", "ten", "adj:pl:gen:m1.m2.m3.f.n:pos", [], []),
    ("tymi", "ten", "adj:pl:inst:m1.m2.m3.f.n:pos", [], []),
    ("tych", "ten", "adj:pl:loc:m1.m2.m3.f.n:pos", [], []),
    ("ci", "ten", "adj:pl:nom.voc:m1:pos", [], []),
    ("te", "ten", "adj:pl:nom.voc:m2.m3.f.n:pos", [], []),
    ("tą", "ten", "adj:sg:acc:f:pos", [], ["pot."]),
    ("tę", "ten", "adj:sg:acc:f:pos", [], []),
    ("tego", "ten", "adj:sg:acc:m1.m2:pos", [], []),
    ("ten", "ten", "adj:sg:acc:m3:pos", [], []),
    ("to", "ten", "adj:sg:acc:n:pos", [], []),
    ("tej", "ten", "adj:sg:dat:f:pos", [], []),
    ("temu", "ten", "adj:sg:dat:m1.m2.m3.n:pos", [], []),
    ("tej", "ten", "adj:sg:gen:f:pos", [], []),
    ("tego", "ten", "adj:sg:gen:m1.m2.m3.n:pos", [], []),
    ("tą", "ten", "adj:sg:inst:f:pos", [], []),
    ("tym", "ten", "adj:sg:inst:m1.m2.m3.n:pos", [], []),
    ("tej", "ten", "adj:sg:loc:f:pos", [], []),
    ("tym", "ten", "adj:sg:loc:m1.m2.m3.n:pos", [], []),
    ("ta", "ten", "adj:sg:nom.voc:f:pos", [], []),
    ("ten", "ten", "adj:sg:nom.voc:m1.m2.m3:pos", [], []),
    ("to", "ten", "adj:sg:nom.voc:n:pos", [], []),
)
_MALFORMED_ANALYSES: tuple[_MalformedAnalysisRow, ...] = (
    (1, 2, ("Te", "ten", "adj:pl:nom.voc:m2.m3.f.n:pos", [], [])),
)


class _AgreementBackend(Protocol):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]: ...

    def generate(self, lemma: str) -> Sequence[_GenerationRow]: ...


class _QualifiedBackend:
    def __init__(
        self,
        *,
        te_analyses: Sequence[_AnalysisRow] = _TE_ANALYSES,
        duze_analyses: Sequence[_AnalysisRow] = _DUZE_ANALYSES,
        okno_analyses: Sequence[_AnalysisRow] = _OKNO_ANALYSES,
        to_forms: Sequence[_GenerationRow] = _TO_FORMS,
    ) -> None:
        self.te_analyses = te_analyses
        self.duze_analyses = duze_analyses
        self.okno_analyses = okno_analyses
        self.to_forms = to_forms
        self.calls = 0

    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        self.calls += 1
        return {
            "Te": self.te_analyses,
            "duże": self.duze_analyses,
            "okno": self.okno_analyses,
        }[text]

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        self.calls += 1
        assert lemma == "ten"
        return self.to_forms


class _FailingBackend(_QualifiedBackend):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        raise RuntimeError(text)


class _MalformedRowsBackend:
    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        return _MALFORMED_ANALYSES

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        return _TO_FORMS


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


def test_nominal_group_agreement_emits_exact_review_only_finding() -> None:
    # Given
    rule = AgreementNominalGroupTeDuzeOknoRule(_provider(_QualifiedBackend()))

    # When
    findings = rule.find("Te duże okno jest otwarte.", options=AnalysisOptions())

    # Then
    assert len(findings) == 1
    finding = findings[0]
    assert str(finding.source) == "rule:agreement.nominal_group_te_duze_okno"
    assert finding.category is Category.AGREEMENT
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "Te"
    assert finding.suggestion == "To"
    assert (finding.start, finding.end) == (0, 2)
    assert finding.confidence.value == 0.9
    assert rule.operation == "replace.demonstrative_neuter_form"
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
    rule = AgreementNominalGroupTeDuzeOknoRule(
        _provider(_QualifiedBackend(), **identity)
    )

    # When
    findings = rule.find("Te duże okno jest otwarte.", options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    "backend",
    (
        _QualifiedBackend(te_analyses=()),
        _MalformedRowsBackend(),
        _QualifiedBackend(te_analyses=((0, 1, ("Te", "ten", "ign", [], [])),)),
        _QualifiedBackend(
            duze_analyses=((0, 1, ("duże", "duży", "adj:pl:nom.voc:f.n:pos", [], [])),)
        ),
        _QualifiedBackend(
            okno_analyses=(
                (0, 1, ("okno", "okno", "subst:pl:nom.acc.voc:n:ncol", [], [])),
            )
        ),
        _QualifiedBackend(to_forms=()),
        _QualifiedBackend(
            to_forms=(
                *_TO_FORMS,
                ("toż", "ten", "adj:sg:nom.voc:n:pos", [], []),
            )
        ),
        _FailingBackend(),
    ),
)
def test_rule_abstains_on_malformed_unknown_or_non_unique_provider_output(
    backend: _AgreementBackend,
) -> None:
    # Given
    rule = AgreementNominalGroupTeDuzeOknoRule(_provider(backend))

    # When
    findings = rule.find("Te duże okno jest otwarte.", options=AnalysisOptions())

    # Then
    assert findings == ()


def test_rule_abstains_when_a_selected_lemma_is_ambiguous() -> None:
    # Given
    alternate: _AnalysisRow = (
        0,
        1,
        ("duże", "duża", "adj:sg:nom.voc:n:pos", [], []),
    )
    rule = AgreementNominalGroupTeDuzeOknoRule(
        _provider(_QualifiedBackend(duze_analyses=(*_DUZE_ANALYSES, alternate)))
    )

    # When
    findings = rule.find("Te duże okno jest otwarte.", options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    "text",
    (
        "To duże okno jest otwarte.",
        "Te duże okna są otwarte.",
        "Te duże dziecko jest gotowe.",
        "Te duży okno jest otwarte.",
        "Te duże okno jest otwarte!",
        "Dzisiaj Te duże okno jest otwarte.",
    ),
)
def test_rule_abstains_for_close_negative_sentences(text: str) -> None:
    # Given
    backend = _QualifiedBackend()
    rule = AgreementNominalGroupTeDuzeOknoRule(_provider(backend))

    # When
    findings = rule.find(text, options=AnalysisOptions())

    # Then
    assert findings == ()
    assert backend.calls == 0


def test_rule_excludes_category_before_calling_provider() -> None:
    # Given
    backend = _QualifiedBackend()
    rule = AgreementNominalGroupTeDuzeOknoRule(_provider(backend))

    # When
    findings = rule.find(
        "Te duże okno jest otwarte.",
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    # Then
    assert findings == ()
    assert backend.calls == 0


def test_rule_abstains_without_provider() -> None:
    # Given
    rule = AgreementNominalGroupTeDuzeOknoRule(None)

    # When
    findings = rule.find("Te duże okno jest otwarte.", options=AnalysisOptions())

    # Then
    assert findings == ()
