from __future__ import annotations

import json
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Final

from polis.evaluation._synthetic_corpus_candidates import Candidate, ErrorClass
from polis.evaluation._synthetic_corpus_sources import SourceMetadata, SourceText

ERROR_CLASSES: Final[tuple[ErrorClass, ...]] = (
    "case",
    "agreement",
    "punctuation",
    "diacritics",
)
type ClassDistribution = Mapping[ErrorClass, int]
type NormalizedClassDistribution = dict[ErrorClass, int]


class ClassDistributionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ClassDistributionKeysError(ClassDistributionError):
    missing: tuple[str, ...]
    unexpected: tuple[str, ...]

    def __str__(self) -> str:
        return (
            "class_distribution must contain exactly all error classes; "
            f"missing={self.missing}, unexpected={self.unexpected}"
        )


@dataclass(frozen=True, slots=True)
class InvalidClassQuotaError(ClassDistributionError):
    error_class: str

    def __str__(self) -> str:
        return (
            "class_distribution quotas must be non-negative integers; "
            f"invalid class={self.error_class}"
        )


@dataclass(frozen=True, slots=True)
class ClassDistributionCountError(ClassDistributionError):
    requested_count: int
    distribution_count: int

    def __str__(self) -> str:
        return (
            "class_distribution quotas must sum to count; "
            f"count={self.requested_count}, quota_sum={self.distribution_count}"
        )


@dataclass(frozen=True, slots=True)
class ClassCapacityError(ClassDistributionError):
    error_class: ErrorClass
    requested: int
    capacity: int

    def __str__(self) -> str:
        return (
            f"requested {self.requested} {self.error_class} pairs but class capacity "
            f"is {self.capacity}"
        )


def normalize_class_distribution(
    distribution: ClassDistribution, *, count: int
) -> NormalizedClassDistribution:
    expected = set(ERROR_CLASSES)
    supplied = set(distribution)
    if supplied != expected:
        raise ClassDistributionKeysError(
            missing=tuple(sorted(expected - supplied)),
            unexpected=tuple(sorted(str(item) for item in supplied - expected)),
        )
    for error_class in ERROR_CLASSES:
        quota = distribution[error_class]
        if isinstance(quota, bool) or not isinstance(quota, int) or quota < 0:
            raise InvalidClassQuotaError(error_class=error_class)
    normalized = {
        error_class: distribution[error_class] for error_class in ERROR_CLASSES
    }
    distribution_count = sum(normalized.values())
    if distribution_count != count:
        raise ClassDistributionCountError(
            requested_count=count,
            distribution_count=distribution_count,
        )
    return normalized


def select_candidates(
    candidates: Sequence[Candidate],
    count: int,
    seed: int,
    class_distribution: ClassDistribution | None,
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
        msg = f"synthetic source cannot cover classes: {', '.join(missing)}"
        raise ValueError(msg)
    if class_distribution is None:
        if count > len(candidates):
            msg = (
                f"requested {count} pairs but only {len(candidates)} unique pairs exist"
            )
            raise ValueError(msg)
        quotas = _quotas(
            {error_class: len(pool) for error_class, pool in pools.items()}, count
        )
    else:
        quotas = normalize_class_distribution(class_distribution, count=count)
    for error_class in ERROR_CLASSES:
        if quotas[error_class] > len(pools[error_class]):
            raise ClassCapacityError(
                error_class=error_class,
                requested=quotas[error_class],
                capacity=len(pools[error_class]),
            )
    randomizer = random.Random(seed)
    for pool in pools.values():
        randomizer.shuffle(pool)
    selected = [
        candidate
        for error_class in ERROR_CLASSES
        for candidate in pools[error_class][: quotas[error_class]]
    ]
    randomizer.shuffle(selected)
    return tuple(selected)


def punctuation_development_material() -> tuple[
    tuple[SourceText, ...], tuple[Candidate, ...]
]:
    texts = tuple(
        f"Dokument nr {index}, który opisuje wariant, pozostaje ważny."
        for index in range(1, 251)
    )
    payload = json.dumps(texts, ensure_ascii=False, separators=(",", ":")).encode()
    metadata = SourceMetadata(
        dataset_id="synthetic-punctuation-development",
        dataset_version=1,
        path="generated/synthetic-punctuation-development-v1",
        sha256=sha256(payload).hexdigest(),
        license="CC0-1.0",
        source="project-authored",
        clean_case_count=len(texts),
    )
    sources = tuple(
        SourceText(
            metadata=metadata,
            case_id=f"punctuation_development_{index:04d}",
            text=text,
        )
        for index, text in enumerate(texts, start=1)
    )
    candidates = tuple(
        Candidate(
            error_class="punctuation",
            correct_text=source.text,
            incorrect_text=source.text[:index] + source.text[index + 1 :],
            start=index,
            end=index,
            original="",
            suggestion=",",
            source_dataset=metadata.dataset_id,
            source_case_id=source.case_id,
        )
        for source in sources
        for index, character in enumerate(source.text)
        if character == ","
    )
    return sources, candidates


def _quotas(
    capacities: Mapping[ErrorClass, int], count: int
) -> NormalizedClassDistribution:
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
