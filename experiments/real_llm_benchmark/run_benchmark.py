"""Experiment-only local LLM benchmark helpers for GitHub issue #42."""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from polis.core import AnalysisResult, Finding
from polis.llm import build_prompt, validate_llm_response

_ALLOWED_VERIFICATION = frozenset({"rules", "llm_planned", "negative"})
_BENCHMARK_VERIFICATION = frozenset({"llm_planned", "negative"})
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


@dataclass(frozen=True)
class BenchmarkCase:
    """One gold corpus case evaluated by a real local model."""

    case_id: str
    source: str
    expected_output: str
    tags: tuple[str, ...]
    verification: str
    tracking_issue: int | None
    expected_findings: tuple[GoldFinding, ...]


@dataclass(frozen=True)
class GoldFinding:
    """One exact gold correction used for finding-level benchmark metrics."""

    category: str
    start: int
    end: int
    original: str
    suggestion: str


@dataclass(frozen=True)
class FindingScore:
    """Exact matching counts for one benchmark case."""

    true_positives: int
    false_positives: int
    false_negatives: int


@dataclass(frozen=True)
class CaseScore:
    """Outcome of one model response against one gold case."""

    case_id: str
    exact_match: bool
    valid_response: bool
    elapsed_ms: float
    disqualified: bool


@dataclass(frozen=True)
class TimedResponse:
    """Raw local-model response together with wall-clock latency."""

    raw_response: str
    elapsed_ms: float


class PromptClient(Protocol):
    """Minimal local transport needed by the benchmark runner."""

    def generate(self, prompt: str) -> TimedResponse:
        """Return one raw response with its elapsed time."""


@dataclass(frozen=True)
class BenchmarkObservation:
    """A validated model response and its finding-level score for one case."""

    case: BenchmarkCase
    valid_response: bool
    elapsed_ms: float
    finding_score: FindingScore
    corrected_output: str


@dataclass(frozen=True)
class CategoryMetrics:
    """Precision, recall, and F1 derived from exact finding matches."""

    true_positives: int
    false_positives: int
    false_negatives: int

    @property
    def precision(self) -> float:
        denominator = self.true_positives + self.false_positives
        return self.true_positives / denominator if denominator else 0.0

    @property
    def recall(self) -> float:
        denominator = self.true_positives + self.false_negatives
        return self.true_positives / denominator if denominator else 0.0

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return 2 * self.precision * self.recall / denominator if denominator else 0.0


@dataclass(frozen=True)
class BenchmarkReport:
    """Aggregate benchmark evidence, excluding any unmeasured selection threshold."""

    valid_responses: int
    total_responses: int
    negative_cases_changed: int
    median_latency_ms: float
    overall_metrics: CategoryMetrics
    category_metrics: dict[str, CategoryMetrics]

    @property
    def safety_eligible(self) -> bool:
        """Return whether every response is valid and every negative case is safe."""

        return (
            self.valid_responses == self.total_responses
            and not self.negative_cases_changed
        )


