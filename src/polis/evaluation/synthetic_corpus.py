from __future__ import annotations

import argparse
import importlib
import json
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final, Literal, NotRequired, TypedDict, cast

from polis.evaluation._synthetic_corpus_candidates import (
    Candidate,
    ErrorClass,
    MorphologyBackend,
    _validated_rejection_reason,
    build_candidates,
    build_validated_candidates,
)
from polis.evaluation._synthetic_corpus_sources import (
    SourceMetadata,
    SourceText,
    provided_source_texts,
    source_texts,
)

GENERATOR_VERSION: Final = "polis-synthetic-corpus-v1"
VALIDATED_GENERATOR_VERSION: Final = "polis-synthetic-corpus-v2-validated"
DEFAULT_SEED: Final = 426
DEFAULT_COUNT: Final = 5000
type SyntheticProfile = Literal["legacy", "validated"]
ERROR_CLASSES: Final[tuple[ErrorClass, ...]] = (
    "case",
    "agreement",
    "punctuation",
    "diacritics",
)


@dataclass(frozen=True, slots=True)
class SyntheticPair:
    id: str
    error_class: ErrorClass
    incorrect_text: str
    correct_text: str
    start: int
    end: int
    original: str
    suggestion: str
    source_dataset: str
    source_case_id: str
    lemma: str | None = None
    generated_tag: str | None = None


@dataclass(frozen=True, slots=True)
class SyntheticCorpus:
    seed: int
    pairs: tuple[SyntheticPair, ...]
    sources: tuple[SourceMetadata, ...]
    profile: SyntheticProfile = "legacy"
    coverage: CoverageReport | None = None

    @property
    def class_counts(self) -> dict[ErrorClass, int]:
        counts = Counter(pair.error_class for pair in self.pairs)
        return {
            error_class: counts.get(error_class, 0) for error_class in ERROR_CLASSES
        }


class SourceManifest(TypedDict):
    dataset_id: str
    dataset_version: int
    path: str
    sha256: str
    license: str
    source: str
    clean_case_count: int


class CoverageReport(TypedDict):
    phenomenon_counts: dict[str, int]
    shape_strata_counts: dict[str, int]
    hard_negative_count: int
    rejected_counts: dict[str, int]


class Manifest(TypedDict):
    schema_id: str
    schema_version: int
    profile: NotRequired[SyntheticProfile]
    generator_version: str
    seed: int
    requested_count: int
    pair_count: int
    class_counts: dict[ErrorClass, int]
    artifact_sha256: str
    license: str
    source: str
    purpose: str
    holdout: bool
    sources: list[SourceManifest]
    coverage: NotRequired[CoverageReport]


def generate(
    *,
    clean_texts: str | Sequence[str] | None = None,
    source_license: str | None = None,
    source_origin: str | None = None,
    seed: int = DEFAULT_SEED,
    count: int | None = None,
    root: Path | None = None,
    backend: MorphologyBackend | None = None,
    profile: SyntheticProfile = "legacy",
) -> SyntheticCorpus:
    if profile not in {"legacy", "validated"}:
        raise ValueError("profile must be legacy or validated")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("seed must be a non-negative integer")
    if count is not None and (
        isinstance(count, bool)
        or not isinstance(count, int)
        or count < len(ERROR_CLASSES)
    ):
        raise ValueError(f"count must be at least {len(ERROR_CLASSES)}")
    if clean_texts is None:
        if source_license is not None or source_origin is not None:
            raise ValueError("source license and source origin require clean_texts")
        project_root = root or Path(__file__).resolve().parents[3]
        sources = source_texts(project_root)
    else:
        if source_license is None or source_origin is None:
            raise ValueError(
                "source license and source origin are required for clean_texts"
            )
        sources = provided_source_texts(
            clean_texts,
            license_name=source_license,
            source_name=source_origin,
        )
    if profile == "legacy":
        morphology = backend or _load_morfeusz()
        candidates = build_candidates(sources, morphology)
    else:
        candidates = build_validated_candidates(sources)
    if count is None:
        requested_count = DEFAULT_COUNT if profile == "legacy" else len(candidates)
    else:
        requested_count = count
    selected = _select_candidates(candidates, requested_count, seed)
    pair_prefix = (
        "synthetic_426" if profile == "legacy" else f"synthetic_{profile}_{seed}"
    )
    pairs = tuple(
        SyntheticPair(id=f"{pair_prefix}_{index:05d}", **asdict(candidate))
        for index, candidate in enumerate(selected, start=1)
    )
    metadata = tuple(
        sorted({source.metadata for source in sources}, key=lambda item: item.path)
    )
    coverage = _coverage_report(sources, selected) if profile == "validated" else None
    return SyntheticCorpus(
        seed=seed,
        pairs=pairs,
        sources=metadata,
        profile=profile,
        coverage=coverage,
    )


