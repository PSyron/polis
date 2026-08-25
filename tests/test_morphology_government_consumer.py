from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol

import pytest

from polis import AnalysisOptions
from polis.core import Category
from polis.core.models import Severity
from polis.rules._morfeusz import _ProviderIdentity, _QualifiedMorfeusz
from polis.rules.government import (
    _GOVERNED_FORMS,
    InflectionGovernmentPotrzebowacPomocRule,
)

_NOTICE_SHA256 = "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
_BEHAVIOR_VERSION = (
    "inflection-government-potrzebowac-pomoc/2.0+"
    "morfeusz2-1.99.15.pl-sgjp-sgjp-2026.06.01.notice-"
    f"{_NOTICE_SHA256}"
)
_TEXT = "Potrzebuję pomoc."
type _Interpretation = tuple[str, str, str, list[str], list[str]]
type _AnalysisRow = tuple[int, int, _Interpretation]
type _GenerationRow = tuple[str, str, str, list[str], list[str]]
type _MalformedAnalysisRow = tuple[Literal[1], Literal[2], _Interpretation]

_GOVERNOR_ANALYSES: tuple[_AnalysisRow, ...] = (
    (0, 1, ("Potrzebuję", "potrzebować", "fin:sg:pri:imperf", [], [])),
)
_GOVERNED_ANALYSES: tuple[_AnalysisRow, ...] = (
    (0, 1, ("pomoc", "pomoc", "subst:sg:nom:f", ["nazwa_pospolita"], [])),
    (0, 1, ("pomoc", "pomoc", "subst:sg:acc:f", ["nazwa_pospolita"], [])),
)
_POMOCY_FORMS: tuple[_GenerationRow, ...] = (
    ("pomocy", "pomoc", "subst:sg:gen:f", ["nazwa_pospolita"], []),
)
_MALFORMED_ANALYSES: tuple[_MalformedAnalysisRow, ...] = (
    (1, 2, ("pomoc", "pomoc", "subst:sg:nom:f", ["nazwa_pospolita"], [])),
)


class _GovernmentBackend(Protocol):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]: ...

    def generate(self, lemma: str) -> Sequence[_GenerationRow]: ...


class _QualifiedBackend:
    def __init__(
        self,
        *,
        governor_analyses: Sequence[_AnalysisRow] = _GOVERNOR_ANALYSES,
        governed_analyses: Sequence[_AnalysisRow] = _GOVERNED_ANALYSES,
        pomocy_forms: Sequence[_GenerationRow] = _POMOCY_FORMS,
    ) -> None:
        self.governor_analyses = governor_analyses
        self.governed_analyses = governed_analyses
        self.pomocy_forms = pomocy_forms
        self.calls = 0

    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        self.calls += 1
        return {
            "Potrzebuję": self.governor_analyses,
            "pomoc": self.governed_analyses,
        }[text]

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        self.calls += 1
        assert lemma == "pomoc"
        return self.pomocy_forms


class _FailingBackend(_QualifiedBackend):
    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        raise RuntimeError(text)


class _MalformedRowsBackend:
    def analyse(self, text: str) -> Sequence[_AnalysisRow]:
        del text
        return _MALFORMED_ANALYSES

    def generate(self, lemma: str) -> Sequence[_GenerationRow]:
        del lemma
        return _POMOCY_FORMS