@dataclass(frozen=True)
class OllamaClient:
    """Configuration boundary for an experiment-only localhost Ollama client."""

    base_url: str
    model: str
    timeout_seconds: float

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Ollama base URL must use HTTP")
        if parsed.hostname not in _LOOPBACK_HOSTS:
            raise ValueError("Ollama base URL must use a loopback host")
        if not self.model:
            raise ValueError("Ollama model must be non-empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def generate(self, prompt: str) -> TimedResponse:
        """Request one non-streaming JSON response from local Ollama chat."""

        payload = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
                "think": False,
                "options": {"num_predict": 512, "seed": 42, "temperature": 0},
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            f"{self.base_url.rstrip('/')}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            raw_envelope = response.read().decode("utf-8")
        elapsed_ms = (time.perf_counter() - started) * 1_000
        envelope = json.loads(raw_envelope)
        if not isinstance(envelope, dict):
            raise ValueError("Ollama response must be an object")
        message = envelope.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise ValueError("Ollama chat response must contain message.content")
        return TimedResponse(
            raw_response=message["content"],
            elapsed_ms=elapsed_ms,
        )


def load_cases(path: Path) -> tuple[BenchmarkCase, ...]:
    """Load the planned-LLM and no-change cases from corpus v2."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("cases"), list):
        raise ValueError("benchmark corpus must contain a cases list")

    cases: list[BenchmarkCase] = []
    for item in raw["cases"]:
        if not isinstance(item, dict):
            raise ValueError("benchmark corpus case must be an object")
        verification = item.get("verification")
        if verification not in _ALLOWED_VERIFICATION:
            raise ValueError(f"unknown verification mode: {verification!r}")
        if verification not in _BENCHMARK_VERIFICATION:
            continue

        tracking_issue = item.get("tracking_issue")
        if tracking_issue is not None and not isinstance(tracking_issue, int):
            raise ValueError("tracking_issue must be an integer")
        tags = item.get("tags")
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise ValueError("benchmark case tags must be a string list")

        case_id = item.get("id")
        source = item.get("input")
        expected_output = item.get("expected_output")
        expected_findings = _load_expected_findings(item, source)
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("benchmark case id must be a non-empty string")
        if not isinstance(source, str) or not source:
            raise ValueError("benchmark case input must be a non-empty string")
        if not isinstance(expected_output, str) or not expected_output:
            raise ValueError(
                "benchmark case expected_output must be a non-empty string"
            )
        cases.append(
            BenchmarkCase(
                case_id=case_id,
                source=source,
                expected_output=expected_output,
                tags=tuple(tags),
                verification=verification,
                tracking_issue=tracking_issue,
                expected_findings=expected_findings,
            )
        )

    if not cases:
        raise ValueError("benchmark corpus contains no planned or negative cases")
    return tuple(cases)


def _load_expected_findings(
    item: dict[str, object], source: object
) -> tuple[GoldFinding, ...]:
    raw_findings = item.get("expected_findings")
    if not isinstance(raw_findings, list):
        raise ValueError("benchmark case expected_findings must be a list")
    if not isinstance(source, str):
        raise ValueError("benchmark case input must be a non-empty string")

    findings: list[GoldFinding] = []
    for finding in raw_findings:
        if not isinstance(finding, dict):
            raise ValueError("expected finding must be an object")
        category = finding.get("category")
        start = finding.get("start")
        end = finding.get("end")
        original = finding.get("original")
        suggestion = finding.get("suggestion")
        if not isinstance(category, str) or not category:
            raise ValueError("expected finding category must be a non-empty string")
        if isinstance(start, bool) or not isinstance(start, int):
            raise ValueError("expected finding start must be an integer")
        if isinstance(end, bool) or not isinstance(end, int):
            raise ValueError("expected finding end must be an integer")
        if not isinstance(original, str) or not isinstance(suggestion, str):
            raise ValueError("expected finding text fields must be strings")
        if start < 0 or end < start or end > len(source):
            raise ValueError("expected finding must have an in-bounds range")
        if source[start:end] != original:
            raise ValueError("expected finding original must match its input range")
        findings.append(GoldFinding(category, start, end, original, suggestion))
    return tuple(findings)


def score_case(
    case: BenchmarkCase,
    *,
    corrected_output: str,
    valid_response: bool,
    elapsed_ms: float,
) -> CaseScore:
    """Score exact output and disqualify invalid or negative-changing responses."""

    exact_match = corrected_output == case.expected_output
    return CaseScore(
        case_id=case.case_id,
        exact_match=exact_match,
        valid_response=valid_response,
        elapsed_ms=elapsed_ms,
        disqualified=not valid_response
        or (case.verification == "negative" and not exact_match),
    )


def corrected_output_from_findings(source: str, findings: Iterable[Finding]) -> str:
    """Apply every validated, correctable finding for an exact-output score."""

    selected = tuple(finding for finding in findings if finding.suggestion is not None)
    return cast(
        str,
        AnalysisResult(source, selected).apply(finding.id for finding in selected),
    )


def score_findings(case: BenchmarkCase, findings: Iterable[Finding]) -> FindingScore:
    """Score only exact category, offset, source-text, and correction matches."""

    expected = {
        (item.category, item.start, item.end, item.original, item.suggestion)
        for item in case.expected_findings
    }
    observed = {
        (
            finding.category.value,
            finding.start,
            finding.end,
            finding.original,
            finding.suggestion,
        )
        for finding in findings
    }
    matched = expected & observed
    return FindingScore(
        true_positives=len(matched),
        false_positives=len(observed - expected),
        false_negatives=len(expected - observed),
    )


def summarize_observations(
    observations: Iterable[BenchmarkObservation],
) -> BenchmarkReport:
    """Aggregate exact findings by expected category and enforce safety basics."""

    collected = tuple(observations)
    if not collected:
        raise ValueError("benchmark requires at least one observation")

    metrics: dict[str, CategoryMetrics] = {}
    for observation in collected:
        categories = {
            finding.category for finding in observation.case.expected_findings
        }
        for category in categories:
            current = metrics.get(category, CategoryMetrics(0, 0, 0))
            expected_count = sum(
                finding.category == category
                for finding in observation.case.expected_findings
            )
            true_positives = min(
                observation.finding_score.true_positives,
                expected_count,
            )
            metrics[category] = CategoryMetrics(
                true_positives=current.true_positives + true_positives,
                false_positives=current.false_positives,
                false_negatives=current.false_negatives
                + max(expected_count - true_positives, 0),
            )

    negative_cases_changed = sum(
        observation.case.verification == "negative"
        and observation.corrected_output != observation.case.expected_output
        for observation in collected
    )
    elapsed = sorted(
        observation.elapsed_ms
        for observation in collected
        if observation.valid_response
    )
    midpoint = len(elapsed) // 2
    median_latency_ms = (
        0.0
        if not elapsed
        else elapsed[midpoint]
        if len(elapsed) % 2
        else (elapsed[midpoint - 1] + elapsed[midpoint]) / 2
    )
    return BenchmarkReport(
        valid_responses=sum(observation.valid_response for observation in collected),
        total_responses=len(collected),
        negative_cases_changed=negative_cases_changed,
        median_latency_ms=median_latency_ms,
        overall_metrics=CategoryMetrics(
            true_positives=sum(
                observation.finding_score.true_positives for observation in collected
            ),
            false_positives=sum(
                observation.finding_score.false_positives for observation in collected
            ),
            false_negatives=sum(
                observation.finding_score.false_negatives for observation in collected
            ),
        ),
        category_metrics=metrics,
    )


def run_cases(
    client: PromptClient,
    cases: Iterable[BenchmarkCase],
) -> tuple[BenchmarkObservation, ...]:
    """Run an experiment without letting an invalid model response stop it."""

    observations: list[BenchmarkObservation] = []
    for case in cases:
        try:
            response = client.generate(build_prompt(case.source))
            findings = validate_llm_response(
                response.raw_response,
                source_text=case.source,
                source_name=f"benchmark-{case.case_id}",
            )
        except (OSError, TimeoutError, TypeError, ValueError, json.JSONDecodeError):
            observations.append(
                BenchmarkObservation(
                    case=case,
                    valid_response=False,
                    elapsed_ms=0.0,
                    finding_score=FindingScore(0, 0, 0),
                    corrected_output=case.source,
                )
            )
            continue

        observations.append(
            BenchmarkObservation(
                case=case,
                valid_response=True,
                elapsed_ms=response.elapsed_ms,
                finding_score=score_findings(case, findings),
                corrected_output=corrected_output_from_findings(case.source, findings),
            )
        )
    return tuple(observations)


def report_as_json(report: BenchmarkReport) -> str:
    """Serialize aggregate evidence in a deterministic, audit-friendly form."""

    return json.dumps(
        {
            "category_metrics": {
                category: {
                    "f1": metrics.f1,
                    "false_negatives": metrics.false_negatives,
                    "false_positives": metrics.false_positives,
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "true_positives": metrics.true_positives,
                }
                for category, metrics in sorted(report.category_metrics.items())
            },
            "safety_eligible": report.safety_eligible,
            "median_latency_ms": report.median_latency_ms,
            "negative_cases_changed": report.negative_cases_changed,
            "overall_metrics": {
                "f1": report.overall_metrics.f1,
                "false_negatives": report.overall_metrics.false_negatives,
                "false_positives": report.overall_metrics.false_positives,
                "precision": report.overall_metrics.precision,
                "recall": report.overall_metrics.recall,
                "true_positives": report.overall_metrics.true_positives,
            },
            "total_responses": report.total_responses,
            "valid_responses": report.valid_responses,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the local benchmark and print its machine-readable evidence."""

    parser = argparse.ArgumentParser(
        description="Benchmark a local Ollama model against the Polis E2E corpus."
    )
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("tests/fixtures/e2e/polish_correction_corpus.json"),
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    arguments = parser.parse_args(argv)

    client = OllamaClient(
        base_url=arguments.base_url,
        model=arguments.model,
        timeout_seconds=arguments.timeout_seconds,
    )
    report = summarize_observations(run_cases(client, load_cases(arguments.corpus)))
    print(report_as_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