def serialize_corpus(corpus: SyntheticCorpus) -> bytes:
    lines = []
    for pair in corpus.pairs:
        record = asdict(pair)
        lines.append(
            json.dumps(
                record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            + "\n"
        )
    return "".join(lines).encode("utf-8")


def build_manifest(corpus: SyntheticCorpus, *, artifact_sha256: str) -> Manifest:
    licenses = {source.license for source in corpus.sources}
    sources = {source.source for source in corpus.sources}
    manifest = Manifest(
        schema_id="polis.synthetic-corpus-manifest",
        schema_version=1,
        generator_version=GENERATOR_VERSION,
        seed=corpus.seed,
        requested_count=len(corpus.pairs),
        pair_count=len(corpus.pairs),
        class_counts=corpus.class_counts,
        artifact_sha256=artifact_sha256,
        license=next(iter(licenses)) if len(licenses) == 1 else "mixed",
        source=next(iter(sources)) if len(sources) == 1 else "mixed",
        purpose="repeatable-development-only",
        holdout=False,
        sources=[_source_manifest(source) for source in corpus.sources],
    )
    if corpus.profile == "validated":
        if corpus.coverage is None:
            raise ValueError("validated corpus is missing coverage report")
        manifest["profile"] = corpus.profile
        manifest["generator_version"] = VALIDATED_GENERATOR_VERSION
        manifest["coverage"] = corpus.coverage
    return manifest


def write_artifacts(
    corpus: SyntheticCorpus, corpus_path: Path, manifest_path: Path
) -> Manifest:
    artifact = serialize_corpus(corpus)
    digest = sha256(artifact).hexdigest()
    manifest = build_manifest(corpus, artifact_sha256=digest)
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    corpus_path.write_bytes(artifact)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def _select_candidates(
    candidates: Sequence[Candidate], count: int, seed: int
) -> tuple[Candidate, ...]:
    pools: dict[ErrorClass, list[Candidate]] = {
        error_class: sorted(
            (
                candidate
                for candidate in candidates
                if candidate.error_class == error_class
            ),
            key=lambda item: item.key,
        )
        for error_class in ERROR_CLASSES
    }
    if any(not pool for pool in pools.values()):
        missing = [error_class for error_class, pool in pools.items() if not pool]
        raise ValueError(f"synthetic source cannot cover classes: {', '.join(missing)}")
    if count > len(candidates):
        raise ValueError(
            f"requested {count} pairs but only {len(candidates)} unique pairs exist"
        )
    randomizer = random.Random(seed)
    for pool in pools.values():
        randomizer.shuffle(pool)
    quotas = _quotas(
        {error_class: len(pool) for error_class, pool in pools.items()}, count
    )
    selected = [
        candidate
        for error_class in ERROR_CLASSES
        for candidate in pools[error_class][: quotas[error_class]]
    ]
    randomizer.shuffle(selected)
    return tuple(selected)


def _quotas(capacities: dict[ErrorClass, int], count: int) -> dict[ErrorClass, int]:
    total_capacity = sum(capacities.values())
    quotas = {
        error_class: max(1, count * capacity // total_capacity)
        for error_class, capacity in capacities.items()
    }
    while sum(quotas.values()) < count:
        candidates = [
            error_class
            for error_class in ERROR_CLASSES
            if quotas[error_class] < capacities[error_class]
        ]
        selected = max(
            candidates,
            key=lambda error_class: (
                capacities[error_class] / quotas[error_class],
                -ERROR_CLASSES.index(error_class),
            ),
        )
        quotas[selected] += 1
    while sum(quotas.values()) > count:
        selected = max(
            (error_class for error_class in ERROR_CLASSES if quotas[error_class] > 1),
            key=lambda error_class: quotas[error_class],
        )
        quotas[selected] -= 1
    return quotas


def _source_manifest(source: SourceMetadata) -> SourceManifest:
    return SourceManifest(
        dataset_id=source.dataset_id,
        dataset_version=source.dataset_version,
        path=source.path,
        sha256=source.sha256,
        license=source.license,
        source=source.source,
        clean_case_count=source.clean_case_count,
    )


def _coverage_report(
    sources: Sequence[SourceText], selected: Sequence[Candidate]
) -> CoverageReport:
    source_by_key = {
        (source.metadata.dataset_id, source.case_id): source for source in sources
    }
    selected_sources = [
        source_by_key[(candidate.source_dataset, candidate.source_case_id)]
        for candidate in selected
    ]
    phenomena = Counter(source.phenomenon or "unknown" for source in selected_sources)
    strata = Counter(
        shape
        for source in selected_sources
        for shape in (source.shape_strata or frozenset({"unstratified"}))
    )
    rejected = Counter(
        reason
        for source in sources
        if (reason := _validated_rejection_reason(source)) is not None
    )
    return CoverageReport(
        phenomenon_counts=dict(sorted(phenomena.items())),
        shape_strata_counts=dict(sorted(strata.items())),
        hard_negative_count=rejected.get("no_controlled_pair", 0),
        rejected_counts=dict(sorted(rejected.items())),
    )


def _load_morfeusz() -> MorphologyBackend:
    try:
        module = importlib.import_module("morfeusz2")
    except ImportError as error:
        raise RuntimeError(
            "issue #426 requires the optional 'morphology' extra (morfeusz2==1.99.15)"
        ) from error
    factory = module.__dict__.get("Morfeusz")
    if not callable(factory):
        raise RuntimeError("morfeusz2 does not expose Morfeusz")
    return cast(MorphologyBackend, factory())


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--profile", choices=("legacy", "validated"), default="legacy")
    args = parser.parse_args()
    corpus = generate(
        seed=args.seed,
        count=args.count,
        profile=cast(SyntheticProfile, args.profile),
    )
    manifest = write_artifacts(corpus, args.output, args.manifest)
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
