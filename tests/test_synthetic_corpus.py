from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast

import pytest

from polis.evaluation._synthetic_corpus_candidates import _agreement_mismatch
from polis.evaluation.synthetic_corpus import (
    DEFAULT_COUNT,
    ERROR_CLASSES,
    GENERATOR_VERSION,
    build_manifest,
    generate,
    serialize_corpus,
    write_artifacts,
)

_CASE_FEATURES = frozenset({"nom", "gen", "dat", "acc", "inst", "loc", "voc"})


def _tag_features(tag: str) -> frozenset[str]:
    return frozenset(part for token in tag.split(":") for part in token.split("."))


def test_generate_is_deterministic_for_the_same_seed() -> None:
    first = serialize_corpus(generate(seed=426, count=64))
    second = serialize_corpus(generate(seed=426, count=64))

    assert first == second
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()


def test_generate_default_corpus_has_at_least_five_thousand_pairs() -> None:
    corpus = generate(seed=426)

    assert DEFAULT_COUNT >= 5000
    assert len(corpus.pairs) == DEFAULT_COUNT


def test_every_generated_pair_is_reversible() -> None:
    corpus = generate(seed=426)

    for pair in corpus.pairs:
        repaired = (
            pair.incorrect_text[: pair.start]
            + pair.suggestion
            + pair.incorrect_text[pair.end :]
        )
        assert repaired == pair.correct_text
        assert pair.incorrect_text[pair.start : pair.end] == pair.original


def test_generated_corpus_covers_all_four_error_classes() -> None:
    corpus = generate(seed=426, count=256)

    assert {pair.error_class for pair in corpus.pairs} == set(ERROR_CLASSES)
    assert set(corpus.class_counts) == set(ERROR_CLASSES)
    assert sum(corpus.class_counts.values()) == len(corpus.pairs)


def test_case_corruptions_are_direct_morfeusz_generation_results() -> None:
    morfeusz2 = pytest.importorskip("morfeusz2")
    backend = morfeusz2.Morfeusz()
    corpus = generate(seed=426, count=128)

    case_pairs = [pair for pair in corpus.pairs if pair.error_class == "case"]
    assert case_pairs
    for pair in case_pairs:
        assert pair.lemma is not None
        generated = {
            row[0]
            for row in backend.generate(pair.lemma)
            if len(row) >= 3 and isinstance(row[0], str)
        }
        assert pair.original in generated


def test_case_corruptions_change_only_the_noun_case() -> None:
    morfeusz2 = pytest.importorskip("morfeusz2")
    backend = morfeusz2.Morfeusz()
    corpus = generate(seed=426, count=512)

    for pair in corpus.pairs:
        if pair.error_class != "case":
            continue
        source_tags = [
            row[2][2]
            for row in backend.analyse(pair.suggestion)
            if len(row) >= 3
            and isinstance(row[2], tuple)
            and len(row[2]) >= 3
            and row[2][1] == pair.lemma
            and isinstance(row[2][2], str)
            and row[2][2].startswith("subst:")
        ]
        assert pair.generated_tag is not None
        generated_features = _tag_features(pair.generated_tag)
        assert any(
            (_tag_features(source_tag) & _CASE_FEATURES).isdisjoint(
                generated_features & _CASE_FEATURES
            )
            and _tag_features(source_tag) - _CASE_FEATURES
            == generated_features - _CASE_FEATURES
            for source_tag in source_tags
        )


def test_agreement_corruption_rejects_any_compatible_ambiguous_noun_analysis() -> None:
    assert not _agreement_mismatch(
        "adj:sg:acc:f:com",
        ("subst:sg:gen:f", "subst:pl:nom.acc.voc:f"),
    )


def test_generate_accepts_clean_texts_with_explicit_provenance() -> None:
    corpus = generate(
        clean_texts=("Dobry dom, żółć.",),
        source_license="CC0-1.0",
        source_origin="test-authored",
        seed=426,
        count=4,
    )

    assert len(corpus.pairs) == 4
    assert corpus.sources[0].source == "test-authored"
    assert corpus.sources[0].license == "CC0-1.0"


@pytest.mark.parametrize(
    ("source_license", "source_origin"),
    ((["CC0-1.0"], "test-authored"), ("CC0-1.0", ["test-authored"])),
)
def test_generate_rejects_non_string_provenance(
    source_license: object, source_origin: object
) -> None:
    with pytest.raises(ValueError, match="source license and source origin"):
        generate(
            clean_texts=("Dobry dom, żółć.",),
            source_license=cast(str, source_license),
            source_origin=cast(str, source_origin),
            seed=426,
            count=4,
        )


def test_manifest_binds_artifact_digest_and_cc0_sources(tmp_path: Path) -> None:
    corpus = generate(seed=426, count=64)
    corpus_path = tmp_path / "cases.jsonl"
    manifest_path = tmp_path / "manifest.json"

    manifest = write_artifacts(corpus, corpus_path, manifest_path)
    artifact_bytes = corpus_path.read_bytes()
    raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["generator_version"] == GENERATOR_VERSION
    assert manifest["pair_count"] == len(corpus.pairs)
    assert manifest["artifact_sha256"] == hashlib.sha256(artifact_bytes).hexdigest()
    assert raw_manifest["artifact_sha256"] == manifest["artifact_sha256"]
    assert all(source["license"] == "CC0-1.0" for source in manifest["sources"])
    assert all(source["source"] == "project-authored" for source in manifest["sources"])
    assert manifest["holdout"] is False


def test_build_manifest_does_not_omit_class_distribution() -> None:
    corpus = generate(seed=426, count=64)

    manifest = build_manifest(corpus, artifact_sha256="a" * 64)

    assert manifest["class_counts"] == corpus.class_counts
    assert manifest["seed"] == 426


def test_generated_artifacts_are_not_committed_to_runtime_repository() -> None:
    root = Path(__file__).resolve().parents[1]
    artifact_path = root / "src/polis/evaluation/datasets/synthetic_v1/cases.jsonl"
    manifest_path = root / "src/polis/evaluation/datasets/synthetic_v1/manifest.json"

    assert not artifact_path.exists()
    assert not manifest_path.exists()
