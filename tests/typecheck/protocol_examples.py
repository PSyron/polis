"""Strict static conformance checks for the M0 protocol boundaries."""

from polis import AnalysisOptions, AnalysisResult
from polis.core import Finding, Source
from polis.core.protocols import (
    AnalysisOrchestrator,
    DeterministicAnalyzer,
    Rule,
    RuleRegistry,
)
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
orchestrator: AnalysisOrchestrator = StrictOrchestrator()
runtime_registry: RuleRegistry = DeterministicRuleRegistry(())

assert rule.source.name == "strict"
assert analyzer.source.name == "strict-analyzer"
assert registry.find("Tekst", options=AnalysisOptions()) == ()
