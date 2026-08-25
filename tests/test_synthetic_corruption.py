from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import replace

import pytest

from polis.evaluation._synthetic_candidates import collect_candidates
from polis.evaluation.synthetic_corpus import (
    CorruptionClass,
    MorphologyAnalysis,
    MorphologyForm,
    SyntheticGeneratorConfig,
    apply_edit,
    build_manifest_bytes,
    corpus_sha256,
    generate_synthetic_corpus,
    load_morfeusz_provider,
    validate_synthetic_corpus,
)


class _FakeMorphology:
    def __init__(self) -> None:
        self.generated_lemmas: list[str] = []

    def analyse(self, text: str) -> Sequence[MorphologyAnalysis]:
        analyses = {
            "widzę": (MorphologyAnalysis("widzę", "widzieć", "fin:sg:pri"),),
            "kota": (MorphologyAnalysis("kota", "kot", "subst:sg:gen.acc:m1"),),
            "czerwony": (
                MorphologyAnalysis("czerwony", "czerwony", "adj:sg:nom:m1.m2.m3:pos"),
            ),
            "kot": (MorphologyAnalysis("kot", "kot", "subst:sg:nom:m1"),),
            "płynie": (MorphologyAnalysis("płynie", "płynąć", "fin:sg:ter"),),
            "łódź": (MorphologyAnalysis("łódź", "łódź", "subst:sg:nom:f"),),
            "a": (MorphologyAnalysis("a", "a", "conj"),),
        }
        return analyses.get(text, ())

    def generate(self, lemma: str) -> Sequence[MorphologyForm]:
        self.generated_lemmas.append(lemma)
        forms = {
            "kot": (
                MorphologyForm("kot", "kot", "subst:sg:nom:m1"),
                MorphologyForm("kota", "kot", "subst:sg:gen.acc:m1"),
                MorphologyForm("kotem", "kot", "subst:sg:inst:m1"),
            ),
            "czerwony": (
                MorphologyForm("czerwony", "czerwony", "adj:sg:nom:m1.m2.m3:pos"),
                MorphologyForm("czerwona", "czerwony", "adj:sg:nom:f:pos"),
                MorphologyForm("czerwone", "czerwony", "adj:pl:nom:m2.m3.f.n:pos"),
            ),
        }
        return forms.get(lemma, ())


class _FeatureMorphology:
    def analyse(self, text: str) -> Sequence[MorphologyAnalysis]:
        analyses = {
            "kota": (MorphologyAnalysis("kota", "kot", "subst:sg:gen.acc:m1"),),
            "ładny": (MorphologyAnalysis("ładny", "ładny", "adj:sg:nom:m1.m2.m3:pos"),),
            "ładna": (MorphologyAnalysis("ładna", "ładny", "adj:sg:nom:f:pos"),),
            "kot": (MorphologyAnalysis("kot", "kot", "subst:sg:nom:m1"),),
        }
        return analyses.get(text, ())

    def generate(self, lemma: str) -> Sequence[MorphologyForm]:
        forms = {
            "kot": (
                MorphologyForm("kot", "kot", "subst:sg:nom:m1"),
                MorphologyForm("kotem", "kot", "subst:sg:inst:m1"),
            ),
            "ładny": (
                MorphologyForm("ładny", "ładny", "adj:sg:nom:m1.m2.m3:pos"),
                MorphologyForm("ładna", "ładny", "adj:sg:nom:f:pos"),
            ),
        }
        return forms.get(lemma, ())


def _source_text() -> str:
    return " ".join(
        "Widzę kota, czerwony kot płynie, a łódź czeka.".casefold() for _ in range(4)
    )


def _config(pair_count: int = 8) -> SyntheticGeneratorConfig:
    return SyntheticGeneratorConfig(
        seed=426,
        pair_count=pair_count,
        source_name="tests/synthetic-source.txt",
        source_license="CC0-1.0",
        source_notes="Autorski tekst testowy utworzony wyłącznie na potrzeby testu.",
    )


def test_same_seed_produces_same_canonical_sha256() -> None:
    first = generate_synthetic_corpus(_source_text(), _config(), _FakeMorphology())
    second = generate_synthetic_corpus(_source_text(), _config(), _FakeMorphology())

    assert corpus_sha256(first) == corpus_sha256(second)


def test_corpus_covers_all_classes_and_is_reversible() -> None:
    corpus = generate_synthetic_corpus(_source_text(), _config(), _FakeMorphology())

    validate_synthetic_corpus(corpus)
    assert {pair.corruption_class for pair in corpus.pairs} == {
        CorruptionClass.MORPHOLOGY_CASE,
        CorruptionClass.AGREEMENT_NUMBER_OR_GENDER,
        CorruptionClass.REMOVED_COMMA,
        CorruptionClass.REMOVED_DIACRITIC,
    }
    for pair in corpus.pairs:
        assert apply_edit(pair.corrupted_text, pair.edit) == pair.clean_text


