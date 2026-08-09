from __future__ import annotations

from dataclasses import replace
from typing import Literal, assert_never

import pytest

from polis.evaluation.calibration_denominators import FINITE_SOURCE_CAPACITIES
from polis.evaluation.calibration_freeze_models import OverlapResult
from polis.evaluation.calibration_models import (
    CalibrationCase,
    CalibrationContractError,
    CalibrationDataset,
    ExpectedFinding,
)
from polis.evaluation.calibration_overlap import build_keyed_overlap
from polis.evaluation.calibration_sources import SOURCE_ROWS

type CollisionClass = Literal["exact", "near"]


def _correct_dataset(identifier: str, text: str) -> CalibrationDataset:
    case = CalibrationCase(f"{identifier}-case", "correct", "rule:x", text, ())
    return CalibrationDataset(identifier, (case,), "1" * 64)


def _correct_cases_dataset(
    identifier: str, left: str, right: str
) -> CalibrationDataset:
    cases = (
        CalibrationCase(f"{identifier}-left", "correct", "rule:x", left, ()),
        CalibrationCase(f"{identifier}-right", "correct", "rule:x", right, ()),
    )
    return CalibrationDataset(identifier, cases, "1" * 64)


def _finite_calibration() -> CalibrationDataset:
    capacities = dict(FINITE_SOURCE_CAPACITIES)
    cases: list[CalibrationCase] = []
    inputs = tuple(
        f"Powierzchnia grupa-{group}." if group < 4 else f"Wejście unikalne-{group}."
        for group in (0, 0, 0, 1, 1, 1, 2, 2, 2, 3, 3, 3, 10)
    )
    corrected = tuple(
        f"Powierzchnia grupa-{group}." if group < 6 else f"Wynik unikalny-{group}."
        for group in (4, 4, 4, 5, 5, 5, 20, 21, 22, 23, 24, 25, 26)
    )
    ordinal = 0
    for source_index, row in enumerate(SOURCE_ROWS):
        for case_index in range(capacities.get(row.source, 0)):
            text = inputs[ordinal]
            suggestion = corrected[ordinal]
            finding = ExpectedFinding(
                row.source, row.category, 0, len(text), text, suggestion
            )
            cases.append(
                CalibrationCase(
                    f"cal-v2-{source_index:02d}-error-{case_index:02d}",
                    "error",
                    row.source,
                    text,
                    (finding,),
                )
            )
            ordinal += 1
    return CalibrationDataset("polis-a-b-calibration-v2-v1", tuple(cases), "1" * 64)


def _finite_public_references(
    calibration: CalibrationDataset,
) -> tuple[CalibrationDataset, ...]:
    channels = tuple(
        value
        for case in calibration.cases
        for value in (case.text, case.expected_findings[0].suggestion)
    )
    distinct = tuple(dict.fromkeys(channels))

    def reference(identifier: str, values: tuple[str, ...]) -> CalibrationDataset:
        cases = tuple(
            CalibrationCase(f"{identifier}-{index}", "correct", "public:x", value, ())
            for index, value in enumerate(values)
        )
        return CalibrationDataset(identifier, cases, "2" * 64)

    quality_values = (*distinct, *distinct[:4], distinct[6])
    v1_values = (*distinct[:6], *distinct[6:9])
    return (
        reference("polis_v1_quality_development", quality_values),
        reference("polis_pl_initial_v1", v1_values),
        reference("conservative-corrections-v1", ("Odrębna referencja.",)),
    )


def _finite_overlap(calibration: CalibrationDataset) -> OverlapResult:
    holdout = _correct_dataset("hold", "Całkowicie odrębny holdout.")
    references = _finite_public_references(_finite_calibration())
    return build_keyed_overlap(calibration, holdout, references, b"k" * 32)


def test_overlap_requires_private_32_byte_key() -> None:
    with pytest.raises(CalibrationContractError):
        build_keyed_overlap(
            _correct_dataset("cal", "alpha"),
            _correct_dataset("hold", "beta"),
            (),
            b"",
        )


@pytest.mark.parametrize("dataset_role", ["calibration", "holdout"])
@pytest.mark.parametrize(
    ("collision_class", "left", "right"),
    [
        ("exact", "ten sam przypadek", "ten sam przypadek"),
        ("near", "abcdefghijklmnopqrstuvwxy", "abcdefghijklmnopqrstuvwxz"),
    ],
)
def test_distinct_cases_within_each_new_dataset_still_block(
    dataset_role: Literal["calibration", "holdout"],
    collision_class: CollisionClass,
    left: str,
    right: str,
) -> None:
    colliding = _correct_cases_dataset(dataset_role, left, right)
    separate = _correct_dataset("separate", "zupełnie oddzielny przypadek")
    calibration, holdout = (
        (colliding, separate)
        if dataset_role == "calibration"
        else (separate, colliding)
    )

    result = build_keyed_overlap(calibration, holdout, (), b"k" * 32)

    assert result.verdict == "BLOCK"
    assert result.exact_collisions == (collision_class == "exact")
    assert result.near_collisions == (collision_class == "near")


