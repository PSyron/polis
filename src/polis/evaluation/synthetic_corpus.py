from __future__ import annotations

import importlib
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final, Literal, NotRequired, TypedDict, cast

from polis.evaluation._synthetic_corpus_candidates import (
    ErrorClass,
    MorphologyBackend,
    build_candidates,
    build_validated_candidates,
)
from polis.evaluation._synthetic_corpus_cli import run as _main
from polis.evaluation._synthetic_corpus_coverage import (
    CoverageReport,
    coverage_report,
)
from polis.evaluation._synthetic_corpus_distribution import (
    ERROR_CLASSES,
    ClassDistribution,
    punctuation_development_material,
    select_candidates,
)
from polis.evaluation._synthetic_corpus_sources import (
    SourceMetadata,
    SourceText,
    provided_source_texts,
    source_texts,
)
from polis.evaluation._synthetic_corpus_validation import (
    SourceDisjointSplit,
    assert_source_disjoint,
    split_source_disjoint,
)

GENERATOR_VERSION: Final = "polis-synthetic-corpus-v1"
VALIDATED_GENERATOR_VERSION: Final = "polis-synthetic-corpus-v2-validated"
DEFAULT_SEED: Final = 426
DEFAULT_COUNT: Final = 5000
VALIDATED_DEVELOPMENT_RATIO: Final = 0.8
VALIDATED_SPLIT_STRATEGY: Final = "source-disjoint"
type SyntheticProfile = Literal["legacy", "validated"]


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
    split: SourceDisjointSplit[SyntheticPair] | None = None
    split_report: SplitReport | None = None
    requested_class_distribution: dict[ErrorClass, int] | None = None

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


class SplitPartitionReport(TypedDict):
    pair_count: int
    class_counts: dict[ErrorClass, int]
    phenomenon_counts: dict[str, int]
    shape_strata_counts: dict[str, int]
    source_case_ids: list[str]
    correct_text_sha256: list[str]


class SplitReport(TypedDict):
    strategy: str
    development_ratio: float
    seed: int
    partitions: dict[str, SplitPartitionReport]


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
    split: NotRequired[SplitReport]
    requested_class_distribution: NotRequired[dict[ErrorClass, int]]
    obtained_class_distribution: NotRequired[dict[ErrorClass, int]]


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
    class_distribution: ClassDistribution | None = None,
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
        if class_distribution is not None and clean_texts is None:
            punctuation_sources, punctuation_candidates = (
                punctuation_development_material()
            )
            sources += punctuation_sources
            candidates += punctuation_candidates
    else:
        candidates = build_validated_candidates(sources)
    if count is None:
        requested_count = DEFAULT_COUNT if profile == "legacy" else len(candidates)
    else:
        requested_count = count
    selected = select_candidates(
        candidates,
        requested_count,
        seed,
        class_distribution,
    )
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
    coverage = coverage_report(sources, selected) if profile == "validated" else None
    split = (
        split_source_disjoint(
            pairs,
            development_ratio=VALIDATED_DEVELOPMENT_RATIO,
            seed=seed,
        )
        if profile == "validated"
        else None
    )
    if split is not None:
        assert_source_disjoint(split.development, split.test)
    split_report = _split_report(sources, split, seed) if split is not None else None
    return SyntheticCorpus(
        seed=seed,
        pairs=pairs,
        sources=metadata,
        profile=profile,
        coverage=coverage,
        split=split,
        split_report=split_report,
        requested_class_distribution=(
            dict(class_distribution) if class_distribution is not None else None
        ),
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
        if corpus.coverage is None or corpus.split_report is None:
            raise ValueError("validated corpus is missing validation metadata")
        manifest["profile"] = corpus.profile
        manifest["generator_version"] = VALIDATED_GENERATOR_VERSION
        manifest["coverage"] = corpus.coverage
        manifest["split"] = corpus.split_report
    if corpus.requested_class_distribution is not None:
        manifest["requested_class_distribution"] = corpus.requested_class_distribution
        manifest["obtained_class_distribution"] = corpus.class_counts
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


def _split_report(
    sources: Sequence[SourceText],
    split: SourceDisjointSplit[SyntheticPair],
    seed: int,
) -> SplitReport:
    source_by_key = {
        (source.metadata.dataset_id, source.case_id): source for source in sources
    }
    return SplitReport(
        strategy=VALIDATED_SPLIT_STRATEGY,
        development_ratio=VALIDATED_DEVELOPMENT_RATIO,
        seed=seed,
        partitions={
            "development": _split_partition_report(source_by_key, split.development),
            "test": _split_partition_report(source_by_key, split.test),
        },
    )


def _split_partition_report(
    source_by_key: dict[tuple[str, str], SourceText], pairs: Sequence[SyntheticPair]
) -> SplitPartitionReport:
    selected_sources = tuple(
        source_by_key[(pair.source_dataset, pair.source_case_id)] for pair in pairs
    )
    phenomena = Counter(source.phenomenon or "unknown" for source in selected_sources)
    strata = Counter(
        shape
        for source in selected_sources
        for shape in (source.shape_strata or frozenset({"unstratified"}))
    )
    return SplitPartitionReport(
        pair_count=len(pairs),
        class_counts={
            error_class: sum(pair.error_class == error_class for pair in pairs)
            for error_class in ERROR_CLASSES
        },
        phenomenon_counts=dict(sorted(phenomena.items())),
        shape_strata_counts=dict(sorted(strata.items())),
        source_case_ids=sorted({pair.source_case_id for pair in pairs}),
        correct_text_sha256=sorted(
            {sha256(pair.correct_text.encode("utf-8")).hexdigest() for pair in pairs}
        ),
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


if __name__ == "__main__":
    raise SystemExit(_main())
