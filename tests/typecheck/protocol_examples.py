"""Strict static conformance checks for the M0 protocol boundaries."""

from polis import AnalysisOptions, AnalysisResult
from polis.core import Finding, Source
from polis.core.protocols import (
    AnalysisOrchestrator,
    DeterministicAnalyzer,
    LocalGenerationBackend,
    MonotonicClock,
    Rule,
    RuleRegistry,
)


class StrictRule:
    source: Source = Source.parse("rule:strict")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return ()


class StrictAnalyzer:
    source: Source = Source.parse("rule:strict-analyzer")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return ()


class StrictRegistry:
    def rules(self) -> tuple[Rule, ...]:
        return (StrictRule(),)


class StrictBackend:
    name: str = "strict-local"

    async def generate(self, prompt: str) -> str:
        return "{}"


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
clock: MonotonicClock = StrictClock()
orchestrator: AnalysisOrchestrator = StrictOrchestrator()

assert rule.source.name == "strict"
assert analyzer.source.name == "strict-analyzer"
assert registry.rules() == (rule,)
assert backend.name == "strict-local"
assert clock.monotonic() == 0.0
