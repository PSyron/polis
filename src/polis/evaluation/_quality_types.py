"""Value types for the active quality-development dataset."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Final

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)

QUALITY_DATASET_PATH: Final = (
    Path(__file__).parent / "datasets" / "quality" / "v1" / "cases.json"
)
QUALITY_MANIFEST_PATH: Final = QUALITY_DATASET_PATH.with_name("manifest.json")


class QualityDatasetVersion(StrEnum):
    V1 = "v1"
    V2 = "v2"
    V3 = "v3"


def quality_dataset_paths(version: QualityDatasetVersion) -> tuple[Path, Path]:
    dataset_path = (
        Path(__file__).parent / "datasets" / "quality" / version.value / "cases.json"
    )
    return dataset_path, dataset_path.with_name("manifest.json")


class QualityDatasetError(ValueError):
    """Raised when quality dataset bytes do not satisfy the reviewed contract."""


class QualityCaseKind(StrEnum):
    """The role of a case in the quality protocol."""

    ERROR = "error"
    CORRECT = "correct"
    CONFLICT = "conflict"
    ABSTAIN = "abstain"


class QualityPhenomenon(StrEnum):
    """A linguistic phenomenon required by the v1 quality matrix."""

    INFLECTION = "inflection"
    RECTION = "rection"
    AGREEMENT = "agreement"
    SPELLING = "spelling"
    SYNTAX = "syntax"
    PUNCTUATION = "punctuation"


class QualityFeature(StrEnum):
    """A cross-cutting quality-protocol feature."""

    UNICODE = "unicode"
    MULTI_SENTENCE = "multi_sentence"
    CONFLICT = "conflict"
    ABSTENTION = "abstention"


@dataclass(frozen=True, slots=True)
class QualityExpectedFinding:
    """One expected minimal correction against a half-open source span."""

    category: str
    start: int
    end: int
    original: str
    suggestion: str
    rationale: str


@dataclass(frozen=True, slots=True)
class QualityCase:
    """One project-authored input in the active quality matrix."""

    id: str
    kind: QualityCaseKind
    phenomenon: QualityPhenomenon | None
    pair_id: str | None
    features: frozenset[QualityFeature]
    text: str
    findings: tuple[QualityExpectedFinding, ...]
    rationale: str | None


@dataclass(frozen=True, slots=True)
class QualityReview:
    """Maintainer review evidence bound to one canonical dataset identity."""

    status: str
    reviewer_role: str
    checklist_version: str
    reviewed_case_ids: tuple[str, ...]
    canonical_sha256: str


@dataclass(frozen=True, slots=True)
class QualityDataset:
    """The validated active dataset together with its review identity."""

    schema_id: str
    schema_version: int
    id: str
    dataset_version: int
    license: str
    source: str
    cases: tuple[QualityCase, ...]
    canonical_sha256: str
    review: QualityReview
    manifest_canonical_sha256: str
