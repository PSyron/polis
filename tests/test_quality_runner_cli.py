from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from tests.quality_runner_helpers import _ARTIFACT_SHA256


def _write_compare_inputs(tmp_path: Path) -> dict[str, Path]:
    from tests.test_quality_comparison_v4 import _write_artifacts

    return _write_artifacts(tmp_path)


def _module_command(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "polis.evaluation.quality_runner", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize("metric", ("p95", "throughput", "rss"))
def test_compare_returns_nonzero_for_each_failed_performance_gate(
    tmp_path: Path, metric: str
) -> None:
    import hashlib
    import json

    paths = _write_compare_inputs(tmp_path)
    performance = paths["morphology"].with_name("performance-result-morphology.json")
    payload = json.loads(performance.read_text(encoding="utf-8"))
    if metric == "p95":
        payload["performance"]["latency_ns"].update(p95=101, max=101)
    elif metric == "throughput":
        payload["performance"]["throughput"].update(
            total_duration_ns=124000,
            cases_per_second=5_000_000.0,
            code_points_per_second=50_000_000.0,
        )
    else:
        payload["rss"].update(
            worker_peak_rss_bytes=1999,
            worker_measured_incremental_peak_rss_bytes=999,
        )
    performance.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    proposal = json.loads(paths["proposal"].read_text(encoding="utf-8"))
    proposal["profiles"]["morphology"]["performance_result_artifact"]["sha256"] = (
        hashlib.sha256(performance.read_bytes()).hexdigest()
    )
    paths["proposal"].write_text(json.dumps(proposal, sort_keys=True), encoding="utf-8")

    result = _module_command(
        "compare",
        "--baseline-default",
        str(paths["default"]),
        "--baseline-morphology",
        str(paths["morphology"]),
        "--result-default",
        str(paths["result-default"]),
        "--result-morphology",
        str(paths["result-morphology"]),
        "--proposal",
        str(paths["proposal"]),
        "--output",
        str(paths["comparison"]),
    )

    assert result.returncode == 1
    comparison = json.loads(paths["comparison"].read_text(encoding="utf-8"))
    assert comparison["aggregate_verdict"] == "fail"


def test_module_help_lists_only_supported_commands() -> None:
    result = _module_command("--help")

    assert result.returncode == 0
    assert "baseline" in result.stdout
    assert "validate-proposal" in result.stdout
    assert "analyze" not in result.stdout


def test_baseline_help_exposes_only_default_protocol_flags() -> None:
    result = _module_command("baseline", "--help")

    assert result.returncode == 0
    for flag in (
        "--warmup",
        "--repetitions",
        "--artifact-sha256",
        "--dataset-version",
        "--output",
        "--replace",
    ):
        assert flag in result.stdout
    for forbidden in (
        "--dataset",
        "--config",
        "--category",
        "--rule",
        "--threshold",
        "--minimum-confidence",
    ):
        assert f"{forbidden} " not in result.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        ("--warmup", "-1"),
        ("--repetitions", "1"),
        ("--artifact-sha256", "a" * 63),
        ("--artifact-sha256", "A" * 64),
        ("--artifact-sha256", "g" * 64),
    ],
)
def test_baseline_rejects_invalid_protocol_values(
    arguments: tuple[str, str],
    tmp_path: Path,
) -> None:
    options = {
        "--warmup": "0",
        "--repetitions": "2",
        "--artifact-sha256": _ARTIFACT_SHA256,
    }
    options[arguments[0]] = arguments[1]
    output = tmp_path / "baseline.json"

    result = _module_command(
        "baseline",
        *(item for pair in options.items() for item in pair),
        "--output",
        str(output),
    )

    assert result.returncode == 2
    assert not output.exists()


def test_v2_baseline_requires_source_sha_and_profile(tmp_path: Path) -> None:
    output = tmp_path / "baseline.json"

    result = _module_command(
        "baseline",
        "--dataset-version",
        "v2",
        "--warmup",
        "0",
        "--repetitions",
        "2",
        "--artifact-sha256",
        _ARTIFACT_SHA256,
        "--output",
        str(output),
    )

    assert result.returncode == 2
    assert "--source-sha" in result.stderr
    assert "--profile" in result.stderr
    assert not output.exists()


@pytest.mark.parametrize(
    "flag",
    [
        "--dataset",
        "--config",
        "--category",
        "--rule",
        "--threshold",
        "--minimum-confidence",
    ],
)
def test_baseline_rejects_every_non_default_surface(
    flag: str,
    tmp_path: Path,
) -> None:
    output = tmp_path / "baseline.json"

    result = _module_command(
        "baseline",
        "--warmup",
        "0",
        "--repetitions",
        "2",
        "--artifact-sha256",
        _ARTIFACT_SHA256,
        "--output",
        str(output),
        flag,
        "forbidden",
    )

    assert result.returncode == 2
    assert f"unrecognized arguments: {flag} forbidden" in result.stderr
    assert not output.exists()
