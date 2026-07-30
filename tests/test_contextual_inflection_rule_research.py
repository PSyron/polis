from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from experiments.sentence_safety_gate.gate import load_development_sentences

from polis import Analyzer, AnalyzerConfig

pytestmark = pytest.mark.research


class FakeContextTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[tuple[int, int], ...], float]] = []

    def synthesize_context(
        self,
        text: str,
        *,
        spans: tuple[tuple[int, int], ...],
        timeout_seconds: float,
    ) -> Mapping[str, object]:
        self.calls.append((text, spans, timeout_seconds))
        raise AssertionError("protected development cases must not call transport")


def test_contextual_inflection_abstains_on_protected_development_cases() -> None:
    cases = load_development_sentences(
        Path("tests/fixtures/evaluation/polish_correction_safety_corpus_v1.xml")
    )
    protected = tuple(case for case in cases if case.protected_negative)
    transport = FakeContextTransport()
    analyzer = Analyzer(AnalyzerConfig(), contextual_inflection_transport=transport)

    results = tuple(analyzer.analyze(case.source) for case in protected)

    assert len(protected) == 20
    assert all(
        str(finding.source) != "rule:languagetool.contextual_inflection"
        for result in results
        for finding in result.issues
    )
    assert transport.calls == []
