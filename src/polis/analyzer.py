"""Runtime analyzer implementation for the thin CLI and API examples."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from polis.analysis.pipeline import analyze_text, analyze_text_async
from polis.core import (
    AnalysisOptions,
    AnalysisResult,
    Confidence,
    ConfigurationError,
    Finding,
)
from polis.core.models import Category
from polis.correction import findings_conflict
from polis.correction.policy import (
    SOURCE_POLICY_VERSION,
    is_automatic_correction_eligible,
)
from polis.rules import (
    AgreementCopulaJaRule,
    AgreementCopulaRule,
    AgreementNominalGroupTaNowyKsiazkaRule,
    AgreementNominalGroupTeDuzeOknoRule,
    AgreementSubjectVerbMyCzytaRule,
    AgreementSubjectVerbOniCzytaRule,
    AgreementSubjectVerbPresentRule,
    AgreementTeNeuterNounRule,
    AgreementTeZdanieRule,
    DeterministicRuleRegistry,
    InflectionGovernmentBycNauczycielRule,
    InflectionGovernmentDoSklepRule,
    InflectionGovernmentInteresowacSieHistoriaRule,
    InflectionGovernmentPotrzebowacPomocRule,
    InflectionGovernmentSluchacRadioRule,
    InflectionGovernmentSzukacKluczRule,
    InflectionGovernmentUfacLekarzRule,
    InflectionGovernmentUzywacTelefonRule,
    InflectionNegatedLubicKaweRule,
    InflectionNegatedMiecCzasRule,
    InflectionNegatedWidziecNominalGroupRule,
    InflectionNegatedWidziecRule,
    InflectionNumeralFiveGenitivePluralRule,
    InflectionPrzygladacSieNowyBudynekRule,
    PunctuationAbbreviationDotRule,
    RuleRegistration,
    RuleSourceIdentity,
    SpellingConajmniejRule,
    SpellingCzybyRule,
    SpellingJestesRule,
    SpellingMonthWeekdayLowercaseRule,
    SpellingNapewnoRule,
    SpellingNaprawdeRule,
    SpellingNarazieRule,
    SpellingNieBycJointRule,
    SpellingPoprostuRule,
    SpellingPoszlemRule,
    SpellingPozatymRule,
    SpellingProperAdjectiveLowercaseRule,
    SpellingPrzedewszystkimRule,
    SpellingSentenceInitialCapitalRule,
    SpellingSpowrotemRule,
    SpellingTymbardziejRule,
    SpellingWkoncuRule,
    SpellingWlanczacRule,
    SpellingWlasnieRule,
    SpellingWogoleDiacriticRule,
    SpellingWogoleRule,
    SpellingWziascDiacriticRule,
    SpellingWziascRule,
    SpellingZebyRule,
    SyntaxCommaBeforeBoRule,
    SyntaxCommaBeforeZebyPurposeRule,
    SyntaxCommaBeforeZeReportingRule,
    SyntaxCommaSpacingRule,
    SyntaxDuplicateCommaRule,
    SyntaxInitialConditionalCommaRule,
    SyntaxInitialTemporalCommaRule,
    SyntaxListSpacingRule,
    SyntaxMissingCorrelativeRule,
    SyntaxMissingDestinationPrepositionRule,
    SyntaxMissingReflexiveRule,
    SyntaxQuoteSpacingRule,
    SyntaxSentenceSpacingRule,
)
from polis.rules._morfeusz import _load_qualified_morfeusz

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
_UNSUPPORTED_V1_SECTIONS: Final[tuple[str, ...]] = (
    "backend",
    "language_tool",
    "contextual_inflection",
    "vendored_language_tool",
)


@dataclass(frozen=True)
class SuggestionOutcome:
    """Versioned suggestion-run outcome retained for 0.x schema compatibility."""

    status: SuggestionStatus
    backend: str
    operation: str
    suggestions: int
    model_calls: int
    protocol_versions: tuple[str, ...] = ()
    operation_version: str = _SUGGESTION_OUTCOME_VERSION
    source_policy_version: str = SOURCE_POLICY_VERSION


@dataclass(frozen=True)
class AnalyzerConfig:
    """Configuration for the conservative, deterministic v1 analyzer."""

    categories: frozenset[Category] | None = None
    minimum_confidence: float = 0.0

    def __post_init__(self) -> None:
        try:
            minimum_confidence = Confidence(self.minimum_confidence).value
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(
                "'analysis.minimum_confidence' must be a finite number "
                "between 0.0 and 1.0",
                code="configuration.invalid",
                retryable=False,
                context={"operation": "configuration.construct"},
            ) from exc
        object.__setattr__(self, "minimum_confidence", minimum_confidence)

    @classmethod
    def from_toml(cls, path: str | Path) -> AnalyzerConfig:
        """Load supported analysis settings from a local TOML file."""

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

        for section in _UNSUPPORTED_V1_SECTIONS:
            if section in raw:
                raise ConfigurationError(
                    f"configuration section '{section}' is not supported in Polis v1",
                    code="configuration.unsupported_section",
                    retryable=False,
                    context={
                        "operation": "configuration.load",
                        "path": str(path_obj),
                        "section": section,
                    },
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

        try:
            return cls(
                categories=categories,
                minimum_confidence=analysis.get("minimum_confidence", 0.0),
            )
        except ConfigurationError as exc:
            raise ConfigurationError(
                str(exc),
                code="configuration.invalid",
                retryable=exc.retryable,
                context={
                    "operation": "configuration.load",
                    "path": str(path_obj),
                },
            ) from exc

    @classmethod
    def from_config(cls, path: str | Path) -> AnalyzerConfig:
        """Compatibility alias for :meth:`from_toml`."""

        return cls.from_toml(path)


@dataclass(frozen=True)
class CorrectionResult:
    """Conservative correction outcome for one sentence or paragraph."""

    original_text: str
    corrected_text: str
    applied_findings: tuple[Finding, ...]
    skipped_findings: tuple[Finding, ...]
    suggestion_outcomes: tuple[SuggestionOutcome, ...]
    source_policy_version: str

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
    """Thin runtime analyzer composed only from conservative v1 rules."""

    def __init__(self, config: AnalyzerConfig) -> None:
        if not isinstance(config, AnalyzerConfig):
            raise TypeError("config must be AnalyzerConfig")
        self._config = config
        self._registry: DeterministicRuleRegistry = _make_default_registry()

    @classmethod
    def from_config(cls, path: str | Path) -> Analyzer:
        return cls(AnalyzerConfig.from_config(path))

    @property
    def language_tool_process_start_count(self) -> int:
        """Return zero because the conservative v1 analyzer owns no process."""

        return 0

    @property
    def source_identity_snapshot(self) -> tuple[RuleSourceIdentity, ...]:
        """Return the immutable identity of the composed deterministic sources."""

        snapshot: list[RuleSourceIdentity] = []
        for identity in self._registry.source_identity_snapshot():
            snapshot.append(identity)
        return tuple(snapshot)

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
            options=resolved_options,
        )
        return AnalysisResult(text=text, issues=findings, options=resolved_options)

    def correct(self, text: str) -> CorrectionResult:
        """Apply only high-confidence, non-conflicting deterministic corrections."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.correct_async(text))
        raise RuntimeError(
            "Analyzer.correct() cannot be called from a running event loop; "
            "use 'await Analyzer.correct_async(...)' instead"
        )

    async def correct_async(self, text: str) -> CorrectionResult:
        """Asynchronously return the same conservative correction outcome."""

        options = AnalysisOptions(
            categories=self._config.categories,
            minimum_confidence=self._config.minimum_confidence,
        )
        analysis = await self.analyze_async(text, options=options)
        selected: list[Finding] = []
        skipped: list[Finding] = []
        for finding in analysis.issues:
            if (
                finding.suggestion is not None
                and self._should_apply_automatically(finding)
                and not any(findings_conflict(finding, item) for item in selected)
            ):
                selected.append(finding)
            else:
                skipped.append(finding)
        return CorrectionResult(
            original_text=analysis.text,
            corrected_text=analysis.apply(item.id for item in selected),
            applied_findings=tuple(selected),
            skipped_findings=tuple(skipped),
            suggestion_outcomes=(),
            source_policy_version=SOURCE_POLICY_VERSION,
        )

    def close(self) -> None:
        """Compatibility no-op; the conservative v1 analyzer owns no resources."""

    def __enter__(self) -> Analyzer:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _should_apply_automatically(self, finding: Finding) -> bool:
        behavior = self._registry.source_behavior(finding.source)
        return bool(
            is_automatic_correction_eligible(
                finding,
                behavior,
                source_policy_version=SOURCE_POLICY_VERSION,
            )
        )


