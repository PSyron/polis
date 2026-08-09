from __future__ import annotations

from pathlib import Path

from polis.evaluation.calibration_operator_public import _conservative

ROOT = Path(__file__).parents[1]


def test_operator_accepts_every_frozen_conservative_fixture_case_shape() -> None:
    fixture = ROOT / "tests" / "fixtures" / "v1" / "conservative_corrections.json"

    dataset = _conservative(fixture.read_bytes())

    assert len(dataset.cases) == 25
    assert sum(case.role == "error" for case in dataset.cases) == 12
    assert sum(case.role == "correct" for case in dataset.cases) == 13
