"""Deterministic rule registration and execution support."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final, Protocol

from polis.core import AnalysisOptions, Category, Finding, Rule, Source, VersionedRule
from polis.correction.policy import SourceBehavior
from polis.rules.agreement import (
    AgreementCopulaJaRule,
    AgreementCopulaRule,
    AgreementNominalGroupTaNowyKsiazkaRule,
    AgreementNominalGroupTeDuzeOknoRule,
    AgreementTeNeuterNounRule,
    AgreementTeZdanieRule,
)
from polis.rules.diacritics import SpellingDiacriticsRestoreRule
from polis.rules.government import (
    InflectionGovernmentBycNauczycielRule,
    InflectionGovernmentDoSklepRule,
    InflectionGovernmentInteresowacSieHistoriaRule,
    InflectionGovernmentPotrzebowacPomocRule,
    InflectionGovernmentSluchacRadioRule,
    InflectionGovernmentSzukacKluczRule,
    InflectionGovernmentUfacLekarzRule,
    InflectionGovernmentUzywacTelefonRule,
    InflectionNegatedLubicKaweRule,
)
from polis.rules.inflection import (
    InflectionNegatedMiecCzasRule,
    InflectionNegatedWidziecNominalGroupRule,
    InflectionNegatedWidziecRule,
    InflectionNumeralFiveGenitivePluralRule,
)
from polis.rules.przygladac import InflectionPrzygladacSieNowyBudynekRule
from polis.rules.spelling import (
    SpellingArcyPrefixRule,
    SpellingConajmniejRule,
    SpellingCoNiemiaraRule,
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
    TypoSpellingRule,
    _CasePatternRule,
    collect_closed_literal_findings,
)
from polis.rules.subject_verb import (
    AgreementSubjectVerbMyCzytaRule,
    AgreementSubjectVerbOniCzytaRule,
    AgreementSubjectVerbPresentRule,
)
from polis.rules.syntax import (
    PunctuationAbbreviationDotRule,
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


@dataclass(frozen=True, slots=True)
class RuleRegistration:
    """A typed rule registration entry with optional category scope."""

    rule: Rule
    categories: frozenset[Category] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.rule, Rule):
            raise TypeError("rule must satisfy the Rule protocol")
        if self.categories is not None:
            if isinstance(self.categories, str):
                raise TypeError("categories must be an iterable of Category values")
            normalized: set[Category] = set()
            for category in self.categories:
                if isinstance(category, Category):
                    normalized.add(category)
                    continue
                if isinstance(category, str):
                    normalized.add(Category(category))
                    continue
                raise TypeError("categories must contain Category values or strings")
            normalized_categories = frozenset(normalized)
            object.__setattr__(self, "categories", normalized_categories)


@dataclass(frozen=True, slots=True)
class RuleSourceIdentity:
    """Immutable public identity of one composed deterministic source."""

    source: str
    operation: str
    behavior_version: str


class _RuleFind(Protocol):
    def __call__(
        self, text: str, *, options: AnalysisOptions
    ) -> tuple[Finding, ...]: ...


@dataclass(frozen=True, slots=True)
class _DispatchEntry:
    """Precomputed immutable metadata for one active runtime rule."""

    find: _RuleFind
    source: Source
    categories: frozenset[Category] | None
    literal_rule: _CasePatternRule | None


class RuleRegistryError(ValueError):
    """Base error for rule registration and deterministic execution failures."""


class DuplicateRuleSourceError(RuleRegistryError):
    """Two registrations use the same rule source identifier."""


class IncompatibleRuleOutputError(RuleRegistryError):
    """A rule returns findings outside its declared registry contract."""


class DuplicateFindingError(RuleRegistryError):
    """Two emitted findings share the same stable identifier."""


class DeterministicRuleRegistry:
    """Concrete registry with deterministic registration and execution order."""

    def __init__(self, registrations: Iterable[RuleRegistration]) -> None:
        self._registrations = _normalize_registrations(registrations)
        self._active_registrations = tuple(
            entry
            for entry in self._registrations
            if not _is_absent_morphology_consumer(entry.rule)
        )
        self._active_dispatch = tuple(
            _DispatchEntry(
                find=entry.rule.find,
                source=entry.rule.source,
                categories=entry.categories,
                literal_rule=(
                    entry.rule if isinstance(entry.rule, _CasePatternRule) else None
                ),
            )
            for entry in self._active_registrations
        )
        self._literal_registrations = tuple(
            entry
            for entry in self._active_registrations
            if isinstance(entry.rule, _CasePatternRule)
        )
        self._literal_rules = tuple(
            entry.rule
            for entry in self._literal_registrations
            if isinstance(entry.rule, _CasePatternRule)
        )
        self._behaviors = {
            entry.rule.source: SourceBehavior(
                source=entry.rule.source,
                operation=entry.rule.operation,
                behavior_version=entry.rule.behavior_version,
            )
            for entry in self._registrations
            if isinstance(entry.rule, VersionedRule)
        }

    def rules(self) -> tuple[Rule, ...]:
        """Return registered rules in deterministic order."""

        return tuple(entry.rule for entry in self._registrations)

    def selected_rules(
        self, categories: frozenset[Category] | None
    ) -> tuple[Rule, ...]:
        """Return rules selected by category constraints."""

        return tuple(
            entry.rule
            for entry in self._registrations
            if _selected_by_categories(entry.categories, categories)
        )

    def source_behavior(self, source: Source) -> SourceBehavior | None:
        """Return trusted registered behavior metadata for ``source`` if available."""

        return self._behaviors.get(source)

    def source_identity_snapshot(self) -> tuple[RuleSourceIdentity, ...]:
        """Return the composed versioned sources in deterministic public order."""

        return tuple(
            RuleSourceIdentity(
                str(entry.rule.source),
                entry.rule.operation,
                entry.rule.behavior_version,
            )
            for entry in self._registrations
            if isinstance(entry.rule, VersionedRule)
        )

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        """Execute selected rules and validate their findings."""

        if options.categories is None:
            selected = self._active_dispatch
            literal_rules = self._literal_rules
        else:
            selected = tuple(
                entry
                for entry in self._active_dispatch
                if _selected_by_categories(entry.categories, options.categories)
            )
            literal_rules = tuple(
                entry.literal_rule
                for entry in selected
                if entry.literal_rule is not None
            )
        findings: list[Finding] = []
        seen = set[str]()

        # Closed-literal spelling rules share one token-stream pass when several
        # are selected together (Wave 0 / #338 F0.3). Non-literal rules keep
        # their independent find() paths. Emission order remains registration
        # order for exact source identity compatibility.
        literal_buckets: Mapping[Source, tuple[Finding, ...]] = {}
        if literal_rules:
            literal_buckets = collect_closed_literal_findings(text, literal_rules)

        for entry in selected:
            if entry.literal_rule is not None:
                emitted = literal_buckets.get(entry.source, ())
            else:
                emitted = entry.find(text, options=options)
            for finding in emitted:
                if finding.source != entry.source:
                    raise IncompatibleRuleOutputError(
                        "rule returned a finding with an incompatible source"
                    )
                if (
                    entry.categories is not None
                    and finding.category not in entry.categories
                ):
                    raise IncompatibleRuleOutputError(
                        "rule returned a finding outside its registered categories"
                    )
                if (
                    options.categories is not None
                    and finding.category not in options.categories
                ):
                    continue
                if finding.id in seen:
                    raise DuplicateFindingError(f"duplicate finding id: {finding.id}")
                seen.add(finding.id)
                findings.append(finding)

        return tuple(findings)


def _is_absent_morphology_consumer(rule: Rule) -> bool:
    """Skip provider-gated consumers when the optional morphology backend is absent.

    Rules store ``_provider is None`` after composition without Morfeusz2. Their
    ``find`` methods already return ``()`` in that state; skipping the call is
    behavior-identical and avoids dispatch overhead on the default profile.
    """

    provider = getattr(rule, "_provider", _PROVIDER_SENTINEL)
    return provider is None


_PROVIDER_SENTINEL: Final = object()


def _selected_by_categories(
    registered: frozenset[Category] | None,
    requested: frozenset[Category] | None,
) -> bool:
    if requested is None:
        return True
    if not requested:
        return False
    if registered is None:
        return True
    return bool(registered.intersection(requested))


def _normalize_registrations(
    registrations: Iterable[RuleRegistration],
) -> tuple[RuleRegistration, ...]:
    seen_sources: set[Source] = set()
    normalized: list[RuleRegistration] = []

    for registration in registrations:
        if not isinstance(registration, RuleRegistration):
            raise TypeError("registrations must contain RuleRegistration values")
        if registration.rule.source in seen_sources:
            raise DuplicateRuleSourceError(
                f"duplicate rule source: {registration.rule.source}"
            )
        seen_sources.add(registration.rule.source)
        normalized.append(registration)

    return tuple(normalized)


__all__ = [
    "DeterministicRuleRegistry",
    "DuplicateFindingError",
    "DuplicateRuleSourceError",
    "IncompatibleRuleOutputError",
    "SpellingDiacriticsRestoreRule",
    "SpellingArcyPrefixRule",
    "SpellingCoNiemiaraRule",
    "SpellingConajmniejRule",
    "SpellingCzybyRule",
    "SpellingJestesRule",
    "SpellingNapewnoRule",
    "SpellingNaprawdeRule",
    "SpellingNarazieRule",
    "SpellingNieBycJointRule",
    "SpellingPoprostuRule",
    "SpellingPoszlemRule",
    "SpellingPozatymRule",
    "SpellingPrzedewszystkimRule",
    "SpellingSpowrotemRule",
    "SpellingTymbardziejRule",
    "SpellingWkoncuRule",
    "SpellingWlanczacRule",
    "SpellingWogoleDiacriticRule",
    "SpellingWogoleRule",
    "SpellingWlasnieRule",
    "SpellingMonthWeekdayLowercaseRule",
    "SpellingProperAdjectiveLowercaseRule",
    "SpellingSentenceInitialCapitalRule",
    "SpellingWziascDiacriticRule",
    "SpellingWziascRule",
    "SpellingZebyRule",
    "TypoSpellingRule",
    "AgreementCopulaJaRule",
    "AgreementCopulaRule",
    "AgreementNominalGroupTaNowyKsiazkaRule",
    "AgreementNominalGroupTeDuzeOknoRule",
    "AgreementSubjectVerbMyCzytaRule",
    "AgreementSubjectVerbOniCzytaRule",
    "AgreementSubjectVerbPresentRule",
    "AgreementTeNeuterNounRule",
    "AgreementTeZdanieRule",
    "InflectionNegatedMiecCzasRule",
    "InflectionNegatedWidziecNominalGroupRule",
    "InflectionNegatedWidziecRule",
    "InflectionNumeralFiveGenitivePluralRule",
    "InflectionGovernmentBycNauczycielRule",
    "InflectionGovernmentDoSklepRule",
    "InflectionGovernmentInteresowacSieHistoriaRule",
    "InflectionGovernmentPotrzebowacPomocRule",
    "InflectionGovernmentSluchacRadioRule",
    "InflectionGovernmentSzukacKluczRule",
    "InflectionGovernmentUfacLekarzRule",
    "InflectionGovernmentUzywacTelefonRule",
    "InflectionNegatedLubicKaweRule",
    "InflectionPrzygladacSieNowyBudynekRule",
    "PunctuationAbbreviationDotRule",
    "SyntaxCommaBeforeBoRule",
    "SyntaxCommaBeforeZeReportingRule",
    "SyntaxCommaBeforeZebyPurposeRule",
    "SyntaxCommaSpacingRule",
    "SyntaxDuplicateCommaRule",
    "SyntaxInitialConditionalCommaRule",
    "SyntaxInitialTemporalCommaRule",
    "SyntaxListSpacingRule",
    "SyntaxMissingCorrelativeRule",
    "SyntaxMissingDestinationPrepositionRule",
    "SyntaxMissingReflexiveRule",
    "SyntaxQuoteSpacingRule",
    "SyntaxSentenceSpacingRule",
    "RuleRegistration",
    "RuleSourceIdentity",
    "RuleRegistryError",
]