def test_morphology_case_forms_come_from_generate_for_the_same_lemma() -> None:
    provider = _FakeMorphology()
    corpus = generate_synthetic_corpus(_source_text(), _config(), provider)

    morphology_pairs = [
        pair
        for pair in corpus.pairs
        if pair.corruption_class is CorruptionClass.MORPHOLOGY_CASE
    ]
    assert morphology_pairs
    assert all(
        pair.corrupted_text[pair.edit.start : pair.edit.end] in pair.generated_forms
        for pair in morphology_pairs
    )
    assert set(pair.source_lemma for pair in morphology_pairs) <= {
        "kot",
    }
    assert "kot" in provider.generated_lemmas


def test_generator_fails_closed_when_source_cannot_reach_requested_size() -> None:
    with pytest.raises(ValueError, match="not enough safe candidates"):
        generate_synthetic_corpus(
            _source_text(),
            _config(pair_count=5000),
            _FakeMorphology(),
        )


def test_morphology_filters_split_tags_and_requires_actual_disagreement() -> None:
    provider = _FeatureMorphology()

    candidates = collect_candidates("kota ładny kot, łódź", provider)

    case_candidates = candidates[CorruptionClass.MORPHOLOGY_CASE]
    assert {candidate.corrupted_form for candidate in case_candidates} == {
        "kotem",
        "kot",
    }
    assert candidates[CorruptionClass.AGREEMENT_NUMBER_OR_GENDER]

    unsafe_source = collect_candidates("kota ładna kot, łódź", provider)
    assert not unsafe_source[CorruptionClass.AGREEMENT_NUMBER_OR_GENDER]


def test_generator_reaches_five_thousand_without_repeating_candidates() -> None:
    corpus = generate_synthetic_corpus(
        _source_text() * 700,
        _config(pair_count=5000),
        _FakeMorphology(),
    )

    signatures = {
        (pair.corrupted_text, pair.edit.start, pair.edit.end, pair.source_offset)
        for pair in corpus.pairs
    }
    assert len(corpus.pairs) == 5000
    assert len(signatures) == 5000


def test_qualified_morfeusz_provider_supports_all_classes() -> None:
    corpus = generate_synthetic_corpus(
        "Widzę kota, czerwony kot płynie, a łódź czeka.",
        _config(pair_count=4),
        load_morfeusz_provider(),
    )

    assert {pair.corruption_class for pair in corpus.pairs} == set(CorruptionClass)


def test_manifest_binds_result_and_class_distribution() -> None:
    corpus = generate_synthetic_corpus(_source_text(), _config(), _FakeMorphology())

    manifest = json.loads(build_manifest_bytes(corpus))

    assert manifest["corpus_sha256"] == corpus_sha256(corpus)
    assert manifest["pair_count"] == 8
    assert manifest["class_counts"] == {
        "agreement_number_or_gender": 2,
        "morphology_case": 1,
        "removed_comma": 2,
        "removed_diacritic": 3,
    }
    assert manifest["source"] == {
        "name": "tests/synthetic-source.txt",
        "license": "CC0-1.0",
        "notes": "Autorski tekst testowy utworzony wyłącznie na potrzeby testu.",
        "sha256": hashlib.sha256(_source_text().encode("utf-8")).hexdigest(),
    }


def test_validation_rejects_edit_with_wrong_class() -> None:
    corpus = generate_synthetic_corpus(_source_text(), _config(), _FakeMorphology())
    pair = corpus.pairs[0]
    invalid_pair = replace(
        pair,
        edit=replace(
            pair.edit,
            corruption_class=(
                CorruptionClass.REMOVED_COMMA
                if pair.edit.corruption_class is not CorruptionClass.REMOVED_COMMA
                else CorruptionClass.MORPHOLOGY_CASE
            ),
        ),
    )
    invalid_corpus = replace(corpus, pairs=(invalid_pair, *corpus.pairs[1:]))

    with pytest.raises(ValueError, match="edit class"):
        validate_synthetic_corpus(invalid_corpus)


def test_validation_rejects_edit_outside_corrupted_text() -> None:
    corpus = generate_synthetic_corpus(_source_text(), _config(), _FakeMorphology())
    pair = corpus.pairs[0]
    invalid_pair = replace(
        pair,
        source_offset=len(pair.corrupted_text),
        edit=replace(
            pair.edit,
            start=len(pair.corrupted_text),
            end=len(pair.corrupted_text) + 1,
            original="",
            suggestion="",
        ),
    )
    invalid_corpus = replace(corpus, pairs=(invalid_pair, *corpus.pairs[1:]))

    with pytest.raises(ValueError, match="edit bounds"):
        validate_synthetic_corpus(invalid_corpus)


def test_validation_rejects_source_hash_or_offset_mismatch() -> None:
    corpus = generate_synthetic_corpus(_source_text(), _config(), _FakeMorphology())
    pair = corpus.pairs[0]
    invalid_pair = replace(pair, source_offset=pair.source_offset + 1)
    invalid_corpus = replace(
        corpus,
        source_sha256="0" * 64,
        pairs=(invalid_pair, *corpus.pairs[1:]),
    )

    with pytest.raises(ValueError, match="source_sha256"):
        validate_synthetic_corpus(invalid_corpus)
