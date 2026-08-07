from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from tests.quality_runner_helpers import _write_baseline

from polis import AnalyzerConfig
from polis.evaluation.quality_report import baseline_file_sha256

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


def test_validate_proposal_reads_artifacts_without_constructing_analyzer(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from polis.evaluation import quality_runner

    baseline = tmp_path / "baseline.json"
    proposal = tmp_path / "proposal.json"
    _write_baseline(monkeypatch, baseline)
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    proposal.write_text(
        json.dumps(
            {
                "schema_id": "polis.quality-threshold-proposal",
                "schema_version": 1,
                "baseline_path": str(baseline),
                "baseline_sha256": baseline_file_sha256(baseline),
                "dataset_sha256": payload["dataset"]["sha256"],
                "proposed_thresholds": {
                    "minimum_precision": payload["quality"]["precision"],
                    "minimum_recall": payload["quality"]["recall"],
                    "minimum_f1": payload["quality"]["f1"],
                    "minimum_span_accuracy": payload["quality"]["span_accuracy"],
                    "minimum_correction_accuracy": payload["quality"][
                        "correction_accuracy"
                    ],
                    "maximum_false_alarm_rate": payload["quality"]["false_alarm_rate"],
                },
                "status": "pending_maintainer_approval",
                "enforced": False,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    class ForbiddenAnalyzer:
        def __init__(self, _config: AnalyzerConfig) -> None:
            pytest.fail("validate-proposal must not construct an analyzer")

    monkeypatch.setattr(quality_runner, "Analyzer", ForbiddenAnalyzer)

    result = quality_runner.run(
        [
            "validate-proposal",
            "--baseline",
            str(baseline),
            "--proposal",
            str(proposal),
        ]
    )

    assert result == 0
    assert (
        capsys.readouterr().out
        == "threshold proposal valid and pending maintainer approval\n"
    )
