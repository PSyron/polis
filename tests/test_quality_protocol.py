from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest

from polis.core import Category, Confidence, Finding, Source
from polis.core.models import Severity
from polis.evaluation.dataset import EvaluationCase, EvaluationDataset, ExpectedFinding
from polis.evaluation.quality_protocol import (
    NonDeterministicBaselineError,
    RunIdentity,
    UnsupportedRssPlatformError,
    peak_rss_bytes,
    run_quality_protocol,
)


def _dataset(*, correct_only: bool = False) -> EvaluationDataset:
    correct_case = EvaluationCase(
        id="correct_case",
        outcome="correct",
        text="Dobrze.",
        findings=(),
    )
    if correct_only:
        return EvaluationDataset(
            schema_version=1,
            id="synthetic_quality",
            cases=(correct_case,),
            source="memory",
            canonical_hash="a" * 64,
        )
    incorrect_case = EvaluationCase(
        id="spelling_case",
        outcome="incorrect",
        text="Zeby.",
        findings=(
            ExpectedFinding(
                category="spelling",
                start=0,
                end=4,
                original="Zeby",
                suggestion="Żeby",
                rationale="Synthetic exact edit.",
            ),
        ),
    )
    return EvaluationDataset(
        schema_version=1,
        id="synthetic_quality",
        cases=(incorrect_case, correct_case),
        source="memory",
        canonical_hash="a" * 64,
    )


def _finding(*, suggestion: str = "Żeby") -> Finding:
    return Finding.create(
        category=Category.SPELLING,
        severity=Severity.ERROR,
        message="Literówka.",
        explanation="Syntetyczne znalezisko testowe.",
        original="Zeby",
        suggestion=suggestion,
        start=0,
        end=4,
        confidence=Confidence(1.0),
        source=Source.parse("rule:test"),
    )


def _identity() -> RunIdentity:
    return RunIdentity(
        analyzer="Analyzer(AnalyzerConfig())",
        artifact_sha256="b" * 64,
        package_version="1.0.0",
        python_version="3.13.5",
        platform_system="Darwin",
        platform_release="25.0.0",
        platform_machine="arm64",
        dataset_schema_id="polis.quality-dataset",
        dataset_schema_version=1,
        manifest_schema_id="polis.quality-dataset-manifest",
        manifest_schema_version=1,
        manifest_sha256="c" * 64,
    )


def _clock(values: tuple[int, ...]) -> Iterator[int]:
    yield from values


def test_protocol_reports_exact_quality_latency_throughput_and_rss() -> None:
    dataset = _dataset()
    analyzer_calls: list[str] = []

    def analyzer(text: str) -> tuple[Finding, ...]:
        analyzer_calls.append(text)
        return (_finding(),) if text == "Zeby." else ()

    clock = _clock((0, 100, 100, 400, 400, 900, 900, 1600))

    result = run_quality_protocol(
        dataset=dataset,
        analyzer=analyzer,
        run_identity=_identity(),
        warmup_repetitions=1,
        measured_repetitions=2,
        clock_ns=lambda: next(clock),
        rss_probe=lambda: 12_345,
    )

    assert analyzer_calls == [
        "Zeby.",
        "Dobrze.",
        "Zeby.",
        "Dobrze.",
        "Zeby.",
        "Dobrze.",
    ]
    assert result.baseline.aggregate.true_positives == 1
    assert result.baseline.aggregate.false_positives == 0
    assert result.baseline.aggregate.false_negatives == 0
    assert result.baseline.aggregate.exact_edit_precision == 1.0
    assert result.baseline.aggregate.exact_edit_recall == 1.0
    assert result.baseline.aggregate.exact_edit_f1 == 1.0
    assert result.baseline.aggregate.span_accuracy == 1.0
    assert result.baseline.aggregate.correction_accuracy == 1.0
    assert result.baseline.aggregate.correct_sentence_false_alarm_rate == 0.0
    assert result.latency.sample_count == 4
    assert result.latency.min_ns == 100
    assert result.latency.mean_ns == 400
    assert result.latency.p50_ns == 300
    assert result.latency.p95_ns == 700
    assert result.latency.max_ns == 700
    assert result.throughput.measured_cases == 4
    assert result.throughput.measured_code_points == 24
    assert result.throughput.total_duration_ns == 1_600
    assert result.throughput.cases_per_second == 2_500_000.0
    assert result.throughput.code_points_per_second == 15_000_000.0
    assert result.resources.peak_rss_bytes == 12_345
    assert len(result.repetition_hashes) == 2
    assert result.repetition_hashes[0] == result.repetition_hashes[1]


def test_protocol_preserves_undefined_quality_ratios() -> None:
    result = run_quality_protocol(
        dataset=_dataset(correct_only=True),
        analyzer=lambda _text: (),
        run_identity=_identity(),
        warmup_repetitions=0,
        measured_repetitions=2,
        clock_ns=lambda: 0,
        rss_probe=lambda: 0,
    )

    assert result.baseline.aggregate.exact_edit_precision is None
    assert result.baseline.aggregate.exact_edit_recall is None
    assert result.baseline.aggregate.exact_edit_f1 is None
    assert result.baseline.aggregate.span_accuracy is None
    assert result.baseline.aggregate.correction_accuracy is None
    assert result.baseline.aggregate.correct_sentence_false_alarm_rate == 0.0


@pytest.mark.parametrize(
    ("system", "raw_rss", "expected_bytes"),
    (("Darwin", 12_345, 12_345), ("Linux", 12_345, 12_641_280)),
)
def test_peak_rss_bytes_normalizes_supported_platforms(
    monkeypatch: pytest.MonkeyPatch,
    system: str,
    raw_rss: int,
    expected_bytes: int,
) -> None:
    monkeypatch.setattr(
        "polis.evaluation.quality_protocol.platform.system", lambda: system
    )
    monkeypatch.setattr(
        "polis.evaluation.quality_protocol.resource.getrusage",
        lambda _who: SimpleNamespace(ru_maxrss=raw_rss),
    )

    assert peak_rss_bytes() == expected_bytes


def test_peak_rss_bytes_rejects_unsupported_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "polis.evaluation.quality_protocol.platform.system", lambda: "Windows"
    )

    with pytest.raises(
        UnsupportedRssPlatformError,
        match="peak RSS measurement is unsupported on platform: Windows",
    ):
        peak_rss_bytes()


def test_protocol_rejects_nondeterministic_findings() -> None:
    calls = 0

    def analyzer(text: str) -> tuple[Finding, ...]:
        nonlocal calls
        if text != "Zeby.":
            return ()
        calls += 1
        return (_finding(suggestion="Żeby" if calls == 1 else "Aby"),)

    with pytest.raises(
        NonDeterministicBaselineError,
        match="baseline findings changed between measured repetitions",
    ):
        run_quality_protocol(
            dataset=_dataset(),
            analyzer=analyzer,
            run_identity=_identity(),
            warmup_repetitions=0,
            measured_repetitions=2,
            clock_ns=lambda: 0,
            rss_probe=lambda: 0,
        )
