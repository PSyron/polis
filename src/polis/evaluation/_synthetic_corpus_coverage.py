from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Protocol, TypedDict

from polis.evaluation._synthetic_corpus_candidates import (
    _validated_rejection_reason,
)
from polis.evaluation._synthetic_corpus_sources import SourceText


class _CoverageCandidate(Protocol):
    source_dataset: str
    source_case_id: str


class CoverageReport(TypedDict):
    phenomenon_counts: dict[str, int]
    shape_strata_counts: dict[str, int]
    hard_negative_count: int
    rejected_counts: dict[str, int]


def coverage_report(
    sources: Sequence[SourceText], selected: Sequence[_CoverageCandidate]
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
