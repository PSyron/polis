from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

from polis import AnalyzerConfig
from polis.evaluation.quality_dataset import (
    QualityDataset,
    QualityReview,
    load_quality_dataset,
)

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


_ARTIFACT_SHA256 = "0" * 64


def _reviewed_dataset(status: str = "maintainer-reviewed") -> QualityDataset:
    dataset = load_quality_dataset()
    reviewed_ids = tuple(c.id for c in dataset.cases) if status.startswith("m") else ()
    review = QualityReview(
        status=status,
        reviewer_role=dataset.review.reviewer_role,
        checklist_version=dataset.review.checklist_version,
        reviewed_case_ids=reviewed_ids,
        canonical_sha256=dataset.review.canonical_sha256,
    )
    return replace(dataset, review=review)


def _enable_successful_baseline(
    monkeypatch: MonkeyPatch,
) -> list[AnalyzerConfig]:
    from polis.evaluation import quality_runner

    constructed_configs: list[AnalyzerConfig] = []

    class FakeAnalyzer:
        def __init__(self, config: AnalyzerConfig) -> None:
            constructed_configs.append(config)

        def analyze(self, _text: str) -> SimpleNamespace:
            return SimpleNamespace(issues=())

    monkeypatch.setattr(quality_runner, "Analyzer", FakeAnalyzer)
    monkeypatch.setattr(
        quality_runner,
        "load_quality_dataset",
        lambda **_kwargs: _reviewed_dataset(),
    )
    return constructed_configs


def _write_baseline(
    monkeypatch: MonkeyPatch,
    output: Path,
) -> None:
    from polis.evaluation.quality_runner import run

    _enable_successful_baseline(monkeypatch)
    assert (
        run(
            [
                "baseline",
                "--warmup",
                "0",
                "--repetitions",
                "2",
                "--artifact-sha256",
                _ARTIFACT_SHA256,
                "--output",
                str(output),
            ]
        )
        == 0
    )
