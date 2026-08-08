from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.morphology_provider_benchmark import normalized_digest

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs/morphology-provider-qualification-v1.json"
REPRODUCTION = ROOT / "docs/morphology-provider-qualification-reproduction-v1.json"


def test_recorded_report_passes_every_preregistered_gate() -> None:
    report = json.loads(REPORT.read_text())

    assert report["schema_id"] == "polis.morphology-provider-qualification-report"
    assert report["verdict"] == "PASS"
    assert all(report["gates"].values())
    assert report["quality"] == {
        "alarmed_negative_cases": 0,
        "correction_accuracy": 1.0,
        "false_alarm_rate": 0.0,
        "false_negatives": 0,
        "false_positives": 0,
        "negative_cases": 6,
        "precision": 1.0,
        "recall": 1.0,
        "true_positives": 3,
    }
    assert len(set(report["reproducibility"]["repetition_hashes"])) == 1
    assert report["normalized_digest"] == normalized_digest(report)


def test_recorded_report_contains_no_analyzed_input_text() -> None:
    report = json.loads(REPORT.read_text())

    assert "input_form" not in REPORT.read_text()
    assert all(
        set(outcome) == {"case_id", "kind", "form", "reason"}
        for outcome in report["outcomes"]
    )


def test_recorded_report_preserves_exact_provider_identity_and_footprint() -> None:
    report = json.loads(REPORT.read_text())

    assert report["identity"] == {
        "dictionary_id": "pl.sgjp.sgjp-2026.06.01",
        "dictionary_notice_sha256": (
            "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
        ),
        "package_version": "1.99.15",
        "provider": "morfeusz2",
    }
    assert report["performance"]["installed_size_delta_bytes"] == 40_725_689


def test_recorded_reproduction_preserves_both_command_runs() -> None:
    reproduction = json.loads(REPRODUCTION.read_text())
    runs = reproduction["runs"]

    assert reproduction["normalized_digest_match"] is True
    assert [run["exit_code"] for run in runs] == [0, 0]
    assert [run["verdict"] for run in runs] == ["PASS", "PASS"]
    assert len({run["normalized_digest"] for run in runs}) == 1
    assert runs[1]["report_sha256"] == hashlib.sha256(REPORT.read_bytes()).hexdigest()
