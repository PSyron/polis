from __future__ import annotations

import json
from pathlib import Path

import pytest
from experiments.languagetool_stdio_session.run_benchmark import (
    _validate_runtime_artifacts,
    benchmark_qualifies,
    load_development_sentence_cases,
    validate_privacy_safe_report,
)

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "languagetool_stdio_session"
CONFIG = EXPERIMENT / "config.json"
REPORT = EXPERIMENT / "report.json"
CORPUS = ROOT / "tests" / "fixtures" / "evaluation" / "polish_correction_corpus_v3.json"


def test_benchmark_configuration_is_closed_and_sentence_only() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))

    assert set(config) == {
        "schema_version",
        "experiment_id",
        "sentence_only",
        "corpus",
        "language_tool",
        "repetitions",
        "gates",
    }
    assert config["schema_version"] == 1
    assert config["sentence_only"] is True
    assert config["repetitions"] == {"warmup": 1, "measured": 2}
    assert set(config["language_tool"]) == {
        "version",
        "upstream_commit",
        "manifest_sha256",
        "bridge_sha256",
        "runner_path",
        "runner_sha256",
        "artifact_path",
        "artifact_sha256",
        "dependencies_path",
        "dependencies_sha256",
    }
    for name, value in config["language_tool"].items():
        if name.endswith("_sha256"):
            assert len(value) == 64
    assert config["gates"] == {
        "maximum_warm_p95_ms": 500.0,
        "maximum_combined_rss_bytes": 1_073_741_824,
        "maximum_swap_delta_bytes": 0,
        "maximum_socket_count": 0,
        "required_process_start_count": 1,
        "required_repeatable_cases": 69,
    }


def test_benchmark_loads_only_69_development_sentences() -> None:
    cases = load_development_sentence_cases(CORPUS)

    assert len(cases) == 69
    assert all(
        case.split == "development" and case.unit == "sentence" for case in cases
    )


@pytest.mark.parametrize(
    "override",
    (
        "POLIS_LT_MAIN_CLASS",
        "POLIS_LT_ARTIFACT",
        "POLIS_LT_DEPENDENCIES",
        "JAVA_BIN",
    ),
)
def test_benchmark_rejects_runtime_identity_overrides(
    monkeypatch: pytest.MonkeyPatch,
    override: str,
) -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    monkeypatch.setenv(override, "/tmp/unverified-runtime")

    with pytest.raises(ValueError, match="environment override"):
        _validate_runtime_artifacts(config, root=ROOT)


def test_gate_rejects_vacuous_or_unmeasured_evidence() -> None:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    passing = {
        "warm_p95_ms": 1.0,
        "combined_rss_bytes": 1,
        "swap_delta_bytes": 0,
        "socket_count": 0,
        "process_start_count": 1,
        "repeatable_case_count": 69,
        "measured_samples": 138,
    }

    assert benchmark_qualifies(passing, config)
    for key in passing:
        failed = dict(passing)
        failed[key] = (
            0 if key in {"measured_samples", "repeatable_case_count"} else 10**12
        )
        if key == "process_start_count":
            failed[key] = 2
        assert not benchmark_qualifies(failed, config), key


def test_committed_report_is_private_and_qualified() -> None:
    if not REPORT.exists():
        pytest.skip("real report is generated after the implementation passes")
    report = json.loads(REPORT.read_text(encoding="utf-8"))

    assert validate_privacy_safe_report(report) == report
    assert report["summary"]["process_start_count"] == 1
    assert report["summary"]["repeatable_case_count"] == 69
    assert report["summary"]["socket_count"] == 0
    assert report["decision"]["qualified"] is True
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    for name in ("runner_sha256", "artifact_sha256", "dependencies_sha256"):
        assert report["environment"][name] == config["language_tool"][name]
    assert all(item["input_character_count"] > 0 for item in report["case_evidence"])
