from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from polis import AnalysisResult, Analyzer, AnalyzerConfig, CorrectionResult

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_TEXTS = (
    "Ona jestem tutaj.",
    "Zeby jutro,powiem o tym.",
    "Wogole nie wiem, co wybrac.",
    "Te zdanie zawiera błąd.",
    "Używam telefon, laptop i tablet.",
    "Nie widzę kawa.",
    "Przyglądam się nowy budynek.",
    "To jest tekst bez zmian.",
)
CORRECTION_TEXTS = (
    "Zeby jutro,powiem o tym.",
    "Wogole nie wiem, co wybrac.",
    "To jest tekst bez zmian.",
    "Ona jestem tutaj.",
    "Nie widzę kawa.",
    "Używam telefon, laptop i tablet.",
    "Przyglądam się nowy budynek.",
    "Te zdanie zawiera błąd.",
)


def test_shared_analyzer_analyze_matches_sequential_results() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    expected = tuple(analyzer.analyze(text) for text in ANALYSIS_TEXTS)
    barrier = Barrier(len(ANALYSIS_TEXTS))

    def analyze_after_barrier(text: str) -> AnalysisResult:
        barrier.wait()
        return analyzer.analyze(text)

    with ThreadPoolExecutor(max_workers=len(ANALYSIS_TEXTS)) as executor:
        actual = tuple(executor.map(analyze_after_barrier, ANALYSIS_TEXTS))

    assert actual == expected


def test_shared_analyzer_correct_matches_sequential_results() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    expected = tuple(analyzer.correct(text) for text in CORRECTION_TEXTS)
    barrier = Barrier(len(CORRECTION_TEXTS))

    def correct_after_barrier(text: str) -> CorrectionResult:
        barrier.wait()
        return analyzer.correct(text)

    with ThreadPoolExecutor(max_workers=len(CORRECTION_TEXTS)) as executor:
        actual = tuple(executor.map(correct_after_barrier, CORRECTION_TEXTS))

    assert actual == expected


def test_shared_analyzer_repeated_analyze_is_stable() -> None:
    analyzer = Analyzer(AnalyzerConfig())
    expected = analyzer.analyze("Zeby jutro,powiem o tym.")

    for _ in range(32):
        assert analyzer.analyze("Zeby jutro,powiem o tym.") == expected


def test_lifecycle_contract_is_documented() -> None:
    quick_start = (ROOT / "docs" / "quick-start.md").read_text(encoding="utf-8")
    public_api = (ROOT / "docs" / "public-api.md").read_text(encoding="utf-8")

    assert "zbuduj raz" in quick_start.lower()
    assert "23,8 ms" in quick_start
    assert "0,047 ms" in quick_start
    assert "bezpieczna wątkowo" in public_api
    assert "analyze()`\ni `correct()`" in public_api
