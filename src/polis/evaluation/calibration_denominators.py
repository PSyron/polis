from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from polis.evaluation.calibration_models import (
    CalibrationContractError,
    CalibrationRole,
)
from polis.evaluation.calibration_sources import SOURCE_ROWS

type DatasetKind = Literal["calibration", "holdout"]
type PreregisteredVerdict = Literal["insufficient_evidence"]

FINITE_SOURCE_CAPACITIES: Final = (
    ("rule:agreement.nominal_group_te_duze_okno", 1),
    ("rule:agreement.subject_verb_oni_czyta", 1),
    ("rule:inflection.negated_widziec_nominal_group", 1),
    ("rule:inflection.government_potrzebowac_pomoc", 1),
    ("rule:inflection.negated_widziec", 3),
    ("rule:syntax.initial_conditional_comma", 3),
    ("rule:syntax.missing_destination_preposition", 3),
)


@dataclass(frozen=True, slots=True)
class SourceDenominator:
    source: str
    calibration_error_cases: int
    calibration_correct_cases: int
    holdout_error_cases: int
    holdout_correct_cases: int
    preregistered_verdict: PreregisteredVerdict | None


@dataclass(frozen=True, slots=True)
class ExpectedCaseRow:
    case_id: str
    role: CalibrationRole
    source: str


_CAPACITIES: Final = dict(FINITE_SOURCE_CAPACITIES)
SOURCE_DENOMINATORS: Final = tuple(
    SourceDenominator(
        row.source,
        _CAPACITIES.get(row.source, 20),
        40,
        0 if row.source in _CAPACITIES else 10,
        20,
        "insufficient_evidence" if row.source in _CAPACITIES else None,
    )
    for row in SOURCE_ROWS
)

CALIBRATION_ERROR_COUNT: Final = sum(
    row.calibration_error_cases for row in SOURCE_DENOMINATORS
)
CALIBRATION_CORRECT_COUNT: Final = sum(
    row.calibration_correct_cases for row in SOURCE_DENOMINATORS
)
CALIBRATION_CASE_COUNT: Final = CALIBRATION_ERROR_COUNT + CALIBRATION_CORRECT_COUNT
HOLDOUT_ERROR_COUNT: Final = sum(row.holdout_error_cases for row in SOURCE_DENOMINATORS)
HOLDOUT_CORRECT_COUNT: Final = sum(
    row.holdout_correct_cases for row in SOURCE_DENOMINATORS
)
HOLDOUT_CASE_COUNT: Final = HOLDOUT_ERROR_COUNT + HOLDOUT_CORRECT_COUNT


def denominator_for(source: str) -> SourceDenominator:
    for row in SOURCE_DENOMINATORS:
        if row.source == source:
            return row
    raise CalibrationContractError(
        "source is absent from the approved denominator contract"
    )


def counts_for(kind: DatasetKind, source: str) -> tuple[int, int]:
    row = denominator_for(source)
    if kind == "calibration":
        return row.calibration_error_cases, row.calibration_correct_cases
    return row.holdout_error_cases, row.holdout_correct_cases


def expected_case_rows(kind: DatasetKind) -> tuple[ExpectedCaseRow, ...]:
    prefix = "cal-v2" if kind == "calibration" else "hold-v2"
    return tuple(
        ExpectedCaseRow(
            f"{prefix}-{source_index:02d}-{role}-{case_index:02d}",
            role,
            source.source,
        )
        for source_index, source in enumerate(SOURCE_ROWS)
        for role, count in zip(
            ("error", "correct"), counts_for(kind, source.source), strict=True
        )
        for case_index in range(count)
    )
