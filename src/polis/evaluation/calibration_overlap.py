from __future__ import annotations

import hashlib
import hmac
import unicodedata
from typing import assert_never

from polis.evaluation.calibration_freeze_models import (
    FINITE_OVERLAP_APPROVAL,
    FINITE_OVERLAP_HISTOGRAM,
    PREREGISTERED_FINITE_EXACT_MATCHES,
    FiniteOverlapHistogram,
    HoldoutV2Dataset,
    OverlapResult,
    PiiScanResult,
)
from polis.evaluation.calibration_json import fail
from polis.evaluation.calibration_models import (
    CalibrationCase,
    CalibrationDataset,
    ExpectedFinding,
)
from polis.evaluation.calibration_overlap_finite import (
    CALIBRATION_ID,
    Channel,
    finite_channels,
    finite_pair_class,
)
from polis.evaluation.calibration_pii import contains_sensitive_value

type DatasetLike = CalibrationDataset | HoldoutV2Dataset


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).casefold()
    return " ".join(normalized.split())


def _corrected(case: CalibrationCase) -> str | None:
    if case.role != "error" or len(case.expected_findings) != 1:
        return None
    finding: ExpectedFinding = case.expected_findings[0]
    text: str = case.text
    start: int = finding.start
    end: int = finding.end
    suggestion: str = finding.suggestion
    return text[:start] + suggestion + text[end:]


def _channels(
    dataset: DatasetLike, dataset_index: int, public_reference: bool
) -> tuple[Channel, ...]:
    channels: list[Channel] = []
    for case_index, case in enumerate(dataset.cases):
        channels.append(
            Channel(
                _normalize(case.text),
                dataset_index,
                case_index,
                public_reference,
                "input",
                dataset.id,
            )
        )
        corrected = _corrected(case)
        if corrected is not None:
            channels.append(
                Channel(
                    _normalize(corrected),
                    dataset_index,
                    case_index,
                    public_reference,
                    "corrected",
                    dataset.id,
                )
            )
    return tuple(channels)


def _fingerprint(key: bytes, value: str) -> bytes:
    return hmac.new(key, value.encode(), hashlib.sha256).digest()


def _grams(key: bytes, value: str) -> frozenset[bytes]:
    grams = (
        (value,)
        if len(value) < 5
        else tuple(value[index : index + 5] for index in range(len(value) - 4))
    )
    return frozenset(_fingerprint(key, gram) for gram in grams)


def _jaccard(left: frozenset[bytes], right: frozenset[bytes]) -> float:
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


def scan_dataset_pii(dataset: DatasetLike) -> PiiScanResult:
    for case in dataset.cases:
        values = [case.text]
        for finding in case.expected_findings:
            values.extend((finding.original, finding.suggestion))
        if any(contains_sensitive_value(value) for value in values):
            fail("dataset PII scan detected a blocked plaintext value")
    return PiiScanResult(0, 0, 0, 0, 0, "APPROVE")


def build_keyed_overlap(
    calibration: DatasetLike,
    holdout: DatasetLike,
    public_references: tuple[DatasetLike, ...],
    key: bytes,
) -> OverlapResult:
    if len(key) != 32:
        fail("overlap key must contain exactly 32 bytes")
    datasets = (calibration, holdout, *public_references)
    for dataset in datasets:
        scan_dataset_pii(dataset)
    channels = tuple(
        channel
        for dataset_index, dataset in enumerate(datasets)
        for channel in _channels(dataset, dataset_index, dataset_index >= 2)
    )
    fingerprints = tuple(_fingerprint(key, channel.value) for channel in channels)
    grams = tuple(_grams(key, channel.value) for channel in channels)
    eligible = finite_channels(calibration)
    finite_calibration = 0
    finite_quality = 0
    finite_v1 = 0
    finite_conservative = 0
    unexpected_exact = 0
    near = 0
    comparisons = 0
    for left in range(len(channels)):
        for right in range(left + 1, len(channels)):
            left_channel = channels[left]
            right_channel = channels[right]
            same_case = (
                left_channel.dataset_index == right_channel.dataset_index
                and left_channel.case_index == right_channel.case_index
            )
            if same_case or (
                left_channel.public_reference and right_channel.public_reference
            ):
                continue
            comparisons += 1
            if fingerprints[left] == fingerprints[right]:
                pair_class = finite_pair_class(
                    left_channel, right_channel, eligible or frozenset()
                )
                match pair_class:
                    case "calibration_calibration":
                        finite_calibration += 1
                    case "calibration_public_quality":
                        finite_quality += 1
                    case "calibration_public_v1":
                        finite_v1 += 1
                    case "calibration_public_conservative":
                        finite_conservative += 1
                    case None:
                        unexpected_exact += 1
                    case unreachable:
                        assert_never(unreachable)
            elif _jaccard(grams[left], grams[right]) >= 0.85:
                near += 1
    finite_required = calibration.id == CALIBRATION_ID
    histogram = FiniteOverlapHistogram(
        finite_calibration,
        finite_quality,
        finite_v1,
        finite_conservative,
    )
    finite_valid = (
        eligible is not None
        and len(eligible) == 26
        and histogram == FINITE_OVERLAP_HISTOGRAM
        and histogram.total == PREREGISTERED_FINITE_EXACT_MATCHES
    )
    approved = (
        unexpected_exact == 0 and near == 0 and (finite_valid or not finite_required)
    )
    return OverlapResult(
        unexpected_exact,
        near,
        comparisons,
        "APPROVE" if approved else "BLOCK",
        histogram.total,
        histogram,
        FINITE_OVERLAP_APPROVAL,
    )
