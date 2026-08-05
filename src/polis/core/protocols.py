"""Narrow implementation boundaries for future offline analysis."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from polis.core.models import AnalysisOptions, AnalysisResult, Finding, Source


@runtime_checkable
class DeterministicAnalyzer(Protocol):
    """Synchronously produce validated findings for one deterministic source.

    Implementations are created and configured by a future composition root.
    They receive immutable effective options and return findings in their own
    deterministic order. Implementations do not merge findings, call local
    generation, apply corrections, or turn operational failures into partial
    results.
    """

    @property
    def source(self) -> Source:
        """Return the stable source recorded on every produced finding."""

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        """Return validated findings for ``text`` without mutating it."""


@runtime_checkable
class Rule(Protocol):
    """One synchronously evaluated deterministic rule entry.

    A rule has the same shape as a deterministic analyzer but is registered as
    a separately selectable unit. A future registry owns rule construction and
    ordering; a rule owns neither retries nor cross-rule result handling.
    """

    @property
    def source(self) -> Source:
        """Return this rule's stable ``rule:`` source."""

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        """Return this rule's validated findings in deterministic order."""


@runtime_checkable
class VersionedRule(Rule, Protocol):
    """A rule with trusted immutable behavior provenance metadata."""

    @property
    def operation(self) -> str:
        """Return the stable action performed by this rule."""

    @property
    def behavior_version(self) -> str:
        """Return the exact qualified implementation behavior version."""


@runtime_checkable
class RuleRegistry(Protocol):
    """Execute the fixed ordered rule entries for one analyzer lifecycle.

    The registry is configured before analysis begins. It owns rule selection,
    deterministic execution order, and validation of registered rule output.
    It does not call local generation or merge local-backend findings.
    """

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        """Return validated findings from the selected registered rules."""


@runtime_checkable
class AnalysisOrchestrator(Protocol):
    """Produce complete analysis results through synchronous and async entry points.

    Both methods share the ADR-0003 all-or-error contract. The implementation
    owns dependency lifecycles, filtering, canonical ordering, deadlines,
    cancellation, retries, validation, and error translation. It never returns
    a partial result when any configured component fails.
    """

    def analyze(self, text: str, *, options: AnalysisOptions) -> AnalysisResult:
        """Synchronously return a complete result or raise a controlled error."""

    async def analyze_async(
        self, text: str, *, options: AnalysisOptions
    ) -> AnalysisResult:
        """Asynchronously return the same complete result contract."""
