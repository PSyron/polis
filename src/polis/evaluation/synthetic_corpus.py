"""Deterministic, checkout-only synthetic corruption corpus generator.

This module is intentionally excluded from wheel and sdist. It is development
tooling and must never become a runtime or holdout dependency.
"""

from __future__ import annotations

import argparse
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Final, Protocol, runtime_checkable

from polis.evaluation._synthetic_artifacts import (
    build_manifest_bytes,
    corpus_sha256,
    serialize_corpus,
    sha256_bytes,
    write_synthetic_artifacts,
)
from polis.evaluation._synthetic_candidates import Candidate, collect_candidates
from polis.evaluation._synthetic_types import (
    CorruptionClass,
    MorphologyAnalysis,
    MorphologyForm,
    MorphologyProvider,
    SyntheticArtifactPaths,
    SyntheticCorpus,
    SyntheticEdit,
    SyntheticGeneratorConfig,
    SyntheticPair,
)
from polis.rules._morfeusz import _QualifiedMorfeusz

GENERATOR_VERSION: Final[str] = "synthetic-corruption-v1"
_CLASSES: Final[tuple[CorruptionClass, ...]] = tuple(CorruptionClass)

__all__ = [
    "GENERATOR_VERSION",
    "CorruptionClass",
    "MorphologyAnalysis",
    "MorphologyForm",
    "MorphologyProvider",
    "SyntheticArtifactPaths",
    "SyntheticCorpus",
    "SyntheticEdit",
    "SyntheticGeneratorConfig",
    "SyntheticPair",
    "apply_edit",
    "build_manifest_bytes",
    "corpus_sha256",
    "generate_synthetic_corpus",
    "load_morfeusz_provider",
    "serialize_corpus",
    "validate_synthetic_corpus",
    "write_synthetic_artifacts",
]


def generate_synthetic_corpus(
    source_text: str,
    config: SyntheticGeneratorConfig,
    provider: MorphologyProvider | None = None,
) -> SyntheticCorpus:
    """Generate exactly ``config.pair_count`` safe, unique mutations."""

    if provider is None:
        provider = load_morfeusz_provider()
    candidates = collect_candidates(source_text, provider)
    if any(not candidates[category] for category in _CLASSES):
        raise ValueError("source has no safe candidate in every corruption class")
    total = sum(len(items) for items in candidates.values())
    if total < config.pair_count:
        raise ValueError(
            f"not enough safe candidates: requested {config.pair_count}, found {total}"
        )
    selected = _select_candidates(candidates, config.seed, config.pair_count)
    pairs = tuple(
        _materialize_pair(index, candidate, source_text)
        for index, candidate in enumerate(selected, start=1)
    )
    corpus = SyntheticCorpus(
        schema_version=1,
        generator_version=GENERATOR_VERSION,
        dataset_id=config.dataset_id,
        language="pl-PL",
        role="development-only",
        seed=config.seed,
        pair_count=len(pairs),
        source_name=config.source_name,
        source_license=config.source_license,
        source_notes=config.source_notes,
        source_sha256=sha256_bytes(source_text.encode("utf-8")),
        pairs=pairs,
    )
    validate_synthetic_corpus(corpus)
    return corpus


def load_morfeusz_provider() -> MorphologyProvider:
    """Load the already-qualified optional Morfeusz provider in the checkout."""

    from polis.rules._morfeusz import _load_qualified_morfeusz

    qualified = _load_qualified_morfeusz()
    if qualified is None:
        raise RuntimeError(
            "synthetic corpus generation requires the qualified morphology extra"
        )
    return _NormalizedMorfeuszProvider(_qualified_backend(qualified))


@runtime_checkable
class _RawMorfeuszBackend(Protocol):
    def analyse(self, text: str) -> Sequence[Sequence[str | Sequence[str]]]: ...

    def generate(self, lemma: str) -> Sequence[Sequence[str | Sequence[str]]]: ...


class _NormalizedMorfeuszProvider:
    def __init__(self, backend: _RawMorfeuszBackend) -> None:
        self._backend = backend

    def analyse(self, text: str) -> tuple[MorphologyAnalysis, ...]:
        rows = self._backend.analyse(text)
        result: list[MorphologyAnalysis] = []
        for row in rows:
            if len(row) < 3 or not isinstance(row[2], Sequence):
                continue
            payload = row[2]
            if isinstance(payload, str) or len(payload) < 3:
                continue
            surface, lemma, tag = payload[:3]
            if all(isinstance(item, str) for item in (surface, lemma, tag)):
                result.append(MorphologyAnalysis(surface, lemma, tag))
        return tuple(result)

    def generate(self, lemma: str) -> tuple[MorphologyForm, ...]:
        rows = self._backend.generate(lemma)
        result: list[MorphologyForm] = []
        for row in rows:
            if len(row) < 3:
                continue
            form, row_lemma, tag = row[:3]
            if all(isinstance(item, str) for item in (form, row_lemma, tag)):
                result.append(MorphologyForm(form, row_lemma, tag))
        return tuple(result)