def _make_default_registry() -> DeterministicRuleRegistry:
    """Compose the fixed conservative v1 rule set in public evaluation order."""

    morphology = _load_qualified_morfeusz()
    return DeterministicRuleRegistry(
        (
            RuleRegistration(rule=AgreementCopulaRule()),
            RuleRegistration(rule=AgreementCopulaJaRule()),
            RuleRegistration(rule=AgreementTeZdanieRule()),
            RuleRegistration(rule=AgreementTeNeuterNounRule()),
            RuleRegistration(rule=AgreementNominalGroupTeDuzeOknoRule(morphology)),
            RuleRegistration(rule=AgreementNominalGroupTaNowyKsiazkaRule(morphology)),
            RuleRegistration(rule=AgreementSubjectVerbOniCzytaRule(morphology)),
            RuleRegistration(rule=AgreementSubjectVerbMyCzytaRule(morphology)),
            RuleRegistration(rule=AgreementSubjectVerbPresentRule(morphology)),
            RuleRegistration(rule=InflectionNegatedWidziecRule()),
            RuleRegistration(rule=InflectionNegatedWidziecNominalGroupRule(morphology)),
            RuleRegistration(rule=InflectionNegatedMiecCzasRule()),
            RuleRegistration(rule=InflectionNegatedLubicKaweRule(morphology)),
            RuleRegistration(rule=InflectionPrzygladacSieNowyBudynekRule(morphology)),
            RuleRegistration(rule=InflectionGovernmentPotrzebowacPomocRule(morphology)),
            RuleRegistration(rule=InflectionGovernmentSzukacKluczRule(morphology)),
            RuleRegistration(rule=InflectionGovernmentSluchacRadioRule(morphology)),
            RuleRegistration(rule=InflectionGovernmentUzywacTelefonRule(morphology)),
            RuleRegistration(
                rule=InflectionGovernmentInteresowacSieHistoriaRule(morphology)
            ),
            RuleRegistration(rule=InflectionGovernmentBycNauczycielRule(morphology)),
            RuleRegistration(rule=InflectionGovernmentDoSklepRule(morphology)),
            RuleRegistration(rule=InflectionGovernmentUfacLekarzRule(morphology)),
            RuleRegistration(rule=InflectionNumeralFiveGenitivePluralRule()),
            RuleRegistration(rule=SpellingJestesRule()),
            RuleRegistration(rule=SpellingCzybyRule()),
            RuleRegistration(rule=SpellingNapewnoRule()),
            RuleRegistration(rule=SpellingWlasnieRule()),
            RuleRegistration(rule=SpellingZebyRule()),
            RuleRegistration(rule=SpellingWogoleRule()),
            RuleRegistration(rule=SpellingWogoleDiacriticRule()),
            RuleRegistration(rule=SpellingNarazieRule()),
            RuleRegistration(rule=SpellingWziascRule()),
            RuleRegistration(rule=SpellingWziascDiacriticRule()),
            RuleRegistration(rule=SpellingConajmniejRule()),
            RuleRegistration(rule=SpellingPoprostuRule()),
            RuleRegistration(rule=SpellingPozatymRule()),
            RuleRegistration(rule=SpellingPrzedewszystkimRule()),
            RuleRegistration(rule=SpellingWkoncuRule()),
            RuleRegistration(rule=SpellingSpowrotemRule()),
            RuleRegistration(rule=SpellingTymbardziejRule()),
            RuleRegistration(rule=SpellingNaprawdeRule()),
            RuleRegistration(rule=SpellingNieBycJointRule()),
            RuleRegistration(rule=SpellingPoszlemRule()),
            RuleRegistration(rule=SpellingWlanczacRule()),
            RuleRegistration(rule=SpellingMonthWeekdayLowercaseRule()),
            RuleRegistration(rule=SpellingProperAdjectiveLowercaseRule()),
            RuleRegistration(rule=SpellingSentenceInitialCapitalRule()),
            RuleRegistration(rule=SyntaxCommaSpacingRule()),
            RuleRegistration(rule=SyntaxDuplicateCommaRule()),
            RuleRegistration(rule=SyntaxInitialConditionalCommaRule()),
            RuleRegistration(rule=SyntaxInitialTemporalCommaRule()),
            RuleRegistration(rule=SyntaxCommaBeforeZeReportingRule()),
            RuleRegistration(rule=SyntaxCommaBeforeZebyPurposeRule()),
            RuleRegistration(rule=SyntaxCommaBeforeBoRule()),
            RuleRegistration(rule=SyntaxListSpacingRule()),
            RuleRegistration(rule=SyntaxMissingCorrelativeRule()),
            RuleRegistration(rule=SyntaxMissingDestinationPrepositionRule()),
            RuleRegistration(rule=SyntaxMissingReflexiveRule()),
            RuleRegistration(rule=SyntaxQuoteSpacingRule()),
            RuleRegistration(rule=SyntaxSentenceSpacingRule()),
            RuleRegistration(rule=PunctuationAbbreviationDotRule()),
        )
    )
