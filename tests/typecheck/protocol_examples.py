"""Strict static conformance checks for the M0 protocol boundaries."""

from collections.abc import Awaitable, Callable
from typing import Any

from polis import AnalysisOptions, AnalysisResult
from polis.core import Finding, Source
from polis.core.protocols import (
    AnalysisOrchestrator,
    DeterministicAnalyzer,
    LocalFindingBackend,
    LocalGenerationBackend,
    MonotonicClock,
    Rule,
    RuleRegistry,
)
from polis.llm import MockHeuristicBackend, MockHeuristicTransport
from polis.rules import DeterministicRuleRegistry


class StrictRule:
    source: Source = Source.parse("rule:strict")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return ()


class StrictAnalyzer:
    source: Source = Source.parse("rule:strict-analyzer")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return ()


class StrictRegistry:
    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return StrictRule().find(text, options=options)


class StrictBackend:
    name: str = "strict-local"

    async def generate(self, prompt: str) -> str:
        return "{}"


async def strict_sleep(_seconds: float) -> None:
    return None


class StrictFindingBackend:
    name: str = "strict-findings"

    async def generate_findings(
        self,
        text: str,
        *,
        policy: Any = None,
        clock: MonotonicClock | None = None,
        sleep: Callable[[float], Awaitable[None]] = strict_sleep,
        operation: str = "analysis.llm.generate",
    ) -> tuple[Finding, ...]:
        return ()


class StrictClock:
    def monotonic(self) -> float:
        return 0.0


class StrictOrchestrator:
    def analyze(self, text: str, *, options: AnalysisOptions) -> AnalysisResult:
        return AnalysisResult(text=text, options=options)

    async def analyze_async(
        self, text: str, *, options: AnalysisOptions
    ) -> AnalysisResult:
        return AnalysisResult(text=text, options=options)


rule: Rule = StrictRule()
analyzer: DeterministicAnalyzer = StrictAnalyzer()
registry: RuleRegistry = StrictRegistry()
backend: LocalGenerationBackend = StrictBackend()
finding_backend: LocalFindingBackend = StrictFindingBackend()
clock: MonotonicClock = StrictClock()
orchestrator: AnalysisOrchestrator = StrictOrchestrator()
runtime_registry: RuleRegistry = DeterministicRuleRegistry(())
runtime_backend = MockHeuristicBackend(transport=MockHeuristicTransport())
runtime_raw_backend: LocalGenerationBackend = runtime_backend
runtime_finding_backend: LocalFindingBackend = runtime_backend

assert rule.source.name == "strict"
assert analyzer.source.name == "strict-analyzer"
assert registry.find("Tekst", options=AnalysisOptions()) == ()
assert backend.name == "strict-local"
assert finding_backend.name == "strict-findings"
assert clock.monotonic() == 0.0
