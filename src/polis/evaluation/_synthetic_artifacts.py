"""Canonical serialization and manifest writing for synthetic corpus artifacts."""

from __future__ import annotations

import hashlib
import json
from collections import Counter

from polis.evaluation._synthetic_types import (
    JsonValue,
    SyntheticArtifactPaths,
    SyntheticCorpus,
)


def serialize_corpus(corpus: SyntheticCorpus) -> bytes:
    """Return canonical UTF-8 JSON bytes for the corpus data file."""

    return _canonical_json(_corpus_payload(corpus))


def corpus_sha256(corpus: SyntheticCorpus) -> str:
    """Return the SHA-256 of the exact canonical corpus bytes."""

    return sha256_bytes(serialize_corpus(corpus))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_manifest_bytes(corpus: SyntheticCorpus) -> bytes:
    """Return canonical manifest bytes binding source, parameters, and result."""

    counts = Counter(pair.corruption_class.value for pair in corpus.pairs)
    payload: dict[str, JsonValue] = {
        "schema_id": "polis.synthetic-corruption-manifest",
        "schema_version": 1,
        "generator_version": corpus.generator_version,
        "dataset_id": corpus.dataset_id,
        "role": corpus.role,
        "language": corpus.language,
        "seed": corpus.seed,
        "pair_count": corpus.pair_count,
        "parameters": {"seed": corpus.seed, "pair_count": corpus.pair_count},
        "class_counts": dict(sorted(counts.items())),
        "source": {
            "name": corpus.source_name,
            "license": corpus.source_license,
            "notes": corpus.source_notes,
            "sha256": corpus.source_sha256,
        },
        "corpus_sha256": corpus_sha256(corpus),
    }
    return _canonical_json(payload)


def write_synthetic_artifacts(
    corpus: SyntheticCorpus, paths: SyntheticArtifactPaths
) -> None:
    """Write corpus and manifest files for local development use."""

    paths.corpus.parent.mkdir(parents=True, exist_ok=True)
    paths.manifest.parent.mkdir(parents=True, exist_ok=True)
    paths.corpus.write_bytes(serialize_corpus(corpus))
    paths.manifest.write_bytes(build_manifest_bytes(corpus))


def _corpus_payload(corpus: SyntheticCorpus) -> dict[str, JsonValue]:
    return {
        "schema_id": "polis.synthetic-corruption-corpus",
        "schema_version": corpus.schema_version,
        "generator_version": corpus.generator_version,
        "dataset_id": corpus.dataset_id,
        "language": corpus.language,
        "role": corpus.role,
        "seed": corpus.seed,
        "pair_count": corpus.pair_count,
        "source": {
            "name": corpus.source_name,
            "license": corpus.source_license,
            "notes": corpus.source_notes,
            "sha256": corpus.source_sha256,
        },
        "pairs": [
            {
                "id": pair.id,
                "corruption_class": pair.corruption_class.value,
                "clean_text": pair.clean_text,
                "corrupted_text": pair.corrupted_text,
                "source_offset": pair.source_offset,
                "edit": {
                    "start": pair.edit.start,
                    "end": pair.edit.end,
                    "original": pair.edit.original,
                    "suggestion": pair.edit.suggestion,
                },
                "source_lemma": pair.source_lemma,
                "generated_forms": list(pair.generated_forms),
            }
            for pair in corpus.pairs
        ],
    }


def _canonical_json(payload: dict[str, JsonValue]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
