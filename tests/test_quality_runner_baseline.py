from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from tests.quality_runner_helpers import (
    _ARTIFACT_SHA256,
    _enable_successful_baseline,
    _reviewed_dataset,
    _write_baseline,
)

from polis import AnalyzerConfig
from polis.evaluation.quality_dataset import QUALITY_MANIFEST_PATH

if TYPE_CHECKING:
    from _pytest.monkeypatch import MonkeyPatch


type JsonValue = str | int | float | bool | None | list["JsonValue"] | JsonObject
type JsonObject = dict[str, JsonValue]


def test_pending_dataset_fails_closed_without_creating_report(
    monkeypatch: MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from polis.evaluation import quality_runner

    pending = _reviewed_dataset("pending_maintainer_review")
    monkeypatch.setattr(quality_runner, "load_quality_dataset", lambda **_: pending)
    monkeypatch.setattr(quality_runner, "Analyzer", lambda _: pytest.fail())
    output = tmp_path / "baseline.json"

    result = quality_runner.run(
        ["baseline", "--artifact-sha256", _ARTIFACT_SHA256, "--output", str(output)]
    )

    assert result == 2
    assert capsys.readouterr().err == (
        "error: quality dataset requires completed maintainer review "
        f"(status=pending_maintainer_review, reviewed=0/{len(pending.cases)})\n"
    )
    assert not output.exists()


def test_reviewed_baseline_uses_exact_default_analyzer_and_writes_report(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    from polis.evaluation.quality_runner import run

    output = tmp_path / "baseline.json"
    constructed_configs = _enable_successful_baseline(monkeypatch)

    result = run(
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

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == 0
    assert constructed_configs == [AnalyzerConfig()]
    assert payload["analyzer"] == "Analyzer(AnalyzerConfig())"
    assert payload["artifact"] == {"sha256": _ARTIFACT_SHA256}
    assert (
        payload["dataset"]["manifest"]["sha256"]
        == hashlib.sha256(QUALITY_MANIFEST_PATH.read_bytes()).hexdigest()
    )
    assert payload["reproducibility"]["stable_repetitions"] == 2
    assert set(payload["quality"]) >= {
        "precision",
        "recall",
        "f1",
        "span_accuracy",
        "correction_accuracy",
        "false_alarm_rate",
    }
    assert set(payload["performance"]) == {
        "latency_ns",
        "throughput",
        "peak_rss_bytes",
    }
    assert "thresholds" not in payload
    assert not any(key == "text" for key in _all_keys(payload))


def test_baseline_refuses_overwrite_without_replace(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from polis.evaluation.quality_runner import run

    output = tmp_path / "baseline.json"
    _write_baseline(monkeypatch, output)
    original = output.read_bytes()

    result = run(
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

    assert result == 2
    assert "output already exists" in capsys.readouterr().err
    assert output.read_bytes() == original


def _all_keys(value: JsonValue) -> list[str]:
    if isinstance(value, dict):
        return [
            key
            for item_key, item_value in value.items()
            for key in [item_key, *_all_keys(item_value)]
        ]
    if isinstance(value, list):
        return [key for item in value for key in _all_keys(item)]
    return []