@pytest.mark.parametrize("dataset_role", ["calibration", "holdout"])
@pytest.mark.parametrize(
    ("collision_class", "left", "right"),
    [
        ("exact", "wspólny przypadek publiczny", "wspólny przypadek publiczny"),
        ("near", "abcdefghijklmnopqrstuvwxy", "abcdefghijklmnopqrstuvwxz"),
    ],
)
def test_each_new_dataset_still_compares_with_public_references(
    dataset_role: Literal["calibration", "holdout"],
    collision_class: CollisionClass,
    left: str,
    right: str,
) -> None:
    new_dataset = _correct_dataset(dataset_role, left)
    separate = _correct_dataset("separate", "zupełnie oddzielny przypadek")
    calibration, holdout = (
        (new_dataset, separate)
        if dataset_role == "calibration"
        else (separate, new_dataset)
    )

    result = build_keyed_overlap(
        calibration, holdout, (_correct_dataset("public", right),), b"k" * 32
    )

    assert result.verdict == "BLOCK"
    assert result.exact_collisions == (collision_class == "exact")
    assert result.near_collisions == (collision_class == "near")


@pytest.mark.parametrize(
    ("collision_class", "left", "right"),
    [
        ("exact", "wspólna publiczna referencja", "wspólna publiczna referencja"),
        ("near", "abcdefghijklmnopqrstuvwxy", "abcdefghijklmnopqrstuvwxz"),
    ],
)
def test_public_reference_only_pairs_are_not_compared(
    collision_class: CollisionClass, left: str, right: str
) -> None:
    result = build_keyed_overlap(
        _correct_dataset("cal", "wyjątkowa kalibracja"),
        _correct_dataset("hold", "wyjątkowy holdout"),
        (_correct_dataset("public-a", left), _correct_dataset("public-b", right)),
        b"k" * 32,
    )

    assert result.verdict == "APPROVE", collision_class
    assert result.exact_collisions == 0
    assert result.near_collisions == 0


def test_exact_preregistered_finite_pairs_are_classified_separately() -> None:
    result = _finite_overlap(_finite_calibration())

    assert result.verdict == "APPROVE"
    assert result.preregistered_finite_exact_matches == 78
    assert result.finite_match_histogram.calibration_calibration == 18
    assert result.finite_match_histogram.calibration_public_quality == 39
    assert result.finite_match_histogram.calibration_public_v1 == 21
    assert result.finite_match_histogram.calibration_public_conservative == 0
    assert result.unexpected_exact_collisions == 0
    assert result.near_collisions == 0
    assert result.approval.comment_id == 5234058206
    assert result.approval.body_sha256 == (
        "e895bba130d5e13bedc02a49cff53eb43ec435e783ca539b7620c842f6a46b79"
    )


@pytest.mark.parametrize("mutation", ["id", "source", "role", "channel"])
def test_mutated_finite_case_identity_or_channel_blocks(
    mutation: Literal["id", "source", "role", "channel"],
) -> None:
    calibration = _finite_calibration()
    first = calibration.cases[0]
    match mutation:
        case "id":
            changed = replace(first, id="cal-v2-02-error-99")
        case "source":
            changed = replace(first, primary_source_identity="rule:other")
        case "role":
            changed = replace(first, role="correct")
        case "channel":
            changed = replace(first, expected_findings=())
        case unreachable:
            assert_never(unreachable)
    mutated = replace(calibration, cases=(changed, *calibration.cases[1:]))

    assert _finite_overlap(mutated).verdict == "BLOCK"


def test_wrong_finite_match_count_blocks_without_suppressing_matches() -> None:
    calibration = _finite_calibration()
    references = _finite_public_references(calibration)
    shortened = replace(references[0], cases=references[0].cases[1:])
    result = build_keyed_overlap(
        calibration,
        _correct_dataset("hold", "Całkowicie odrębny holdout."),
        (shortened, *references[1:]),
        b"k" * 32,
    )

    assert result.verdict == "BLOCK"
    assert result.preregistered_finite_exact_matches < 78


def test_near_finite_public_pair_remains_a_blocking_near_collision() -> None:
    calibration = _finite_calibration()
    references = _finite_public_references(calibration)
    first = references[0].cases[0]
    near = replace(first, text=first.text[:-1] + "x")
    drifted = replace(references[0], cases=(near, *references[0].cases[1:]))
    result = build_keyed_overlap(
        calibration,
        _correct_dataset("hold", "Całkowicie odrębny holdout."),
        (drifted, *references[1:]),
        b"k" * 32,
    )

    assert result.verdict == "BLOCK"
    assert result.near_collisions > 0


def test_holdout_or_unapproved_public_exact_match_is_unexpected() -> None:
    calibration = _finite_calibration()
    finite_text = calibration.cases[0].text
    holdout = _correct_dataset("hold", finite_text)
    unapproved = _correct_dataset("public-other", finite_text)

    holdout_result = build_keyed_overlap(
        calibration, holdout, _finite_public_references(calibration), b"k" * 32
    )
    public_result = build_keyed_overlap(
        calibration,
        _correct_dataset("hold", "Odrębny holdout."),
        (*_finite_public_references(calibration), unapproved),
        b"k" * 32,
    )

    assert holdout_result.verdict == "BLOCK"
    assert holdout_result.unexpected_exact_collisions > 0
    assert public_result.verdict == "BLOCK"
    assert public_result.unexpected_exact_collisions > 0
