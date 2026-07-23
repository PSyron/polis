"""Runtime analyzer implementation for the thin CLI and API examples."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from polis.analysis import normalize_findings
from polis.analysis.hybrid import HybridSuggestionEngine
from polis.analysis.pipeline import analyze_text, analyze_text_async
from polis.core import (
    AnalysisOptions,
    AnalysisResult,
    AnalysisTimeoutError,
    BackendUnavailableError,
    Confidence,
    ConfigurationError,
    Finding,
    InvalidBackendResponseError,
    Source,
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
    SyntaxMissingCorrelativeRule,
    SyntaxMissingReflexiveRule,
    SyntaxQuoteSpacingRule,
    SyntaxSentenceSpacingRule,
)
from polis.rules.contextual_inflection import (
    ContextMorphologyTransport,
    ContextualInflectionRule,
    ContextualInflectionRuleConfig,
    StdioContextMorphologyTransport,
)
from polis.rules.languagetool import (
    LanguageToolRuleConfig,
    LanguageToolTransport,
    LocalLanguageToolRule,
    LoopbackLanguageToolHttpTransport,
)
from polis.rules.languagetool_stdio import LocalLanguageToolStdioSession

__all__ = [
    "Analyzer",
    "AnalyzerConfig",
    "CorrectionResult",
    "SuggestionOutcome",
    "SuggestionStatus",
]


SuggestionStatus = Literal[
    "complete",
    "unavailable",
    "timed_out",
    "invalid_response",
]

_SUGGESTION_OUTCOME_VERSION: Final[str] = "1.0"
_SUGGESTION_BACKEND_OPERATION: Final[str] = "analysis.correct.suggestions"
_SOURCE_POLICY_VERSION: Final[str] = "1.1"


@dataclass(frozen=True)
class AutomaticCorrectionPolicy:
    """One source-policy entry for automatic deterministic correction."""

    source: Source
    minimum_confidence: Confidence
    category: Category
    policy_version: str = "1.0"


@dataclass(frozen=True)
class SuggestionOutcome:
    """Versioned suggestion-run outcome for optional model-backed operations."""

    status: SuggestionStatus
    backend: str
    operation: str
    suggestions: int
    model_calls: int
    protocol_versions: tuple[str, ...] = ()
    operation_version: str = _SUGGESTION_OUTCOME_VERSION
    source_policy_version: str = _SOURCE_POLICY_VERSION


_AUTOMATIC_CORRECTION_POLICY: tuple[AutomaticCorrectionPolicy, ...] = (
    AutomaticCorrectionPolicy(
        source=Source(SourceKind.RULE, "agreement.copula"),
        category=Category.AGREEMENT,
        minimum_confidence=Confidence(0.9),
    ),
    AutomaticCorrectionPolicy(
        source=Source(SourceKind.RULE, "spelling.jestes"),
        category=Category.SPELLING,
        minimum_confidence=Confidence(0.9),
    ),
    AutomaticCorrectionPolicy(
        source=Source(SourceKind.RULE, "spelling.wlasnie"),
        category=Category.SPELLING,
        minimum_confidence=Confidence(0.9),
    ),
    AutomaticCorrectionPolicy(
        source=Source(SourceKind.RULE, "spelling.zeby"),
        category=Category.SPELLING,
        minimum_confidence=Confidence(0.9),
    ),
    AutomaticCorrectionPolicy(
        source=Source(SourceKind.RULE, "syntax.comma_space"),
        category=Category.PUNCTUATION,
        minimum_confidence=Confidence(0.9),
    ),
    AutomaticCorrectionPolicy(
        source=Source(SourceKind.RULE, "syntax.list_space"),
        category=Category.SYNTAX,
        minimum_confidence=Confidence(0.9),
    ),
    AutomaticCorrectionPolicy(
        source=Source(SourceKind.RULE, "syntax.quote_space"),
        category=Category.PUNCTUATION,
        minimum_confidence=Confidence(0.9),
    ),
    AutomaticCorrectionPolicy(
        source=Source(SourceKind.RULE, "syntax.sentence_space"),
        category=Category.PUNCTUATION,
        minimum_confidence=Confidence(0.9),
    ),
    AutomaticCorrectionPolicy(
        source=Source(SourceKind.RULE, "languagetool.pl"),
        category=Category.PUNCTUATION,
        minimum_confidence=Confidence(0.85),
        policy_version="1.1",
    ),
)


_POLICY_BY_SOURCE: Final[dict[Source, AutomaticCorrectionPolicy]] = {
    entry.source: entry for entry in _AUTOMATIC_CORRECTION_POLICY
}


@dataclass(frozen=True)
class AnalyzerConfig:
    """Runtime analyzer configuration for local CLI and API use."""

    categories: frozenset[Category] | None = None
    minimum_confidence: float = 0.0
    use_local_heuristic_backend: bool = False
    language_tool_url: str | None = None
    language_tool_timeout_seconds: float = 1.0
    contextual_inflection_stdio_path: str | None = None
    contextual_inflection_timeout_seconds: float = 1.0
    vendored_language_tool_stdio_path: str | None = None
    vendored_language_tool_timeout_seconds: float = 2.0

    def __post_init__(self) -> None:
        if self.language_tool_url is not None:
            LanguageToolRuleConfig(
                base_url=self.language_tool_url,
                timeout_seconds=self.language_tool_timeout_seconds,
            )
        ContextualInflectionRuleConfig(
            timeout_seconds=self.contextual_inflection_timeout_seconds
        )
        if self.contextual_inflection_stdio_path is not None:
            StdioContextMorphologyTransport(Path(self.contextual_inflection_stdio_path))
        ContextualInflectionRuleConfig(
            timeout_seconds=self.vendored_language_tool_timeout_seconds
        )
        if self.vendored_language_tool_stdio_path is not None:
            StdioContextMorphologyTransport(
                Path(self.vendored_language_tool_stdio_path)
            )
            if (
                self.language_tool_url is not None
                or self.contextual_inflection_stdio_path is not None
            ):
                raise ValueError(
                    "vendored LanguageTool stdio mode is mutually exclusive"
                )

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

        language_tool_present = "language_tool" in raw
        language_tool = raw.get("language_tool", {})
        if not isinstance(language_tool, Mapping):
            raise ConfigurationError(
                "'language_tool' section must be a table",
                code="configuration.invalid_file",
                retryable=False,
                context={"path": str(path_obj)},
            )
        language_tool_url = language_tool.get("base_url")
        if language_tool_present and language_tool_url is None:
            raise ConfigurationError(
                "'language_tool.base_url' is required when the section is present",
                code="configuration.invalid_value",
                retryable=False,
                context={"path": str(path_obj)},
            )
        if language_tool_url is not None and not isinstance(language_tool_url, str):
            raise ConfigurationError(
                "'language_tool.base_url' must be a string",
                code="configuration.invalid_value",
                retryable=False,
                context={"path": str(path_obj)},
            )
        language_tool_timeout = language_tool.get("timeout_seconds", 1.0)
        contextual_present = "contextual_inflection" in raw
        contextual = raw.get("contextual_inflection", {})
        if not isinstance(contextual, Mapping):
            raise ConfigurationError(
                "'contextual_inflection' section must be a table",
                code="configuration.invalid_file",
                retryable=False,
                context={"path": str(path_obj)},
            )
        contextual_path = contextual.get("stdio_path")
        if contextual_present and contextual_path is None:
            raise ConfigurationError(
                "'contextual_inflection.stdio_path' is required when the "
                "section is present",
                code="configuration.invalid_value",
                retryable=False,
                context={"path": str(path_obj)},
            )
        if contextual_path is not None and not isinstance(contextual_path, str):
            raise ConfigurationError(
                "'contextual_inflection.stdio_path' must be a string",
                code="configuration.invalid_value",
                retryable=False,
                context={"path": str(path_obj)},
            )
        contextual_timeout = contextual.get("timeout_seconds", 1.0)
        vendored_present = "vendored_language_tool" in raw
        vendored = raw.get("vendored_language_tool", {})
        if not isinstance(vendored, Mapping):
            raise ConfigurationError(
                "'vendored_language_tool' section must be a table",
                code="configuration.invalid_file",
                retryable=False,
                context={"path": str(path_obj)},
            )
        vendored_path = vendored.get("stdio_path")
        if vendored_present and vendored_path is None:
            raise ConfigurationError(
                "'vendored_language_tool.stdio_path' is required when the "
                "section is present",
                code="configuration.invalid_value",
                retryable=False,
                context={"path": str(path_obj)},
            )
        if vendored_path is not None and not isinstance(vendored_path, str):
            raise ConfigurationError(
                "'vendored_language_tool.stdio_path' must be a string",
                code="configuration.invalid_value",
                retryable=False,
                context={"path": str(path_obj)},
            )
        vendored_timeout = vendored.get("timeout_seconds", 2.0)

        try:
            return cls(
                categories=categories,
                minimum_confidence=float(minimum_confidence),
                use_local_heuristic_backend=use_local,
                language_tool_url=language_tool_url,
                language_tool_timeout_seconds=float(language_tool_timeout),
                contextual_inflection_stdio_path=contextual_path,
                contextual_inflection_timeout_seconds=float(contextual_timeout),
                vendored_language_tool_stdio_path=vendored_path,
                vendored_language_tool_timeout_seconds=float(vendored_timeout),
            )
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(
                "invalid analysis, LanguageTool, contextual inflection, or "
                "vendored stdio configuration",
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
    suggestion_outcomes: tuple[SuggestionOutcome, ...]

    def apply_suggestions(self, finding_ids: Iterable[str]) -> str:
        """Apply explicitly selected skipped suggestions with automatic findings."""

        selected_ids = tuple(finding_ids)
        if not selected_ids:
            return self.corrected_text
        reviewable = AnalysisResult(self.original_text, self.skipped_findings)
        reviewable.apply(selected_ids)
        selected_set = set(selected_ids)
        selected = tuple(
            finding for finding in self.skipped_findings if finding.id in selected_set
        )
        combined = AnalysisResult(
            self.original_text,
            (*self.applied_findings, *selected),
        )
        return cast(
            str,
            combined.apply(
                finding.id for finding in (*self.applied_findings, *selected)
            ),
        )


class Analyzer:
    """Thin runtime analyzer with deterministic rules and optional mock backend."""

    def __init__(
        self,
        config: AnalyzerConfig,
        *,
        specialist_engine: HybridSuggestionEngine | None = None,
        language_tool_transport: LanguageToolTransport | None = None,
        contextual_inflection_transport: ContextMorphologyTransport | None = None,
    ) -> None:
        if not isinstance(config, AnalyzerConfig):
            raise TypeError("config must be AnalyzerConfig")
        if specialist_engine is not None and not isinstance(
            specialist_engine, HybridSuggestionEngine
        ):
            raise TypeError("specialist_engine must be a HybridSuggestionEngine")
        self._config = config
        self._owned_language_tool_session: LocalLanguageToolStdioSession | None = None
        self._closed = False
        if config.vendored_language_tool_stdio_path is not None:
            if (
                language_tool_transport is not None
                or contextual_inflection_transport is not None
            ):
                raise ValueError(
                    "vendored LanguageTool config cannot replace injected transports"
                )
            session = LocalLanguageToolStdioSession.from_executable(
                Path(config.vendored_language_tool_stdio_path),
                timeout_seconds=config.vendored_language_tool_timeout_seconds,
            )
            self._owned_language_tool_session = session
            language_tool_transport = session
            contextual_inflection_transport = session
        self._registry = _make_default_registry(
            config,
            language_tool_transport,
            contextual_inflection_transport,
        )
        self._backend = (
            _make_mock_backend() if config.use_local_heuristic_backend else None
        )
        self._specialist_engine = specialist_engine

    @classmethod
    def from_config(cls, path: str | Path) -> Analyzer:
        return cls(AnalyzerConfig.from_config(path))

    @property
    def language_tool_process_start_count(self) -> int:
        """Return starts of the analyzer-owned vendored LanguageTool process."""

        session = self._owned_language_tool_session
        return 0 if session is None else session.process_start_count

    def analyze(
        self,
        text: str,
        *,
        options: AnalysisOptions | None = None,
    ) -> AnalysisResult:
        self._ensure_open()
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
        self._ensure_open()
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

        return asyncio.run(self.correct_async(text))

    async def correct_async(self, text: str) -> CorrectionResult:
        """Asynchronously return the same conservative correction outcome."""

        self._ensure_open()
        options = AnalysisOptions(
            categories=self._config.categories,
            minimum_confidence=self._config.minimum_confidence,
        )
        analysis, outcomes = await self._analysis_for_correction(text, options)
        suggestions: tuple[Finding, ...] = ()
        if self._specialist_engine is not None:
            specialist_run = await self._specialist_engine.suggest(
                text,
                deterministic_findings=tuple(
                    finding
                    for finding in analysis.issues
                    if finding.source.kind is SourceKind.RULE
                ),
            )
            suggestions = specialist_run.suggestions
            outcomes += (
                SuggestionOutcome(
                    status=specialist_run.status,
                    backend=specialist_run.backend,
                    operation="analysis.correct.specialist",
                    suggestions=len(specialist_run.suggestions),
                    model_calls=specialist_run.model_calls,
                    protocol_versions=specialist_run.operation_versions,
                ),
            )

        combined = normalize_findings(
            (*analysis.issues, *suggestions),
            options=analysis.options,
        )
        correction_analysis = AnalysisResult(
            text=text,
            issues=combined,
            options=analysis.options,
        )
        selected: list[Finding] = []
        skipped: list[Finding] = []
        for finding in correction_analysis.issues:
            if (
                finding.suggestion is not None
                and self._should_apply_automatically(finding)
                and not any(findings_conflict(finding, item) for item in selected)
            ):
                selected.append(finding)
            else:
                skipped.append(finding)
        return CorrectionResult(
            original_text=correction_analysis.text,
            corrected_text=correction_analysis.apply(item.id for item in selected),
            applied_findings=tuple(selected),
            skipped_findings=tuple(skipped),
            suggestion_outcomes=outcomes,
        )

    async def _analysis_for_correction(
        self,
        text: str,
        options: AnalysisOptions,
    ) -> tuple[AnalysisResult, tuple[SuggestionOutcome, ...]]:
        if self._backend is None:
            findings = await analyze_text_async(
                text,
                registry=self._registry,
                local_backend=None,
                options=options,
            )
            return AnalysisResult(text=text, issues=findings, options=options), ()

        counted_backend = _CountingFindingBackend(self._backend)

        try:
            findings = await analyze_text_async(
                text,
                registry=self._registry,
                local_backend=counted_backend,
                options=options,
                ignore_backend_failures=False,
                operation=_SUGGESTION_BACKEND_OPERATION,
            )
            status: SuggestionStatus = "complete"
        except BackendUnavailableError:
            status = "unavailable"
        except AnalysisTimeoutError:
            status = "timed_out"
        except InvalidBackendResponseError:
            status = "invalid_response"

        if status != "complete":
            findings = await analyze_text_async(
                text,
                registry=self._registry,
                local_backend=None,
                options=options,
            )

        analysis = AnalysisResult(text=text, issues=findings, options=options)
        outcome = SuggestionOutcome(
            status=status,
            backend=counted_backend.name,
            operation=_SUGGESTION_BACKEND_OPERATION,
            suggestions=_count_llm_suggestion_findings(analysis.issues),
            model_calls=counted_backend.calls,
        )
        return analysis, (outcome,)

    def close(self) -> None:
        """Close the analyzer-owned local session, if configured."""

        session = self._owned_language_tool_session
        if session is None:
            return
        session.close()
        self._closed = True

    def __enter__(self) -> Analyzer:
        self._ensure_open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("Analyzer-owned LanguageTool session is closed")

    def _should_apply_automatically(self, finding: Finding) -> bool:
        policy = _POLICY_BY_SOURCE.get(finding.source)
        if policy is None:
            return False
        if policy.category != finding.category:
            return False
        if finding.confidence.value < policy.minimum_confidence.value:
            return False
        return True


def _make_default_registry(
    config: AnalyzerConfig,
    language_tool_transport: LanguageToolTransport | None = None,
    contextual_inflection_transport: ContextMorphologyTransport | None = None,
) -> DeterministicRuleRegistry:
    if (
        contextual_inflection_transport is None
        and config.contextual_inflection_stdio_path is not None
    ):
        contextual_inflection_transport = StdioContextMorphologyTransport(
            Path(config.contextual_inflection_stdio_path)
        )
    registrations = [
        RuleRegistration(rule=AgreementCopulaRule()),
        RuleRegistration(rule=SpellingJestesRule()),
        RuleRegistration(rule=SpellingWlasnieRule()),
        RuleRegistration(rule=SpellingZebyRule()),
        RuleRegistration(rule=SyntaxCommaSpacingRule()),
        RuleRegistration(rule=SyntaxListSpacingRule()),
        RuleRegistration(rule=SyntaxMissingCorrelativeRule()),
        RuleRegistration(rule=SyntaxMissingReflexiveRule()),
        RuleRegistration(rule=SyntaxQuoteSpacingRule()),
        RuleRegistration(rule=SyntaxSentenceSpacingRule()),
    ]
    if config.language_tool_url is not None or language_tool_transport is not None:
        timeout_seconds = (
            config.vendored_language_tool_timeout_seconds
            if config.vendored_language_tool_stdio_path is not None
            else config.language_tool_timeout_seconds
        )
        rule_config = LanguageToolRuleConfig(
            base_url=config.language_tool_url or "http://127.0.0.1:1",
            timeout_seconds=timeout_seconds,
        )
        if language_tool_transport is None:
            language_tool_transport = LoopbackLanguageToolHttpTransport(rule_config)
        registrations.append(
            RuleRegistration(
                rule=LocalLanguageToolRule(
                    config=rule_config,
                    transport=language_tool_transport,
                ),
                categories=frozenset({Category.PUNCTUATION}),
            )
        )
    if contextual_inflection_transport is not None:
        registrations.append(
            RuleRegistration(
                rule=ContextualInflectionRule(
                    config=ContextualInflectionRuleConfig(
                        timeout_seconds=(
                            config.vendored_language_tool_timeout_seconds
                            if config.vendored_language_tool_stdio_path is not None
                            else config.contextual_inflection_timeout_seconds
                        )
                    ),
                    transport=contextual_inflection_transport,
                ),
                categories=frozenset({Category.INFLECTION}),
            )
        )
    return DeterministicRuleRegistry(registrations)


def _make_mock_backend() -> MockHeuristicBackend:
    return MockHeuristicBackend(
        transport=MockHeuristicTransport(),
        name="mock-heuristic",
    )


class _CountingFindingBackend:
    """Count calls while preserving the existing finding-backend interface."""

    def __init__(self, backend: Any) -> None:
        self._backend = backend
        self.name = backend.name
        self.calls = 0

    async def generate_findings(
        self,
        text: str,
        *,
        policy: object | None = None,
        clock: object | None = None,
        sleep: Any = None,
        operation: str = "analysis.llm.generate",
    ) -> tuple[Finding, ...]:
        self.calls += 1
        return cast(
            "tuple[Finding, ...]",
            await self._backend.generate_findings(
                text,
                policy=policy,
                clock=clock,
                sleep=sleep,
                operation=operation,
            ),
        )


def _count_llm_suggestion_findings(
    findings: tuple[Finding, ...],
) -> int:
    count = 0
    for finding in findings:
        if finding.source.kind is SourceKind.LLM and finding.suggestion is not None:
            count += 1
    return count
