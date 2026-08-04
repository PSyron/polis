from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import polis.core as core_module
import polis.core.protocols as protocol_module
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
    VersionedRule,
)
from polis.llm import MockHeuristicBackend, MockHeuristicTransport
from polis.rules import DeterministicRuleRegistry

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_MODULE = ROOT / "src" / "polis" / "core" / "protocols.py"
DOCUMENTATION = ROOT / "docs" / "architecture" / "protocols.md"
PIPELINE = ROOT / "src" / "polis" / "analysis" / "pipeline.py"
TYPECHECK_RUNNER = ROOT / "scripts" / "typecheck_protocols.py"


class FakeRule:
    source = Source.parse("rule:example")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return ()


class FakeVersionedRule(FakeRule):
    operation = "replace.example"
    behavior_version = "example-rule/1.0"


class FakeDeterministicAnalyzer:
    source = Source.parse("rule:aggregate")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return ()


class FakeRuleRegistry:
    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        return FakeRule().find(text, options=options)


class FakeBackend:
    name = "local-fake"

    async def generate(self, prompt: str) -> str:
        return '{"findings": []}'


class FakeFindingBackend:
    name = "local-finding-fake"

    async def generate_findings(
        self,
        text: str,
        *,
        policy: object | None = None,
        clock: MonotonicClock | None = None,
        sleep: object = None,
        operation: str = "analysis.llm.generate",
    ) -> tuple[Finding, ...]:
        return ()


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
    assert not isinstance(FakeRule(), VersionedRule)
    assert isinstance(FakeVersionedRule(), VersionedRule)
    assert isinstance(FakeDeterministicAnalyzer(), DeterministicAnalyzer)
    assert isinstance(FakeRuleRegistry(), RuleRegistry)
    assert isinstance(FakeBackend(), LocalGenerationBackend)
    assert isinstance(FakeFindingBackend(), LocalFindingBackend)
    assert isinstance(FakeClock(), MonotonicClock)
    assert isinstance(FakeOrchestrator(), AnalysisOrchestrator)


def test_composed_runtime_implementations_satisfy_public_protocols() -> None:
    registry = DeterministicRuleRegistry(())
    backend = MockHeuristicBackend(transport=MockHeuristicTransport())

    assert isinstance(registry, RuleRegistry)
    assert isinstance(backend, LocalGenerationBackend)
    assert isinstance(backend, LocalFindingBackend)


def test_finding_backend_protocol_is_exported_from_core() -> None:
    assert core_module.LocalFindingBackend is protocol_module.LocalFindingBackend


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
        "## LocalFindingBackend",
        "## MonotonicClock",
        "## AnalysisOrchestrator",
    ):
        assert heading in documentation
    for statement in (
        "Nie jest zwracany częściowy `AnalysisResult`.",
        "Anulowanie i termin wykonania należą do orkiestratora.",
        "Polityka ponowień celowo nie jest jeszcze protokołem.",
    ):
        assert statement in documentation
    assert "documentation-contract" not in documentation
    assert "<!--" not in documentation


def test_pipeline_uses_no_private_shadow_backend_protocol() -> None:
    tree = ast.parse(PIPELINE.read_text(encoding="utf-8"))

    assert not any(
        isinstance(node, ast.ClassDef)
        and any(
            isinstance(base, ast.Name) and base.id == "Protocol" for base in node.bases
        )
        for node in tree.body
    )


def test_runtime_protocol_examples_type_check_strictly() -> None:
    completed = subprocess.run(
        [sys.executable, str(TYPECHECK_RUNNER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
