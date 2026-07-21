"""Runtime analyzer implementation for the thin CLI and API examples."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polis.analysis.pipeline import analyze_text, analyze_text_async
from polis.core import (
    AnalysisOptions,
    AnalysisResult,
    ConfigurationError,
    Finding,
    SourceKind,
)
from polis.core.models import Category
from polis.correction import findings_conflict
from polis.llm.adapter import MockHeuristicBackend, MockHeuristicTransport
from polis.rules import (
    AgreementCopulaRule,
    DeterministicRuleRegistry,
    RuleRegistration,
    SpellingJestesRule,
    SpellingWlasnieRule,
    SpellingZebyRule,
    SyntaxCommaSpacingRule,
    SyntaxListSpacingRule,
    SyntaxQuoteSpacingRule,
    SyntaxSentenceSpacingRule,
)

__all__ = [
    "Analyzer",
    "AnalyzerConfig",
    "CorrectionResult",
]


@dataclass(frozen=True)
class AnalyzerConfig:
    """Runtime analyzer configuration for local CLI and API use."""

    categories: frozenset[Category] | None = None
    minimum_confidence: float = 0.0
    use_local_heuristic_backend: bool = False

    @classmethod
    def from_toml(cls, path: str | Path) -> AnalyzerConfig:
        path_obj = Path(path)
        if not path_obj.exists():
            raise ConfigurationError(
                "analysis configuration file does not exist",
                code="configuration.file_not_found",
                retryable=False,
                context={"path": str(path_obj)},
            )

        raw: Any
        with path_obj.open("rb") as config_file:
            try:
                import tomllib

                raw = tomllib.load(config_file)
            except (OSError, TypeError, ValueError) as exc:
                raise ConfigurationError(
                    "invalid analysis configuration file",
                    code="configuration.invalid_file",
                    retryable=False,
                    context={"path": str(path_obj)},
                ) from exc

        if not isinstance(raw, Mapping):
            raise ConfigurationError(
                "analysis configuration root must be a table",
                code="configuration.invalid_file",
                retryable=False,
                context={"path": str(path_obj)},
            )

        analysis = raw.get("analysis", {})
        if not isinstance(analysis, Mapping):
            raise ConfigurationError(
                "'analysis' section must be a table",
                code="configuration.invalid_file",
                retryable=False,
                context={"path": str(path_obj)},
            )

        categories_raw = analysis.get("categories")
        if categories_raw is None:
            categories = None
        else:
            if isinstance(categories_raw, str) or not isinstance(categories_raw, list):
                raise ConfigurationError(
                    "'analysis.categories' must be a list of category values",
                    code="configuration.invalid_value",
                    retryable=False,
                    context={"path": str(path_obj)},
                )
            try:
                categories = frozenset(Category(value) for value in categories_raw)
            except ValueError as exc:
                raise ConfigurationError(
                    "unsupported category in 'analysis.categories'",
                    code="configuration.invalid_value",
                    retryable=False,
                    context={"path": str(path_obj)},
                ) from exc

        minimum_confidence = analysis.get("minimum_confidence", 0.0)
        backend = raw.get("backend", {})
        if not isinstance(backend, Mapping):
            raise ConfigurationError(
                "'backend' section must be a table",
                code="configuration.invalid_file",
                retryable=False,
                context={"path": str(path_obj)},
            )

        use_local = bool(backend.get("use_mock", False))

        try:
            return cls(
                categories=categories,
                minimum_confidence=float(minimum_confidence),
                use_local_heuristic_backend=use_local,
            )
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(
                "invalid numeric values in analysis configuration",
                code="configuration.invalid_value",
                retryable=False,
                context={"path": str(path_obj)},
            ) from exc

    @classmethod
    def from_config(cls, path: str | Path) -> AnalyzerConfig:
        return cls.from_toml(path)


@dataclass(frozen=True)
class CorrectionResult:
    """Conservative correction outcome for one sentence or paragraph."""

    original_text: str
    corrected_text: str
    applied_findings: tuple[Finding, ...]
    skipped_findings: tuple[Finding, ...]


class Analyzer:
    """Thin runtime analyzer with deterministic rules and optional mock backend."""

    def __init__(self, config: AnalyzerConfig) -> None:
        if not isinstance(config, AnalyzerConfig):
            raise TypeError("config must be AnalyzerConfig")
        self._config = config
        self._registry = _make_default_registry()
        self._backend = (
            _make_mock_backend() if config.use_local_heuristic_backend else None
        )

    @classmethod
    def from_config(cls, path: str | Path) -> Analyzer:
        return cls(AnalyzerConfig.from_config(path))

    def analyze(
        self,
        text: str,
        *,
        options: AnalysisOptions | None = None,
    ) -> AnalysisResult:
        resolved_options = options or AnalysisOptions(
            categories=self._config.categories,
            minimum_confidence=self._config.minimum_confidence,
        )
        findings = analyze_text(
            text,
            registry=self._registry,
            local_backend=self._backend,
            options=resolved_options,
        )
        return AnalysisResult(text=text, issues=findings, options=resolved_options)

    async def analyze_async(
        self, text: str, *, options: AnalysisOptions | None = None
    ) -> AnalysisResult:
        resolved_options = options or AnalysisOptions(
            categories=self._config.categories,
            minimum_confidence=self._config.minimum_confidence,
        )
        findings = await analyze_text_async(
            text,
            registry=self._registry,
            local_backend=self._backend,
            options=resolved_options,
        )
        return AnalysisResult(text=text, issues=findings, options=resolved_options)

    def correct(self, text: str) -> CorrectionResult:
        """Apply only high-confidence, non-conflicting deterministic corrections."""

        analysis = self.analyze(text)
        selected: list[Finding] = []
        skipped: list[Finding] = []
        for finding in analysis.issues:
            is_safe = (
                finding.source.kind is SourceKind.RULE
                and finding.suggestion is not None
                and finding.confidence.value >= 0.9
                and not any(findings_conflict(finding, item) for item in selected)
            )
            if is_safe:
                selected.append(finding)
            else:
                skipped.append(finding)
        return CorrectionResult(
            original_text=analysis.text,
            corrected_text=analysis.apply(item.id for item in selected),
            applied_findings=tuple(selected),
            skipped_findings=tuple(skipped),
        )


def _make_default_registry() -> DeterministicRuleRegistry:
    registrations = (
        RuleRegistration(rule=AgreementCopulaRule()),
        RuleRegistration(rule=SpellingJestesRule()),
        RuleRegistration(rule=SpellingWlasnieRule()),
        RuleRegistration(rule=SpellingZebyRule()),
        RuleRegistration(rule=SyntaxCommaSpacingRule()),
        RuleRegistration(rule=SyntaxListSpacingRule()),
        RuleRegistration(rule=SyntaxQuoteSpacingRule()),
        RuleRegistration(rule=SyntaxSentenceSpacingRule()),
    )
    return DeterministicRuleRegistry(registrations)


def _make_mock_backend() -> MockHeuristicBackend:
    return MockHeuristicBackend(
        transport=MockHeuristicTransport(),
        name="mock-heuristic",
    )
