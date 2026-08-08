from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.morphology_provider_benchmark import normalized_digest

ROOT = Path(__file__).resolve().parents[1]


def test_normalized_digest_ignores_measurements_and_environment() -> None:
    report = {
        "identity": {"provider": "morfeusz2", "version": "1.99.15"},
        "dataset": {"canonical_sha256": "abc"},
        "quality": {"precision": 1.0},
        "gates": {"precision": True},
        "verdict": "PASS",
        "performance": {"p95_ns": 123},
        "environment": {"platform": "one"},
    }
    changed = json.loads(json.dumps(report))
    changed["performance"]["p95_ns"] = 999
    changed["environment"]["platform"] = "two"

    assert normalized_digest(report) == normalized_digest(changed)


def test_cli_invalid_dataset_preserves_existing_output(tmp_path: Path) -> None:
    from scripts.benchmark_morphology_provider import main

    output = tmp_path / "report.json"
    output.write_text("sentinel")

    exit_code = main(
        ["--dataset", str(tmp_path / "missing.json"), "--output", str(output)]
    )

    assert exit_code == 2
    assert output.read_text() == "sentinel"


def test_exact_issue_command_runs_as_a_script(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    command = [
        sys.executable,
        "scripts/benchmark_morphology_provider.py",
        "--dataset",
        "tests/fixtures/v1/morphology_provider_qualification.json",
        "--output",
        str(output),
    ]

    first = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False
    )
    first_report = json.loads(output.read_text())
    second = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, check=False
    )
    second_report = json.loads(output.read_text())

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first_report["verdict"] == second_report["verdict"] == "PASS"
    assert first_report["normalized_digest"] == second_report["normalized_digest"]