def apply_edit(text: str, edit: SyntheticEdit) -> str:
    """Apply one exact half-open edit without changing any other character."""

    if not 0 <= edit.start <= edit.end <= len(text):
        raise ValueError("edit bounds are outside the supplied text")
    if text[edit.start : edit.end] != edit.original:
        raise ValueError("edit original does not match the supplied text")
    return text[: edit.start] + str(edit.suggestion) + text[edit.end :]


def validate_synthetic_corpus(corpus: SyntheticCorpus) -> None:
    """Check schema, class coverage, edit offsets, and every reversal."""

    if corpus.schema_version != 1 or corpus.role != "development-only":
        raise ValueError("synthetic corpus is not a development schema-v1 artifact")
    if corpus.pair_count != len(corpus.pairs) or corpus.pair_count < 4:
        raise ValueError("synthetic corpus pair count is inconsistent")
    if {pair.corruption_class for pair in corpus.pairs} != set(_CLASSES):
        raise ValueError("synthetic corpus must cover all corruption classes")
    if len({pair.id for pair in corpus.pairs}) != len(corpus.pairs):
        raise ValueError("synthetic corpus contains duplicate pair ids")
    source_text = corpus.pairs[0].clean_text
    if sha256_bytes(source_text.encode("utf-8")) != corpus.source_sha256:
        raise ValueError("source_sha256 does not match the clean source")
    for pair in corpus.pairs:
        if pair.edit.corruption_class is not pair.corruption_class:
            raise ValueError(f"pair {pair.id} has an edit class mismatch")
        if not 0 <= pair.edit.start <= pair.edit.end <= len(pair.corrupted_text):
            raise ValueError(f"pair {pair.id} has edit bounds outside corrupted text")
        if pair.clean_text != source_text:
            raise ValueError(f"pair {pair.id} has a different clean source")
        if pair.source_offset != pair.edit.start:
            raise ValueError(f"pair {pair.id} has a source offset mismatch")
        if not 0 <= pair.source_offset < len(pair.clean_text):
            raise ValueError(f"pair {pair.id} has an invalid source offset")
        if apply_edit(pair.corrupted_text, pair.edit) != pair.clean_text:
            raise ValueError(f"pair {pair.id} is not reversible")


def _select_candidates(
    candidates: dict[CorruptionClass, tuple[Candidate, ...]], seed: int, count: int
) -> tuple[Candidate, ...]:
    rng = random.Random(seed)
    buckets = {category: list(candidates[category]) for category in _CLASSES}
    for bucket in buckets.values():
        rng.shuffle(bucket)
    selected = [buckets[category].pop() for category in _CLASSES]
    remaining = [candidate for bucket in buckets.values() for candidate in bucket]
    rng.shuffle(remaining)
    selected.extend(remaining[: count - len(selected)])
    return tuple(selected)


def _materialize_pair(
    index: int, candidate: Candidate, source_text: str
) -> SyntheticPair:
    corrupted = (
        source_text[: candidate.clean_start]
        + candidate.corrupted_form
        + source_text[candidate.clean_end :]
    )
    corrupted_end = candidate.clean_start + len(candidate.corrupted_form)
    edit = SyntheticEdit(
        candidate.corruption_class,
        candidate.clean_start,
        corrupted_end,
        candidate.corrupted_form,
        candidate.clean_form,
    )
    return SyntheticPair(
        id=f"synthetic_{index:06d}",
        corruption_class=candidate.corruption_class,
        clean_text=source_text,
        corrupted_text=corrupted,
        edit=edit,
        source_offset=candidate.clean_start,
        source_lemma=candidate.source_lemma,
        generated_forms=candidate.generated_forms,
    )


def _qualified_backend(qualified: _QualifiedMorfeusz) -> _RawMorfeuszBackend:
    backend = qualified.backend
    if not isinstance(backend, _RawMorfeuszBackend):
        raise RuntimeError("qualified Morfeusz backend has an unsupported interface")
    return backend


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m polis.evaluation.synthetic_corpus")
    parser.add_argument("source", type=Path)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--pairs", type=int, default=5000)
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--source-license", required=True)
    parser.add_argument("--source-notes", required=True)
    args = parser.parse_args(argv)
    source_text = args.source.read_text(encoding="utf-8")
    config = SyntheticGeneratorConfig(
        seed=args.seed,
        pair_count=args.pairs,
        source_name=args.source_name,
        source_license=args.source_license,
        source_notes=args.source_notes,
    )
    corpus = generate_synthetic_corpus(source_text, config)
    write_synthetic_artifacts(
        corpus, SyntheticArtifactPaths(corpus=args.corpus, manifest=args.manifest)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
