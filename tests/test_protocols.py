from __future__ import annotations

import ast
from pathlib import Path

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

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_MODULE = ROOT / "src" / "polis" / "core" / "protocols.py"
DOCUMENTATION = ROOT / "docs" / "architecture" / "protocols.md"


class FakeRule:
    source = Source.parse("rule:example")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return ()


class FakeDeterministicAnalyzer:
    source = Source.parse("rule:aggregate")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return ()


class FakeRuleRegistry:
    def rules(self) -> tuple[Rule, ...]:
        return (FakeRule(),)


class FakeBackend:
    name = "local-fake"

    async def generate(self, prompt: str) -> str:
        return '{"findings": []}'


class FakeClock:
    def monotonic(self) -> float:
        return 0.0


class FakeOrchestrator:
    def analyze(self, text: str, *, options: AnalysisOptions) -> AnalysisResult:
        return AnalysisResult(text=text, options=options)

    async def analyze_async(
        self, text: str, *, options: AnalysisOptions
    ) -> AnalysisResult:
        return AnalysisResult(text=text, options=options)


def test_strict_fakes_structurally_satisfy_runtime_protocols() -> None:
    assert isinstance(FakeRule(), Rule)
    assert isinstance(FakeDeterministicAnalyzer(), DeterministicAnalyzer)
    assert isinstance(FakeRuleRegistry(), RuleRegistry)
    assert isinstance(FakeBackend(), LocalGenerationBackend)
    assert isinstance(FakeClock(), MonotonicClock)
    assert isinstance(FakeOrchestrator(), AnalysisOrchestrator)


def test_protocol_module_has_no_concrete_nlp_or_model_server_import() -> None:
    tree = ast.parse(PROTOCOL_MODULE.read_text(encoding="utf-8"))
    imported_roots = {
        alias.name.split(".", maxsplit=1)[0]
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }

    assert not imported_roots & {
        "spacy",
        "stanza",
        "morfeusz2",
        "requests",
        "httpx",
        "ollama",
    }


def test_protocol_documentation_records_lifecycle_and_failure_ownership() -> None:
    documentation = DOCUMENTATION.read_text(encoding="utf-8")

    for heading in (
        "## DeterministicAnalyzer",
        "## Rule",
        "## RuleRegistry",
        "## LocalGenerationBackend",
        "## MonotonicClock",
        "## AnalysisOrchestrator",
    ):
        assert heading in documentation
    for statement in (
        "No partial `AnalysisResult` is returned.",
        "Cancellation and deadline ownership belongs to the orchestrator.",
        "Retry policy is intentionally not a protocol yet.",
    ):
        assert statement in documentation
