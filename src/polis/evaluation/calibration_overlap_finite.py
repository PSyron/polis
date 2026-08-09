from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

from polis.evaluation.calibration_denominators import FINITE_SOURCE_CAPACITIES
from polis.evaluation.calibration_freeze_models import HoldoutV2Dataset
from polis.evaluation.calibration_models import CalibrationDataset
from polis.evaluation.calibration_sources import SOURCE_ROWS

type ChannelKind = Literal["input", "corrected"]
type FiniteChannelKey = tuple[int, ChannelKind]
type FinitePairClass = Literal[
    "calibration_calibration",
    "calibration_public_quality",
    "calibration_public_v1",
    "calibration_public_conservative",
]
type DatasetLike = CalibrationDataset | HoldoutV2Dataset

CALIBRATION_ID: Final = "polis-a-b-calibration-v2-v1"
_FINITE_CASES: Final = tuple(
    (
        f"cal-v2-{source_index:02d}-error-{case_index:02d}",
        row.source,
        row.category,
    )
    for source_index, row in enumerate(SOURCE_ROWS)
    for case_index in range(dict(FINITE_SOURCE_CAPACITIES).get(row.source, 0))
)
_PUBLIC_CLASSES: Final[tuple[tuple[str, FinitePairClass], ...]] = (
    ("polis_v1_quality_development", "calibration_public_quality"),
    ("polis_pl_initial_v1", "calibration_public_v1"),
    ("conservative-corrections-v1", "calibration_public_conservative"),
)


@dataclass(frozen=True, slots=True)
class Channel:
    value: str = field(repr=False)
    dataset_index: int
    case_index: int
    public_reference: bool
    kind: ChannelKind
    dataset_id: str


def finite_channels(calibration: DatasetLike) -> frozenset[FiniteChannelKey] | None:
    if calibration.id != CALIBRATION_ID:
        return frozenset()
    expected = {
        case_id: (source, category) for case_id, source, category in _FINITE_CASES
    }
    selected = tuple(
        (case_index, case)
        for case_index, case in enumerate(calibration.cases)
        if case.id in expected
    )
    if tuple(case.id for _, case in selected) != tuple(expected):
        return None
    keys: set[FiniteChannelKey] = set()
    for case_index, case in selected:
        source, category = expected[case.id]
        if (
            case.role != "error"
            or case.primary_source_identity != source
            or len(case.expected_findings) != 1
        ):
            return None
        finding = case.expected_findings[0]
        if finding.source != source or finding.category != category:
            return None
        keys.update(((case_index, "input"), (case_index, "corrected")))
    return frozenset(keys)


def _eligible_key(
    channel: Channel, eligible: frozenset[FiniteChannelKey]
) -> FiniteChannelKey | None:
    key = (channel.case_index, channel.kind)
    if channel.dataset_index == 0 and key in eligible:
        return key
    return None


def finite_pair_class(
    left: Channel,
    right: Channel,
    eligible: frozenset[FiniteChannelKey],
) -> FinitePairClass | None:
    left_key = _eligible_key(left, eligible)
    right_key = _eligible_key(right, eligible)
    if left_key is not None and right_key is not None:
        return "calibration_calibration"
    finite, reference = (left_key, right) if left_key is not None else (right_key, left)
    if finite is None or not reference.public_reference:
        return None
    for dataset_id, pair_class in _PUBLIC_CLASSES:
        if reference.dataset_id == dataset_id:
            return pair_class
    return None
