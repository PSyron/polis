from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import cast

import pytest

from polis.evaluation._synthetic_corpus_candidates import _agreement_mismatch
from polis.evaluation._synthetic_corpus_sources import (
    protected_spans,
    source_texts,
)
from polis.evaluation._synthetic_corpus_validation import (
    assert_source_disjoint,
    validate_single_edit,
)
from polis.evaluation.synthetic_corpus import (
    DEFAULT_COUNT,
    ERROR_CLASSES,
    GENERATOR_VERSION,
    VALIDATED_GENERATOR_VERSION,
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


def test_legacy_default_corpus_bytes_are_unchanged() -> None:
    artifact = serialize_corpus(generate(seed=426, count=5000))

    assert hashlib.sha256(artifact).hexdigest() == (
        "d1cd75a9289b12d6913ff4f9912d27f83936ce29bb743a5c13e23796b7d7b1d0"
    )


def test_validated_profile_uses_reviewed_controlled_pairs() -> None:
    corpus = generate(profile="validated", seed=426)

    assert corpus.profile == "validated"
    assert {pair.error_class for pair in corpus.pairs} == set(ERROR_CLASSES)
    assert all(
        validate_single_edit(
            pair.incorrect_text,
            pair.correct_text,
            start=pair.start,
            end=pair.end,
            original=pair.original,
            suggestion=pair.suggestion,
        )
        for pair in corpus.pairs
    )
    assert all("Cytat" not in pair.incorrect_text for pair in corpus.pairs)
    assert all("`" not in pair.incorrect_text for pair in corpus.pairs)


def test_validated_agreement_pairs_are_explicitly_qualified() -> None:
    corpus = generate(profile="validated", seed=426)

    assert {
        (pair.original, pair.suggestion)
        for pair in corpus.pairs
        if pair.error_class == "agreement"
    } == {("nowy", "nowa"), ("czyta", "czytają")}


def test_validated_manifest_reports_a_deterministic_source_disjoint_split() -> None:
    corpus = generate(profile="validated", seed=426)
    manifest = build_manifest(corpus, artifact_sha256="a" * 64)

    assert corpus.split is not None
    assert corpus.split_report is not None
    assert_source_disjoint(corpus.split.development, corpus.split.test)
    assert corpus.split.development
    assert corpus.split.test
    split = manifest["split"]
    assert split == corpus.split_report
    assert split["strategy"] == "source-disjoint"
    assert split["development_ratio"] == 0.8
    assert split["seed"] == 426
    source_by_case_id = {
        source.case_id: source
        for source in source_texts(Path(__file__).resolve().parents[1])
    }
    for name, partition in (
        ("development", corpus.split.development),
        ("test", corpus.split.test),
    ):
        report = split["partitions"][name]
        partition_sources = tuple(
            source_by_case_id[pair.source_case_id] for pair in partition
        )
        assert report["pair_count"] == len(partition)
        assert report["class_counts"] == {
            error_class: sum(pair.error_class == error_class for pair in partition)
            for error_class in ERROR_CLASSES
        }
        assert report["phenomenon_counts"] == dict(
            sorted(
                Counter(
                    source.phenomenon or "unknown" for source in partition_sources
                ).items()
            )
        )
        assert report["shape_strata_counts"] == dict(
            sorted(
                Counter(
                    shape
                    for source in partition_sources
                    for shape in (source.shape_strata or frozenset({"unstratified"}))
                ).items()
            )
        )
        assert report["source_case_ids"] == sorted(
            {pair.source_case_id for pair in partition}
        )
        assert report["correct_text_sha256"] == sorted(
            {
                hashlib.sha256(pair.correct_text.encode("utf-8")).hexdigest()
                for pair in partition
            }
        )


def test_source_metadata_exposes_protected_literal_spans() -> None:
    root = Path(__file__).resolve().parents[1]
    source = next(
        item
        for item in source_texts(root)
        if item.case_id == "v4_agreement_negative_11"
    )

    spans = protected_spans(source.text)

    assert spans
    assert source.protected_spans == spans
    assert source.expected_findings == ()
    assert any(source.text[span.start : span.end].startswith("„") for span in spans)


def test_validated_profile_rejects_inconsistent_and_protected_pairs() -> None:
    root = Path(__file__).resolve().parents[1]
    sources = source_texts(root)

    inconsistent = next(
        item for item in sources if item.case_id == "v4_syntax_negative_02"
    )
    quoted = next(
        item for item in sources if item.case_id == "v4_agreement_negative_11"
    )

    assert inconsistent.controlled_error is None
    assert inconsistent.paired_error is not None
    assert quoted.controlled_error is not None
    assert quoted.shape_strata == frozenset({"quotation-or-literal"})


def test_validated_manifest_is_versioned_separately() -> None:
    corpus = generate(profile="validated", seed=426)

    manifest = build_manifest(corpus, artifact_sha256="a" * 64)

    assert manifest["profile"] == "validated"
    assert manifest["generator_version"] == VALIDATED_GENERATOR_VERSION
    assert manifest["holdout"] is False
    assert manifest["coverage"]["phenomenon_counts"]
    assert manifest["coverage"]["shape_strata_counts"]
    assert manifest["coverage"]["hard_negative_count"] > 0
    assert manifest["coverage"]["rejected_counts"]["no_controlled_pair"] > 0


def test_legacy_manifest_shape_is_unchanged() -> None:
    manifest = build_manifest(generate(seed=426, count=64), artifact_sha256="a" * 64)

    assert "profile" not in manifest
    assert "coverage" not in manifest
    assert "split" not in manifest


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
