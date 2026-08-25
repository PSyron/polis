from __future__ import annotations

import json
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock

import pytest

import polis
import polis.analyzer as analyzer_module
from polis import AnalysisOptions, AnalyzerConfig, Category

ROOT = Path(__file__).resolve().parents[1]
E2E_CORPUS = ROOT / "tests/fixtures/e2e/polish_correction_corpus.json"


@pytest.fixture(autouse=True)
def clear_analyzer_cache() -> Generator[None, None, None]:
    cache = getattr(analyzer_module, "_ANALYZER_CACHE", None)
    if cache is not None:
        cache.clear()
    yield
    if cache is not None:
        cache.clear()


def test_module_level_analyze_is_exported() -> None:
    assert "analyze" in polis.__all__
    assert callable(getattr(polis, "analyze", None))


def test_module_level_correct_is_exported() -> None:
    assert "correct" in polis.__all__
    assert callable(getattr(polis, "correct", None))


@pytest.mark.parametrize(
    "text",
    tuple(
        case["input"]
        for case in json.loads(E2E_CORPUS.read_text(encoding="utf-8"))["cases"]
    ),
)
def test_module_level_analyze_matches_analyzer_for_regression_corpus(
    text: str,
) -> None:
    expected = polis.Analyzer(AnalyzerConfig()).analyze(text)

    assert polis.analyze(text) == expected


def test_module_level_correct_matches_analyzer() -> None:
    text = "Zeby jutro,powiem o tym."

    expected = polis.Analyzer(AnalyzerConfig()).correct(text)

    assert polis.correct(text) == expected


def test_module_level_correct_passes_options_to_cached_analyzer() -> None:
    options = AnalysisOptions(categories={Category.AGREEMENT})

    result = polis.correct("Zeby", options=options)

    assert result.corrected_text == "Zeby"


def test_module_level_analyze_reuses_analyzer_for_same_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    construction_count = 0

    real_analyzer = analyzer_module.Analyzer

    def counting_analyzer(config: AnalyzerConfig) -> polis.Analyzer:
        nonlocal construction_count
        construction_count += 1
        return real_analyzer(config)

    monkeypatch.setattr(analyzer_module, "Analyzer", counting_analyzer)

    polis.analyze("Zeby")
    polis.analyze("Witaj")

    assert construction_count == 1


def test_module_level_analyze_isolates_custom_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    construction_count = 0

    real_analyzer = analyzer_module.Analyzer

    def counting_analyzer(config: AnalyzerConfig) -> polis.Analyzer:
        nonlocal construction_count
        construction_count += 1
        return real_analyzer(config)

    monkeypatch.setattr(analyzer_module, "Analyzer", counting_analyzer)
    custom_config = AnalyzerConfig(categories=frozenset({Category.SPELLING}))

    default = polis.analyze("Te zdanie")
    custom = polis.analyze("Te zdanie", config=custom_config)
    default_again = polis.analyze("Te zdanie")

    assert default.issues
    assert custom.issues == ()
    assert default_again == default
    assert construction_count == 2


def test_module_level_analyze_does_not_duplicate_construction_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    construction_count = 0
    construction_count_lock = Lock()
    construction_started = Event()
    release_construction = Event()
    before_call = [Event() for _ in range(8)]

    real_analyzer = analyzer_module.Analyzer

    def counting_analyzer(config: AnalyzerConfig) -> polis.Analyzer:
        nonlocal construction_count
        with construction_count_lock:
            construction_count += 1
        construction_started.set()
        assert release_construction.wait(timeout=5)
        return real_analyzer(config)

    monkeypatch.setattr(analyzer_module, "Analyzer", counting_analyzer)

    def run(index: int) -> polis.AnalysisResult:
        before_call[index].set()
        return polis.analyze("Zeby")

    with ThreadPoolExecutor(max_workers=len(before_call)) as executor:
        futures = [executor.submit(run, index) for index in range(len(before_call))]
        assert all(event.wait(timeout=5) for event in before_call)
        assert construction_started.wait(timeout=5)
        release_construction.set()
        results = [future.result() for future in futures]

    assert construction_count == 1
    assert all(result == results[0] for result in results)


def test_module_level_analyze_passes_options_to_cached_analyzer() -> None:
    options = AnalysisOptions(categories={Category.SPELLING})

    result = polis.analyze("Te zdanie", options=options)

    assert result.issues == ()
    assert result.options == options