def _provider(
    backend: _GovernmentBackend,
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


def test_governed_form_table_has_exactly_one_approved_row() -> None:
    # Given / When
    rows = _GOVERNED_FORMS

    # Then
    (row,) = rows
    assert (row.governor_surface, row.governor_lemma, row.governor_tags) == (
        "Potrzebuję",
        "potrzebować",
        frozenset({"fin:sg:pri:imperf"}),
    )
    assert (row.governed_surface, row.governed_lemma, row.governed_tags) == (
        "pomoc",
        "pomoc",
        frozenset({"subst:sg:nom:f", "subst:sg:acc:f"}),
    )
    assert (row.target_tag, row.target_form) == ("subst:sg:gen:f", "pomocy")


def test_government_rule_emits_exact_review_only_finding() -> None:
    # Given
    rule = InflectionGovernmentPotrzebowacPomocRule(_provider(_QualifiedBackend()))

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert len(findings) == 1
    finding = findings[0]
    assert str(finding.source) == "rule:inflection.government_potrzebowac_pomoc"
    assert finding.category is Category.INFLECTION
    assert finding.severity is Severity.SUGGESTION
    assert finding.original == "pomoc"
    assert finding.suggestion == "pomocy"
    assert (finding.start, finding.end) == (11, 16)
    assert finding.confidence.value == 0.9
    assert rule.operation == "replace.governed_form"
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
    rule = InflectionGovernmentPotrzebowacPomocRule(
        _provider(_QualifiedBackend(), **identity)
    )

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    "backend",
    (
        None,
        _QualifiedBackend(governor_analyses=()),
        _QualifiedBackend(governed_analyses=()),
        _MalformedRowsBackend(),
        _QualifiedBackend(
            governor_analyses=((0, 1, ("Potrzebuję", "potrzebować", "ign", [], [])),)
        ),
        _QualifiedBackend(
            governed_analyses=(
                (0, 1, ("pomoc", "pomoc", "ign", ["nazwa_pospolita"], [])),
            )
        ),
        _QualifiedBackend(
            governor_analyses=(
                (0, 1, ("Potrzebuję", "potrzebować", "fin:pl:pri:imperf", [], [])),
            )
        ),
        _QualifiedBackend(
            governed_analyses=(
                (0, 1, ("pomoc", "pomoc", "subst:sg:nom:f", ["nazwa_pospolita"], [])),
            )
        ),
        _QualifiedBackend(pomocy_forms=()),
        _FailingBackend(),
    ),
)
def test_rule_abstains_on_missing_malformed_ign_or_exception_provider_output(
    backend: _GovernmentBackend | None,
) -> None:
    # Given
    provider = None if backend is None else _provider(backend)
    rule = InflectionGovernmentPotrzebowacPomocRule(provider)

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    "backend",
    (
        _QualifiedBackend(
            governor_analyses=(
                *_GOVERNOR_ANALYSES,
                (
                    0,
                    1,
                    (
                        "Potrzebuję",
                        "potrzebować:alternate",
                        "fin:sg:pri:imperf",
                        [],
                        [],
                    ),
                ),
            )
        ),
        _QualifiedBackend(
            governor_analyses=(
                *_GOVERNOR_ANALYSES,
                (0, 1, ("Potrzebuję", "potrzebować", "fin:sg:ter:imperf", [], [])),
            )
        ),
        _QualifiedBackend(
            governed_analyses=(
                *_GOVERNED_ANALYSES,
                (0, 1, ("pomoc", "pomoc:alternate", "subst:sg:nom:f", [], [])),
            )
        ),
        _QualifiedBackend(
            governed_analyses=(
                *_GOVERNED_ANALYSES,
                (0, 1, ("pomoc", "pomoc", "subst:sg:gen:f", [], [])),
            )
        ),
        _QualifiedBackend(
            pomocy_forms=(
                *_POMOCY_FORMS,
                ("pomoc_alt", "pomoc", "subst:sg:gen:f", [], []),
            )
        ),
    ),
)
def test_rule_abstains_on_extra_lemma_tag_or_nonunique_generation(
    backend: _GovernmentBackend,
) -> None:
    # Given
    rule = InflectionGovernmentPotrzebowacPomocRule(_provider(backend))

    # When
    findings = rule.find(_TEXT, options=AnalysisOptions())

    # Then
    assert findings == ()


@pytest.mark.parametrize(
    ("text", "categories"),
    (
        ("Potrzebuję pomocy.", None),
        ("Potrzebuję.", None),
        ("Potrzebuję wsparcie.", None),
        ("Potrzebuję pomóc.", None),
        ("Potrzebuję pomoc lub poradę.", None),
        ("Ta pomoc jest potrzebna.", None),
        ("Potrzebuje pomoc.", None),
        ("potrzebuję pomoc.", None),
        ("Nie potrzebuję pomoc.", None),
        ("Myślę o pomoc.", None),
        ("Potrzebuję pomoc!", None),
        ("Bardzo potrzebuję pomoc.", None),
        (_TEXT, frozenset({Category.SPELLING})),
    ),
)
def test_rule_abstains_for_all_named_close_negatives_and_filtered_category(
    text: str,
    categories: frozenset[Category] | None,
) -> None:
    # Given
    backend = _QualifiedBackend()
    rule = InflectionGovernmentPotrzebowacPomocRule(_provider(backend))

    # When
    findings = rule.find(text, options=AnalysisOptions(categories=categories))

    # Then
    assert findings == ()
    assert backend.calls == 0
