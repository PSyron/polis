from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT / "third_party" / "languagetool-pl" / "scripts" / "benchmark.py"
CORPUS = ROOT / "tests" / "fixtures" / "e2e" / "polish_correction_corpus.json"
SNAPSHOT = (
    ROOT / "tests" / "fixtures" / "languagetool" / "allowlisted_pl_68_snapshot.json"
)


def _benchmark_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("lt_benchmark", BENCHMARK_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeSession:
    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self.responses = responses
        self.durations = iter([750.0, *([12.5] * 32)])
        self.rss_kib = 96_000

    def check(self, text: str) -> tuple[dict[str, Any], float]:
        return self.responses[text], next(self.durations)

    def close(self) -> None:
        return None


def _responses() -> dict[str, dict[str, Any]]:
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    findings = snapshot["findings_by_case"]
    responses: dict[str, dict[str, Any]] = {}
    for case in corpus["cases"]:
        matches = []
        for start, end, suggestion in findings.get(case["id"], []):
            matches.append(
                {
                    "offset": start,
                    "length": end - start,
                    "replacements": [{"value": suggestion}],
                    "rule": {"id": "BRAK_PRZECINKA_ZE"},
                }
            )
        responses[case["input"]] = {
            "software": {"name": "LanguageTool", "version": "6.8"},
            "matches": matches,
        }
    return responses


def test_vendor_benchmark_scores_real_corpus_without_snapshot_oracle() -> None:
    module = _benchmark_module()
    report = module.run_benchmark(
        corpus=CORPUS,
        session=_FakeSession(_responses()),
        runtime_disk_bytes=42_000_000,
    )

    assert report["totals"]["case_count"] == 33
    assert report["totals"]["qualified_true_positives"] == 18
    assert report["totals"]["qualified_false_positives"] == 0
    assert report["totals"]["qualified_false_negatives"] == 6
    assert report["totals"]["all_gold_false_negatives"] == 32
    assert report["quality"]["qualified_f1"] == 0.8571428571428571
    assert report["quality"]["all_gold_f1"] == 0.5294117647058824
    assert report["quality"]["hard_negative_unchanged_rate"] == 1.0
    assert report["performance"]["startup_ms"] == 750.0
    assert report["performance"]["warm_latency_ms"]["p50"] == 12.5
    assert report["performance"]["rss_peak_kib"] == 96_000
    assert report["performance"]["runtime_disk_bytes"] == 42_000_000
    assert len(report["cases"]) == 33


def test_vendor_benchmark_normalizes_wide_languagetool_replacement() -> None:
    module = _benchmark_module()
    text = "Powiedział że jutro wróci."
    payload = {
        "matches": [
            {
                "offset": 0,
                "length": 13,
                "replacements": [{"value": "Powiedział, że"}],
                "rule": {"id": "BRAK_PRZECINKA_ZE"},
            }
        ]
    }

    assert module._normalize_prediction(text, payload) == {
        (10, 10, ",", "BRAK_PRZECINKA_ZE")
    }
