from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PROFILES = ("default", "morphology")
ROLES = ("reference", "current")
PROTECTED = {
    "quality-threshold-proposal-v3.json": (
        "c747365bec66b2f3642d617ba53cd234da4098e6405b9ba5cbf79ff3ead28b6a"
    ),
    "quality-comparison-v3.json": (
        "b16ce0a44d46d06ed0b61a49a7153797338c93a616fff5c634c7c676ebe87c16"
    ),
    "quality-result-wave0-default.json": (
        "801116bcc5da9889528c3def9a8e30d8e559e2fab1180c2328f79f9ab743e953"
    ),
    "quality-result-wave0-morphology.json": (
        "02d7a40636b330e7a2e6a63096d59424d50844d962fb5df0398c7d3b3de36fc7"
    ),
    "quality-threshold-proposal-v2.json": (
        "982a4c91809d71ccd90fc3575ea5ae812c92126e964515f2a5f183be95ed3875"
    ),
    "quality-comparison-v2.json": (
        "fe357e42d8a55bb356d31551c4ae4b9fb452c891c94135070395eb7effa64086"
    ),
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _result(role: str, profile: str) -> dict[str, Any]:
    return _load(DOCS / f"runtime-performance-v2-{role}-{profile}.json")


def test_protocol_v2_evidence_is_additive_to_protected_history() -> None:
    for filename, digest in PROTECTED.items():
        assert _sha(DOCS / filename) == digest


def test_protocol_v2_results_share_dataset_environment_and_protocol_identity() -> None:
    protocol_sha = _sha(ROOT / "src/polis/runtime_performance_protocol.py")
    worker_sha = _sha(ROOT / "src/polis/runtime_performance_worker.py")
    environments = []
    for role in ROLES:
        for profile in PROFILES:
            result = _result(role, profile)
            assert result["schema_id"] == "polis.runtime-performance-result"
            assert result["schema_version"] == 1
            assert result["protocol_version"] == 2
            assert result["role"] == role
            assert result["profile"] == profile
            assert result["dataset"]["schema_version"] == 3
            assert result["dataset"]["cases"] == 340
            assert result["dataset"]["sha256"] == (
                "8f6dec8379af6330f2fb8330421f6a6581f6c9e39ad98fe304322b4a9abb6276"
            )
            assert result["protocol_implementation"] == {
                "overlay_applied": role == "reference",
                "runtime_performance_protocol_sha256": protocol_sha,
                "runtime_performance_worker_sha256": worker_sha,
            }
            assert result["reproducibility"]["warmup_repetitions"] == 1
            assert result["reproducibility"]["measured_repetitions"] == 5
            assert result["reproducibility"]["stable_repetitions"] == 5
            rss = result["rss"]
            assert rss["harness_peak_rss_bytes"] > 0
            assert (
                rss["worker_peak_rss_bytes"]
                >= rss["worker_measurement_start_rss_bytes"]
                >= rss["worker_startup_rss_bytes"]
            )
            assert rss["worker_measured_incremental_peak_rss_bytes"] == (
                rss["worker_peak_rss_bytes"] - rss["worker_measurement_start_rss_bytes"]
            )
            environments.append(result["environment"])
    assert all(environment == environments[0] for environment in environments)


def test_profile_identity_and_v3_quality_floors_are_preserved() -> None:
    proposal = _load(DOCS / "quality-threshold-proposal-v3.json")
    for role in ROLES:
        default = _result(role, "default")
        morphology = _result(role, "morphology")
        assert default["morphology_provider"] is None
        assert morphology["morphology_provider"] == {
            "provider": "morfeusz2",
            "package_version": "1.99.15",
            "dictionary_id": "pl.sgjp.sgjp-2026.06.01",
            "dictionary_notice_sha256": (
                "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
            ),
        }
    for profile in PROFILES:
        current = _result("current", profile)["quality"]
        floors = proposal["profiles"][profile]["quality_floors"]
        assert current["precision"] >= floors["minimum_precision"]
        assert current["recall"] >= floors["minimum_recall"]
        assert current["f1"] >= floors["minimum_f1"]
        assert current["span_accuracy"] >= floors["minimum_exact_span_accuracy"]
        assert (
            current["correction_accuracy"]
            >= floors["minimum_exact_correction_accuracy"]
        )
        assert current["false_alarm_rate"] <= floors["maximum_false_alarm_rate"]


def test_thresholds_are_reference_derived_and_comparison_is_fail_closed() -> None:
    thresholds_path = DOCS / "runtime-performance-thresholds-v2.json"
    comparison = _load(DOCS / "runtime-performance-comparison-v2.json")
    thresholds = _load(thresholds_path)
    assert thresholds["schema_id"] == "polis.runtime-performance-thresholds"
    assert thresholds["protocol_version"] == 2
    assert thresholds["comparison_policy"]["allowed_regression_fraction"] == 0.0
    assert thresholds["comparison_policy"]["harness_rss_is_gate_input"] is False
    assert comparison["thresholds_sha256"] == _sha(thresholds_path)

    for profile in PROFILES:
        reference = _result("reference", profile)
        current = _result("current", profile)
        profile_thresholds = thresholds["profiles"][profile]
        caps = profile_thresholds["performance_caps"]
        assert profile_thresholds["reference_result_sha256"] == _sha(
            ROOT / profile_thresholds["reference_result_path"]
        )
        assert (
            caps["maximum_p95_latency_ns"]
            == reference["performance"]["latency_ns"]["p95"]
        )
        assert (
            caps["minimum_throughput_cases_per_second"]
            == reference["performance"]["throughput"]["cases_per_second"]
        )
        assert (
            caps["maximum_worker_measured_incremental_peak_rss_bytes"]
            == reference["rss"]["worker_measured_incremental_peak_rss_bytes"]
        )
        profile_comparison = comparison["profiles"][profile]
        assert profile_comparison["current_result_sha256"] == _sha(
            ROOT / profile_comparison["current_result_path"]
        )
        gates = {item["gate"]: item["pass"] for item in profile_comparison["gates"]}
        assert gates["performance.maximum_p95_latency_ns"] == (
            current["performance"]["latency_ns"]["p95"]
            <= caps["maximum_p95_latency_ns"]
        )
        assert gates["performance.minimum_throughput_cases_per_second"] == (
            current["performance"]["throughput"]["cases_per_second"]
            >= caps["minimum_throughput_cases_per_second"]
        )
        assert gates[
            "performance.maximum_worker_measured_incremental_peak_rss_bytes"
        ] == (
            current["rss"]["worker_measured_incremental_peak_rss_bytes"]
            <= caps["maximum_worker_measured_incremental_peak_rss_bytes"]
        )

    assert comparison["profiles"]["default"]["verdict"] == "fail"
    assert comparison["profiles"]["morphology"]["verdict"] == "pass"
    assert comparison["aggregate_verdict"] == "fail"
