from __future__ import annotations

from typing import Literal

type DatasetKind = Literal["calibration", "holdout"]

FINITE_CAPACITIES = (
    ("rule:agreement.nominal_group_te_duze_okno", 1),
    ("rule:agreement.subject_verb_oni_czyta", 1),
    ("rule:inflection.negated_widziec_nominal_group", 1),
    ("rule:inflection.government_potrzebowac_pomoc", 1),
    ("rule:inflection.negated_widziec", 3),
    ("rule:syntax.initial_conditional_comma", 3),
    ("rule:syntax.missing_destination_preposition", 3),
)


def expected_counts(kind: DatasetKind, source: str) -> tuple[int, int]:
    capacity = dict(FINITE_CAPACITIES).get(source)
    if kind == "calibration":
        return (capacity if capacity is not None else 20, 40)
    return (0 if capacity is not None else 10, 20)


def expected_verdict(source: str) -> str | None:
    return "insufficient_evidence" if source in dict(FINITE_CAPACITIES) else None


def expected_denominators(source: str) -> dict[str, int]:
    error, correct = expected_counts("calibration", source)
    return {"error_cases": error, "correct_cases": correct}
