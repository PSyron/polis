from __future__ import annotations

from collections.abc import Sequence

import pytest

from polis import AnalysisOptions
from polis.core import Category
from polis.core.models import Severity
from polis.rules._morfeusz import (
    _ProviderIdentity,
    _QualifiedMorfeusz,
)
from polis.rules.inflection import InflectionNegatedWidziecNominalGroupRule

_NOTICE_SHA256 = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
_BEHAVIOR_VERSION = (
    "inflection-negated-widziec-nominal-group/1.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    f"{_NOTICE_SHA256}"
)
type _Row = tuple[object, ...]

_ADJECTIVE_ANALYSES: tuple[_Row, ...] = (
    (
        0,
        1,
        (
            "czerwony",
            "czerwony:A",
            "adj:sg:nom.voc:m1.m2.m3:pos",
            [],
            [],
        ),
    ),
    (0, 1, ("czerwony", "czerwony:S", "subst:sg:nom:m1", [], [])),
)
_NOUN_ANALYSES: tuple[_Row, ...] = (
    (0, 1, ("samochód", "samochód", "subst:sg:nom.acc:m3", [], [])),
)
_ADJECTIVE_FORMS: tuple[_Row, ...] = (
    (
        "czerwonego",
        "czerwony:A",
        "adj:sg:gen:m1.m2.m3.n:pos",
        [],
        [],
    ),
)
_NOUN_FORMS: tuple[_Row, ...] = (("samochodu", "samochód", "subst:sg:gen:m3", [], []),)


class _QualifiedBackend:
    def __init__(
        self,
        *,
        adjective_analyses: Sequence[_Row] = _ADJECTIVE_ANALYSES,
        noun_analyses: Sequence[_Row] = _NOUN_ANALYSES,
        adjective_forms: Sequence[_Row] = _ADJECTIVE_FORMS,
        noun_forms: Sequence[_Row] = _NOUN_FORMS,
    ) -> None:
        self.adjective_analyses = adjective_analyses
        self.noun_analyses = noun_analyses
        self.adjective_forms = adjective_forms
        self.noun_forms = noun_forms
        self.calls = 0

    def analyse(self, text: str) -> Sequence[_Row]:
        self.calls += 1
        rows = {
            "czerwony": self.adjective_analyses,
            "samochód": self.noun_analyses,
        }
        return rows[text]

    def generate(self, lemma: str) -> Sequence[_Row]:
        self.calls += 1
        rows = {
            "czerwony:A": self.adjective_forms,
            "samochód": self.noun_forms,
        }
        return rows[lemma]


class _FailingBackend(_QualifiedBackend):
    def analyse(self, text: str) -> Sequence[_Row]:
        raise RuntimeError(text)


def _provider(
    backend: _QualifiedBackend,
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


def test_rule_emits_the_approved_exact_review_only_finding() -> None:
    # Given
    rule = InflectionNegatedWidziecNominalGroupRule(_provider(_QualifiedBackend()))

    # When
    findings = rule.find(
        "Nie widzę czerwony samochód.",
        options=AnalysisOptions(),
    )

    # Then
    assert len(findings) == 1
    finding = findings[0]
    assert str(finding.source) == ("rule:inflection.negated_widziec_nominal_group")
    assert finding.category is Category.INFLECTION
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "czerwony samochód"
    assert finding.suggestion == "czerwonego samochodu"
    assert (finding.start, finding.end) == (10, 27)
    assert finding.confidence.value == 0.9
    assert rule.operation == "replace.negated_government_nominal_group"
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
    identity_field: str,
    drifted_value: str,
) -> None:
    # Given
    identity = {
        "package_version": "1.99.15",
        "dictionary_id": "pl.sgjp.sgjp-2026.06.01",
        "notice_sha256": _NOTICE_SHA256,
    }
    identity[identity_field] = drifted_value
    rule = InflectionNegatedWidziecNominalGroupRule(
        _provider(_QualifiedBackend(), **identity)
    )

    # When
    findings = rule.find("Nie widzę czerwony samochód.", options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    "backend",
    (
        _QualifiedBackend(adjective_analyses=()),
        _QualifiedBackend(adjective_analyses=((),)),
        _QualifiedBackend(
            adjective_analyses=(
                (1, 2, ("czerwony", "czerwony:A", "adj:sg:nom:m3:pos", [], [])),
            )
        ),
        _QualifiedBackend(
            adjective_analyses=(
                (0, 1, ("zielony", "czerwony:A", "adj:sg:nom:m3:pos", [], [])),
            )
        ),
        _QualifiedBackend(
            adjective_analyses=((0, 1, ("czerwony", "czerwony:A", "ign", [], [])),)
        ),
        _QualifiedBackend(adjective_forms=()),
        _QualifiedBackend(adjective_forms=(("", "czerwony:A", "x", [], []),)),
        _QualifiedBackend(
            adjective_forms=(
                *_ADJECTIVE_FORMS,
                ("czerwonej", "czerwony:A", "adj:sg:gen:m1.m2.m3.n:pos", [], []),
            )
        ),
        _FailingBackend(),
    ),
)
def test_rule_abstains_on_untrusted_or_non_unique_provider_output(
    backend: _QualifiedBackend,
) -> None:
    # Given
    rule = InflectionNegatedWidziecNominalGroupRule(_provider(backend))

    # When
    findings = rule.find("Nie widzę czerwony samochód.", options=AnalysisOptions())

    # Then
    assert findings == ()


def test_rule_abstains_on_an_alternate_plausible_adjective_lemma() -> None:
    # Given
    alternate: _Row = (
        0,
        1,
        ("czerwony", "czerwony:Alt", "adj:sg:nom.voc:m1.m2.m3:pos", [], []),
    )
    backend = _QualifiedBackend(adjective_analyses=(*_ADJECTIVE_ANALYSES, alternate))
    rule = InflectionNegatedWidziecNominalGroupRule(_provider(backend))

    # When
    findings = rule.find("Nie widzę czerwony samochód.", options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    "text",
    (
        "Nie widzę czerwonego samochodu.",
        "Nie widzę czerwony rower.",
        "Nie widzę zielony samochód.",
        "Widzę czerwony samochód.",
        "Dzisiaj nie widzę czerwony samochód.",
        "Nie widzę czerwony samochód!",
        "nie widzę czerwony samochód.",
    ),
)
def test_rule_abstains_outside_the_approved_exact_sentence(text: str) -> None:
    # Given
    backend = _QualifiedBackend()
    rule = InflectionNegatedWidziecNominalGroupRule(_provider(backend))

    # When
    findings = rule.find(text, options=AnalysisOptions())

    # Then
    assert findings == ()
    assert backend.calls == 0


def test_rule_excludes_category_before_calling_provider() -> None:
    # Given
    backend = _QualifiedBackend()
    rule = InflectionNegatedWidziecNominalGroupRule(_provider(backend))

    # When
    findings = rule.find(
        "Nie widzę czerwony samochód.",
        options=AnalysisOptions(categories={Category.SPELLING}),
    )

    # Then
    assert findings == ()
    assert backend.calls == 0


def test_rule_abstains_without_provider() -> None:
    # Given
    rule = InflectionNegatedWidziecNominalGroupRule(None)

    # When
    findings = rule.find("Nie widzę czerwony samochód.", options=AnalysisOptions())

    # Then
    assert findings == ()
