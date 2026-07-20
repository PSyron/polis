from __future__ import annotations

from experiments.llm_backends import run_benchmark


def test_benchmark_prefers_heuristic_backend_for_seed_slice() -> None:
    payload, selected = run_benchmark.run_benchmark()
    raw_results = payload["results"]
    assert isinstance(raw_results, list)
    results: dict[str, dict[str, object]] = {}
    for item in raw_results:
        assert isinstance(item, dict)
        results[str(item["name"])] = item

    heu_f1_value = results["mock-heu"]["f1"]
    noisy_f1_value = results["mock-noisy"]["f1"]
    assert isinstance(heu_f1_value, float)
    assert isinstance(noisy_f1_value, float)
    heu_error_count = results["mock-heu"]["error_count"]
    assert isinstance(heu_error_count, int)

    heu_f1 = float(heu_f1_value)
    noisy_f1 = float(noisy_f1_value)
    assert selected == "mock-heu"
    assert heu_f1 >= noisy_f1
    assert heu_error_count == 0


def test_benchmark_results_file_is_reproducible() -> None:
    payload, selected = run_benchmark.run_benchmark()
    assert payload["selected_backend"] == selected


def test_benchmark_record_contains_environment_and_settings() -> None:
    payload, _ = run_benchmark.run_benchmark()

    settings = payload["settings"]
    environment = payload["environment"]

    assert isinstance(settings, dict)
    assert settings["seed"] == "m2-01-heuristic-v1"
    assert settings["offline_only"] is True

    assert isinstance(environment, dict)
    assert "hardware" in environment
    assert "software" in environment

    hardware = environment["hardware"]
    software = environment["software"]
    assert isinstance(hardware, dict)
    assert isinstance(software, dict)
    for key in ("platform", "machine", "processor"):
        assert key in hardware
    for key in ("python", "python_implementation"):
        assert key in software
