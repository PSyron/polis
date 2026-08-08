from __future__ import annotations

from pathlib import Path

from scripts.morphology_provider_contract import (
    QualificationCase,
    load_qualification_dataset,
)
from scripts.morphology_provider_morfeusz import (
    AnalysisRow,
    GenerationRow,
    MorfeuszProvider,
    ProviderIdentity,
)

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "tests/fixtures/v1/morphology_provider_qualification.json"
MANIFEST = DATASET.with_suffix(".manifest.json")


class FakeBackend:
    def analyse(
        self, text: str
    ) -> list[tuple[int, int, tuple[str, str, str, list[str], list[str]]]]:
        rows: dict[str, list[AnalysisRow]] = {
            "pomoc": [(0, 1, ("pomoc", "pomoc", "subst:sg:nom:f", [], []))],
            "pomocy": [
                (0, 1, ("pomocy", "pomoc", "subst:sg:gen:f", [], [])),
                (0, 1, ("pomocy", "pomoc", "subst:sg:dat.loc:f", [], [])),
            ],
            "samochód": [
                (0, 1, ("samochód", "samochód", "subst:sg:nom.acc:m3", [], []))
            ],
            "samochodu": [(0, 1, ("samochodu", "samochód", "subst:sg:gen:m3", [], []))],
            "nowy": [
                (0, 1, ("nowy", "nowy:S", "subst:sg:nom:m1", [], [])),
                (0, 1, ("nowy", "nowy:A", "adj:sg:nom.voc:m1.m2.m3:pos", [], [])),
            ],
            "xyzzyq": [(0, 1, ("xyzzyq", "xyzzyq", "ign", [], []))],
        }
        return rows[text]

    def generate(self, lemma: str) -> list[tuple[str, str, str, list[str], list[str]]]:
        rows: dict[str, list[GenerationRow]] = {
            "pomoc": [
                ("pomocy", "pomoc", "subst:sg:gen:f", [], []),
                ("pomocy", "pomoc", "subst:sg:dat.loc:f", [], []),
            ],
            "samochód": [
                ("samochodu", "samochód", "subst:sg:gen:m3", [], []),
                ("samochodu", "samochód", "subst:sg:gen:m3", [], []),
            ],
            "nowy:A": [("nowa", "nowy:A", "adj:sg:nom.voc:f:pos", [], [])],
            "nowy:S": [("nowy", "nowy:S", "subst:sg:nom:m1", [], [])],
        }
        return rows[lemma]


class InvalidAnalysisBackend(FakeBackend):
    def analyse(self, text: str) -> list[AnalysisRow]:
        return [(0, 1, (text, "", "", [], []))]


class InvalidGenerationBackend(FakeBackend):
    def generate(self, lemma: str) -> list[GenerationRow]:
        return [("", lemma, "subst:sg:gen:f", [], [])]


class InvalidGenerationTypeBackend(FakeBackend):
    def generate(self, lemma: str) -> list[GenerationRow]:
        return [(42, lemma, "subst:sg:gen:f", [], [])]


class IncompleteShapeBackend(FakeBackend):
    def analyse(self, text: str) -> list[AnalysisRow]:
        return [()]


class IncompleteInterpretationBackend(FakeBackend):
    def analyse(self, text: str) -> list[AnalysisRow]:
        return [(0, 1, ())]


class InvalidSpanBackend(FakeBackend):
    def analyse(self, text: str) -> list[AnalysisRow]:
        return [(1, 2, (text, "pomoc", "subst:sg:nom:f", [], []))]


class BooleanSpanBackend(FakeBackend):
    def analyse(self, text: str) -> list[AnalysisRow]:
        return [(False, 1, (text, "pomoc", "subst:sg:nom:f", [], []))]


def test_provider_matches_three_positives_and_abstains_on_six_negatives() -> None:
    dataset = load_qualification_dataset(DATASET, MANIFEST, require_reviewed=False)
    provider = MorfeuszProvider(
        backend=FakeBackend(),
        identity=ProviderIdentity(
            package_version="1.99.15",
            dictionary_id="pl.sgjp.sgjp-2026.06.01",
            dictionary_notice_sha256="84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393",
            installed_bytes=40_725_689,
        ),
    )

    outcomes = tuple(provider.evaluate(case) for case in dataset.cases)

    assert [outcome.form for outcome in outcomes[:3]] == [
        "pomocy",
        "samochodu",
        "nowa",
    ]
    assert all(outcome.kind == "abstain" for outcome in outcomes[3:])
    assert outcomes[5].reason == "ambiguous-source"
    assert outcomes[6].reason == "unknown-source"
    assert outcomes[8].reason == "incompatible-pos"


def test_provider_abstains_on_multiple_unfiltered_tags_for_one_lemma() -> None:
    provider = MorfeuszProvider(
        backend=FakeBackend(),
        identity=ProviderIdentity("1.99.15", "dictionary", "notice", 1),
    )
    case = QualificationCase(
        id="same_lemma_ambiguity",
        phenomenon="ambiguity",
        input_form="pomocy",
        source_lemma=None,
        source_pos=None,
        target_tag="subst:sg:gen:f",
        expected_outcome="abstain",
        expected_form=None,
    )

    outcome = provider.evaluate(case)

    assert outcome.reason == "ambiguous-source"


def test_provider_abstains_on_incomplete_external_rows() -> None:
    dataset = load_qualification_dataset(DATASET, MANIFEST, require_reviewed=False)
    identity = ProviderIdentity("1.99.15", "dictionary", "notice", 1)

    invalid_analysis = MorfeuszProvider(InvalidAnalysisBackend(), identity).evaluate(
        dataset.cases[0]
    )
    invalid_generation = MorfeuszProvider(
        InvalidGenerationBackend(), identity
    ).evaluate(dataset.cases[0])
    invalid_generation_type = MorfeuszProvider(
        InvalidGenerationTypeBackend(), identity
    ).evaluate(dataset.cases[0])
    incomplete_shape = MorfeuszProvider(IncompleteShapeBackend(), identity).evaluate(
        dataset.cases[0]
    )
    incomplete_interpretation = MorfeuszProvider(
        IncompleteInterpretationBackend(), identity
    ).evaluate(dataset.cases[0])
    invalid_span = MorfeuszProvider(InvalidSpanBackend(), identity).evaluate(
        dataset.cases[0]
    )
    boolean_span = MorfeuszProvider(BooleanSpanBackend(), identity).evaluate(
        dataset.cases[0]
    )

    assert invalid_analysis.reason == "invalid-analysis-schema"
    assert invalid_generation.reason == "invalid-generation-schema"
    assert invalid_generation_type.reason == "invalid-generation-schema"
    assert incomplete_shape.reason == "invalid-analysis-schema"
    assert incomplete_interpretation.reason == "invalid-analysis-schema"
    assert invalid_span.reason == "invalid-analysis-schema"
    assert boolean_span.reason == "invalid-analysis-schema"
