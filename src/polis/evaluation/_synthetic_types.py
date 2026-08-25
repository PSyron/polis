"""Typed values shared by the development-only synthetic corpus generator."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol

type JsonValue = (
    None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
)


class CorruptionClass(StrEnum):
    """One controlled corruption family emitted by the generator."""

    MORPHOLOGY_CASE = "morphology_case"
    AGREEMENT_NUMBER_OR_GENDER = "agreement_number_or_gender"
    REMOVED_COMMA = "removed_comma"
    REMOVED_DIACRITIC = "removed_diacritic"


@dataclass(frozen=True, slots=True)
class MorphologyAnalysis:
    """One normalized provider analysis row."""

    surface: str
    lemma: str
    tag: str


@dataclass(frozen=True, slots=True)
class MorphologyForm:
    """One normalized form returned by the provider's ``generate`` call."""

    form: str
    lemma: str
    tag: str


class MorphologyProvider(Protocol):
    """Minimal offline morphology capability required by the generator."""

    def analyse(self, text: str) -> Sequence[MorphologyAnalysis]: ...

    def generate(self, lemma: str) -> Sequence[MorphologyForm]: ...


@dataclass(frozen=True, slots=True)
class SyntheticEdit:
    """The exact edit that turns one corrupted string back into its source."""

    corruption_class: CorruptionClass
    start: int
    end: int
    original: str
    suggestion: str


@dataclass(frozen=True, slots=True)
class SyntheticPair:
    """One source/corrupted pair and its auditable edit evidence."""

    id: str
    corruption_class: CorruptionClass
    clean_text: str
    corrupted_text: str
    edit: SyntheticEdit
    source_offset: int
    source_lemma: str | None
    generated_forms: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SyntheticGeneratorConfig:
    """Stable generator inputs and source provenance supplied by the caller."""

    seed: int
    pair_count: int = 5000
    source_name: str = "unspecified"
    source_license: str = ""
    source_notes: str = ""
    dataset_id: str = "polis_synthetic_corruption_development"

    def __post_init__(self) -> None:
        if isinstance(self.seed, bool):
            raise ValueError("seed must be an integer")
        if self.pair_count < 4:
            raise ValueError("pair_count must be at least four")
        if not self.source_name.strip():
            raise ValueError("source_name must be non-blank")
        if not self.source_license.strip():
            raise ValueError("source_license must be non-blank")
        if not self.source_notes.strip():
            raise ValueError("source_notes must be non-blank")
        if not self.dataset_id.strip():
            raise ValueError("dataset_id must be non-blank")


@dataclass(frozen=True, slots=True)
class SyntheticCorpus:
    """Development-only synthetic corpus; never a holdout or runtime input."""

    schema_version: int
    generator_version: str
    dataset_id: str
    language: str
    role: str
    seed: int
    pair_count: int
    source_name: str
    source_license: str
    source_notes: str
    source_sha256: str
    pairs: tuple[SyntheticPair, ...]


@dataclass(frozen=True, slots=True)
class SyntheticArtifactPaths:
    """Two checkout-only files written by the optional generator command."""

    corpus: Path
    manifest: Path
