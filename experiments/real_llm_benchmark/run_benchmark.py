"""Experiment-only local LLM benchmark helpers for GitHub issue #42."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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
        """Request one non-streaming, JSON-mode response from local Ollama."""

        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"seed": 42, "temperature": 0},
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        request = Request(
            f"{self.base_url.rstrip('/')}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        started = time.perf_counter()
        with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
            raw_envelope = response.read().decode("utf-8")
        elapsed_ms = (time.perf_counter() - started) * 1_000
        envelope = json.loads(raw_envelope)
        if not isinstance(envelope, dict) or not isinstance(
            envelope.get("response"), str
        ):
            raise ValueError("Ollama response must contain a string response field")
        return TimedResponse(
            raw_response=envelope["response"],
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
            )
        )

    if not cases:
        raise ValueError("benchmark corpus contains no planned or negative cases")
    return tuple(cases)


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
