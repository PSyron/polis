"""Experiment-only local LLM benchmark helpers for GitHub issue #42."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import time
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal, Protocol, cast
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from polis.core import AnalysisResult, Finding, PolisError
from polis.llm import build_prompt, validate_llm_response

_ALLOWED_VERIFICATION = frozenset({"rules", "llm_planned", "negative"})
_BENCHMARK_VERIFICATION = frozenset({"llm_planned", "negative"})
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_OLLAMA_DEFAULT_BASE_URL = "http://127.0.0.1:11434"
_OPENAI_COMPAT_BASE_URL = "http://127.0.0.1:8080"
_CASE_STATUSES = frozenset(
    {
        "valid",
        "valid_empty",
        "unavailable",
        "timed_out",
        "invalid_schema",
        "invalid_span",
        "duplicate",
        "conflict",
        "application_failure",
    }
)
_FINDING_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version", "findings"],
    "properties": {
        "schema_version": {"type": "integer", "const": 1},
        "findings": {"type": "array"},
    },
}

CaseStatus = Literal[
    "valid",
    "valid_empty",
    "unavailable",
    "timed_out",
    "invalid_schema",
    "invalid_span",
    "duplicate",
    "conflict",
    "application_failure",
]


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
    category_metrics: dict[str, CategoryMetrics] = field(default_factory=dict)


@dataclass(frozen=True)
class CaseScore:
    """Outcome of one model response against one gold case."""

    case_id: str
    exact_match: bool
    valid_response: bool
    elapsed_ms: float
    disqualified: bool


@dataclass(frozen=True)
class CaseEvidence:
    """Per-case metrics with identifiers only; never includes analyzed text."""

    case_id: str
    status: CaseStatus
    valid_response: bool
    exact_match: bool
    true_positives: int
    false_positives: int
    false_negatives: int
    elapsed_ms: float
    call_count: int


@dataclass(frozen=True)
class TimedResponse:
    """Raw local-model response together with wall-clock latency."""

    raw_response: str
    elapsed_ms: float


@dataclass(frozen=True)
class RuntimeMetadata:
    """Non-sensitive evidence collected before benchmark scoring begins."""

    engine: str
    model_identifier: str
    runtime_version: str | None
    artifact_revision: str | None = None
    quantization: str | None = None
    hardware_class: str | None = None
    loaded_memory_bytes: int | None = None
    cold_start: bool | None = None


class PromptClient(Protocol):
    """Minimal local transport needed by the benchmark runner."""

    def generate(self, prompt: str) -> TimedResponse:
        """Return one raw response with its elapsed time."""


class RuntimeClient(PromptClient, Protocol):
    """A benchmark transport that can be preflighted before corpus scoring."""

    def preflight(self) -> RuntimeMetadata:
        """Verify the local runtime and return non-text metadata."""


@dataclass(frozen=True)
class BenchmarkObservation:
    """A validated model response and its finding-level score for one case."""

    case: BenchmarkCase
    valid_response: bool
    elapsed_ms: float
    finding_score: FindingScore
    corrected_output: str
    status: CaseStatus = "valid"
    call_count: int = 1


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
    p95_latency_ms: float = 0.0
    throughput_chars_per_second: float = 0.0
    case_results: tuple[CaseScore, ...] = ()
    case_statuses: tuple[CaseStatus, ...] = ()
    case_evidence: tuple[CaseEvidence, ...] = ()
    corpus_sha256: str | None = None
    runtime_metadata: RuntimeMetadata | None = None

    @property
    def safety_eligible(self) -> bool:
        """Return whether every response is valid and every negative case is safe."""

        return (
            self.valid_responses == self.total_responses
            and not self.negative_cases_changed
            and all(status in {"valid", "valid_empty"} for status in self.case_statuses)
        )


@dataclass(frozen=True)
class OllamaClient:
    """Configuration boundary for an experiment-only localhost Ollama client."""

    base_url: str
    model: str
    timeout_seconds: float

    def __post_init__(self) -> None:
        _validate_loopback_base_url(self.base_url, "Ollama base")
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
                "format": _FINDING_RESPONSE_SCHEMA,
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

    def preflight(self) -> RuntimeMetadata:
        """Verify the requested local Ollama model before any corpus call."""

        version = _get_json(
            f"{self.base_url.rstrip('/')}/api/version", self.timeout_seconds
        )
        installed = _get_json(
            f"{self.base_url.rstrip('/')}/api/tags", self.timeout_seconds
        )
        processes = _get_json(
            f"{self.base_url.rstrip('/')}/api/ps", self.timeout_seconds
        )
        if (
            not isinstance(version, dict)
            or not isinstance(installed, dict)
            or not isinstance(processes, dict)
        ):
            raise ValueError("Ollama health response must be an object")
        runtime_version = version.get("version")
        if runtime_version is not None and not isinstance(runtime_version, str):
            raise ValueError("Ollama version must be a string")
        installed_models = installed.get("models")
        processes_models = processes.get("models")
        if not isinstance(installed_models, list) or not isinstance(
            processes_models, list
        ):
            raise ValueError("Ollama process response must contain models")
        if not any(
            isinstance(item, dict) and item.get("name") == self.model
            for item in installed_models
        ):
            raise OSError("requested Ollama model is unavailable")
        selected = next(
            (
                item
                for item in processes_models
                if isinstance(item, dict) and item.get("name") == self.model
            ),
            None,
        )
        loaded_memory = (
            None
            if selected is None
            else selected.get("size_vram", selected.get("size"))
        )
        if isinstance(loaded_memory, bool) or not isinstance(loaded_memory, int):
            loaded_memory = None
        return RuntimeMetadata(
            engine="ollama",
            model_identifier=self.model,
            runtime_version=runtime_version,
            loaded_memory_bytes=loaded_memory,
        )


@dataclass(frozen=True)
class OpenAICompatibleClient:
    """Minimal compatibility client for local OpenAI-style chat endpoints."""

    base_url: str
    model: str
    timeout_seconds: float
    request_path: str = "/v1/chat/completions"

    def __post_init__(self) -> None:
        _validate_loopback_base_url(self.base_url, "OpenAI-compatible base")
        if not self.model:
            raise ValueError("OpenAI-compatible model must be non-empty")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    def generate(self, prompt: str) -> TimedResponse:
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": 0,
                "max_tokens": 512,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "polis_finding_response_v1",
                        "strict": True,
                        "schema": _FINDING_RESPONSE_SCHEMA,
                    },
                },
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            f"{self.base_url.rstrip('/')}{self.request_path}",
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
            raise ValueError("OpenAI-compatible response must be an object")
        choices = envelope.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError(
                "OpenAI-compatible response must contain non-empty choices"
            )
        message = choices[0]
        if not isinstance(message, dict):
            raise ValueError("OpenAI-compatible choice must be an object")
        content = message.get("message")
        if not isinstance(content, dict) or not isinstance(content.get("content"), str):
            raise ValueError(
                "OpenAI-compatible response must contain choices[0].message.content"
            )
        return TimedResponse(
            raw_response=content["content"],
            elapsed_ms=elapsed_ms,
        )

    def preflight(self) -> RuntimeMetadata:
        """Verify a local OpenAI-compatible runtime without sending corpus text."""

        envelope = _get_json(
            f"{self.base_url.rstrip('/')}/v1/models", self.timeout_seconds
        )
        if not isinstance(envelope, dict):
            raise ValueError("OpenAI-compatible health response must be an object")
        models = envelope.get("data")
        if not isinstance(models, list):
            raise ValueError("OpenAI-compatible health response must contain data")
        identifiers = {
            item.get("id")
            for item in models
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        if identifiers and self.model not in identifiers:
            raise OSError("requested local model is unavailable")
        return RuntimeMetadata(
            engine="mlx",
            model_identifier=self.model,
            runtime_version=None,
        )


def _default_runtime_engine(requested_engine: str) -> str:
    """Resolve engine aliases and choose MLX first on macOS."""

    if requested_engine == "auto":
        if platform.system() == "Darwin":
            return "mlx"
        return "ollama"
    return requested_engine


def _default_base_url_for_engine(engine: str) -> str:
    """Return local defaults for benchmark-compatible runtimes."""

    if engine == "mlx":
        return _OPENAI_COMPAT_BASE_URL
    return _OLLAMA_DEFAULT_BASE_URL


def _validate_loopback_base_url(base_url: str, label: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"{label} URL must use HTTP")
    if parsed.hostname not in _LOOPBACK_HOSTS:
        raise ValueError(f"{label} URL must use a loopback host")


def _get_json(url: str, timeout_seconds: float) -> object:
    """Fetch a local health endpoint with no benchmark source text."""

    request = Request(url, method="GET")
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _build_client(
    *,
    engine: str,
    base_url: str,
    model: str,
    timeout_seconds: float,
) -> RuntimeClient:
    """Build a benchmark client for the selected local runtime."""

    engine = _default_runtime_engine(engine)
    if engine == "ollama":
        return OllamaClient(base_url, model, timeout_seconds)
    if engine == "mlx":
        return OpenAICompatibleClient(base_url, model, timeout_seconds)
    raise ValueError(f"unsupported benchmark engine: {engine!r}")


def select_healthy_client(
    requested_engine: str,
    candidates: Iterable[tuple[str, RuntimeClient]],
) -> tuple[str, RuntimeClient]:
    """Return the first healthy permitted runtime, or fail before scoring."""

    failures: list[str] = []
    for engine, client in candidates:
        if requested_engine != "auto" and engine != requested_engine:
            continue
        try:
            client.preflight()
        except (
            OSError,
            TimeoutError,
            URLError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            failures.append(f"{engine}: {classify_case_failure(error)}")
            continue
        return engine, client
    attempted = ", ".join(failures) or "no supported runtime candidates"
    raise RuntimeError(f"no healthy local runtime is available ({attempted})")


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
    categories = {item[0] for item in expected | observed}
    category_metrics: dict[str, CategoryMetrics] = {}
    for category in categories:
        expected_for_category = {item for item in expected if item[0] == category}
        observed_for_category = {item for item in observed if item[0] == category}
        category_metrics[category] = CategoryMetrics(
            true_positives=len(expected_for_category & observed_for_category),
            false_positives=len(observed_for_category - expected_for_category),
            false_negatives=len(expected_for_category - observed_for_category),
        )
    return FindingScore(
        true_positives=len(matched),
        false_positives=len(observed - expected),
        false_negatives=len(expected - observed),
        category_metrics=category_metrics,
    )


def classify_case_failure(error: BaseException) -> CaseStatus:
    """Map expected local failures to safe, source-text-free evidence states."""

    if isinstance(error, TimeoutError):
        return "timed_out"
    if isinstance(error, (OSError, URLError)):
        return "unavailable"
    message = str(error).lower()
    if "conflict" in message:
        return "conflict"
    if "duplicate" in message:
        return "duplicate"
    if (
        "range" in message
        or "outside the input text" in message
        or "original must match" in message
        or "original does not match" in message
    ):
        return "invalid_span"
    if isinstance(error, (json.JSONDecodeError, TypeError, ValueError)):
        return "invalid_schema"
    return "application_failure"


def summarize_observations(
    observations: Iterable[BenchmarkObservation],
) -> BenchmarkReport:
    """Aggregate exact findings by expected category and enforce safety basics."""

    collected = tuple(observations)
    if not collected:
        raise ValueError("benchmark requires at least one observation")

    metrics: dict[str, CategoryMetrics] = {}
    for observation in collected:
        category_scores = observation.finding_score.category_metrics
        if not category_scores:
            category_scores = {
                finding.category: CategoryMetrics(
                    true_positives=observation.finding_score.true_positives,
                    false_positives=observation.finding_score.false_positives,
                    false_negatives=observation.finding_score.false_negatives,
                )
                for finding in observation.case.expected_findings
            }
        for category, score in category_scores.items():
            current = metrics.get(category, CategoryMetrics(0, 0, 0))
            metrics[category] = CategoryMetrics(
                true_positives=current.true_positives + score.true_positives,
                false_positives=current.false_positives + score.false_positives,
                false_negatives=current.false_negatives + score.false_negatives,
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
    p95_latency_ms = _percentile(elapsed, 0.95)
    total_elapsed_ms = sum(elapsed)
    throughput = (
        sum(
            len(observation.case.source)
            for observation in collected
            if observation.valid_response
        )
        * 1_000
        / total_elapsed_ms
        if total_elapsed_ms
        else 0.0
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
        p95_latency_ms=p95_latency_ms,
        throughput_chars_per_second=throughput,
        case_results=tuple(
            score_case(
                observation.case,
                corrected_output=observation.corrected_output,
                valid_response=observation.valid_response,
                elapsed_ms=observation.elapsed_ms,
            )
            for observation in collected
        ),
        case_statuses=tuple(observation.status for observation in collected),
        case_evidence=tuple(
            CaseEvidence(
                case_id=observation.case.case_id,
                status=observation.status,
                valid_response=observation.valid_response,
                exact_match=observation.corrected_output
                == observation.case.expected_output,
                true_positives=observation.finding_score.true_positives,
                false_positives=observation.finding_score.false_positives,
                false_negatives=observation.finding_score.false_negatives,
                elapsed_ms=observation.elapsed_ms,
                call_count=observation.call_count,
            )
            for observation in collected
        ),
    )


def _percentile(sorted_values: list[float], percentile: float) -> float:
    """Return a deterministic nearest-rank percentile for latency evidence."""

    if not sorted_values:
        return 0.0
    index = max(0, math.ceil(len(sorted_values) * percentile) - 1)
    return sorted_values[index]


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
        except Exception as error:
            observations.append(
                BenchmarkObservation(
                    case=case,
                    valid_response=False,
                    elapsed_ms=0.0,
                    finding_score=FindingScore(0, 0, 0),
                    corrected_output=case.source,
                    status=classify_case_failure(error),
                )
            )
            continue

        if len({finding.id for finding in findings}) != len(findings):
            observations.append(
                BenchmarkObservation(
                    case=case,
                    valid_response=True,
                    elapsed_ms=response.elapsed_ms,
                    finding_score=score_findings(case, findings),
                    corrected_output=case.source,
                    status="duplicate",
                )
            )
            continue

        try:
            corrected_output = corrected_output_from_findings(case.source, findings)
        except (PolisError, TypeError, ValueError) as error:
            observations.append(
                BenchmarkObservation(
                    case=case,
                    valid_response=True,
                    elapsed_ms=response.elapsed_ms,
                    finding_score=score_findings(case, findings),
                    corrected_output=case.source,
                    status=classify_case_failure(error),
                )
            )
            continue

        observations.append(
            BenchmarkObservation(
                case=case,
                valid_response=True,
                elapsed_ms=response.elapsed_ms,
                finding_score=score_findings(case, findings),
                corrected_output=corrected_output,
                status="valid_empty" if not findings else "valid",
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
            "p95_latency_ms": report.p95_latency_ms,
            "throughput_chars_per_second": report.throughput_chars_per_second,
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
            "corpus_sha256": report.corpus_sha256,
            "runtime": None
            if report.runtime_metadata is None
            else {
                "artifact_revision": report.runtime_metadata.artifact_revision,
                "cold_start": report.runtime_metadata.cold_start,
                "engine": report.runtime_metadata.engine,
                "hardware_class": report.runtime_metadata.hardware_class,
                "loaded_memory_bytes": report.runtime_metadata.loaded_memory_bytes,
                "model_identifier": report.runtime_metadata.model_identifier,
                "quantization": report.runtime_metadata.quantization,
                "runtime_version": report.runtime_metadata.runtime_version,
            },
            "cases": [
                {
                    "call_count": item.call_count,
                    "elapsed_ms": item.elapsed_ms,
                    "exact_match": item.exact_match,
                    "false_negatives": item.false_negatives,
                    "false_positives": item.false_positives,
                    "id": item.case_id,
                    "status": item.status,
                    "true_positives": item.true_positives,
                    "valid_response": item.valid_response,
                }
                for item in report.case_evidence
            ],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Run the local benchmark and print its machine-readable evidence."""

    parser = argparse.ArgumentParser(
        description=(
            "Benchmark a local Polish correction model against the Polis E2E corpus."
        )
    )
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=Path("tests/fixtures/e2e/polish_correction_corpus.json"),
    )
    parser.add_argument(
        "--engine",
        default="auto",
        choices=("auto", "ollama", "mlx"),
        help=(
            "Runtime used to serve the local model. 'auto' prefers MLX on macOS "
            "and Ollama elsewhere."
        ),
    )
    parser.add_argument("--base-url")
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--artifact-revision")
    parser.add_argument("--quantization")
    parser.add_argument("--hardware-class", default=platform.platform())
    parser.add_argument("--cold-start", action="store_true")
    arguments = parser.parse_args(argv)
    candidate_engines = (
        ("mlx", "ollama")
        if arguments.engine == "auto" and platform.system() == "Darwin"
        else ("ollama", "mlx")
        if arguments.engine == "auto"
        else (arguments.engine,)
    )
    candidates = tuple(
        (
            engine,
            _build_client(
                engine=engine,
                base_url=arguments.base_url
                if arguments.base_url is not None
                else _default_base_url_for_engine(engine),
                model=arguments.model,
                timeout_seconds=arguments.timeout_seconds,
            ),
        )
        for engine in candidate_engines
    )
    selected_engine, client = select_healthy_client(arguments.engine, candidates)
    runtime_metadata = client.preflight()
    if runtime_metadata.engine != selected_engine:
        raise RuntimeError("runtime preflight returned an unexpected engine")
    runtime_metadata = replace(
        runtime_metadata,
        artifact_revision=arguments.artifact_revision,
        quantization=arguments.quantization,
        hardware_class=arguments.hardware_class,
        cold_start=arguments.cold_start,
    )
    cases = load_cases(arguments.corpus)
    report = summarize_observations(run_cases(client, cases))
    report = replace(
        report,
        corpus_sha256=hashlib.sha256(arguments.corpus.read_bytes()).hexdigest(),
        runtime_metadata=runtime_metadata,
    )
    print(report_as_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
