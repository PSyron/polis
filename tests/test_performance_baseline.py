from __future__ import annotations

import pytest
from experiments.performance import run_benchmark


@pytest.mark.slow
def test_performance_benchmark_has_required_fields_and_sane_metrics() -> None:
    payload = run_benchmark.run_benchmark(repetitions=2, warmup_repetitions=1)

    assert payload["schema_version"] == 1
    assert payload["benchmark_id"] == "m3-03-v1"

    settings = payload["settings"]
    environment = payload["environment"]
    assert isinstance(settings, dict)
    assert isinstance(environment, dict)
    assert settings["repetitions"] == 2
    assert settings["warmup_repetitions"] == 1

    runs = payload["runs"]
    assert isinstance(runs, list)
    assert len(runs) == 2

    names = {run["name"] for run in runs}
    assert names == {"rules-only", "rules+mock-llm"}

    for run in runs:
        assert run["case_count"] == 17
        assert run["repetitions"] == 2
        assert run["latency_ms"]["count"] == 34
        assert run["latency_ms"]["mean_ms"] >= 0.0
        assert run["latency_ms"]["p95_ms"] >= run["latency_ms"]["median_ms"]
        assert run["throughput_chars_per_sec"] > 0.0
        assert run["throughput_case_per_sec"] > 0.0
        assert run["memory_peak_bytes"] >= 0
        assert len(run["per_case"]) == 17
        assert all("case_id" in item for item in run["per_case"])
        assert all("input_chars" in item for item in run["per_case"])
        assert all(item["latency_ms"]["count"] == 2 for item in run["per_case"])


def test_performance_benchmark_validation_smoke() -> None:
    payload = run_benchmark.run_benchmark(repetitions=1, warmup_repetitions=0)
    run_benchmark._validate(payload)

    # A deliberately malformed payload must be rejected.
    bad_payload = dict(payload)
    bad_payload["schema_version"] = 99
    with pytest.raises(ValueError):
        run_benchmark._validate(bad_payload)
