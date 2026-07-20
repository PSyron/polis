"""Deterministic rule registration and execution support."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from polis.core import AnalysisOptions, Category, Finding, Rule, Source
from polis.rules.agreement import AgreementCopulaRule
from polis.rules.spelling import (
    SpellingJestesRule,
    SpellingWlasnieRule,
    SpellingZebyRule,
    TypoSpellingRule,
)
from polis.rules.syntax import (
    SyntaxCommaSpacingRule,
    SyntaxListSpacingRule,
    SyntaxQuoteSpacingRule,
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

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        """Execute selected rules and validate their findings."""

        selected = tuple(
            entry
            for entry in self._registrations
            if _selected_by_categories(entry.categories, options.categories)
        )
        findings: list[Finding] = []
        seen = set[str]()

        for entry in selected:
            emitted = entry.rule.find(text, options=options)
            for finding in emitted:
                if finding.source != entry.rule.source:
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
    "SpellingJestesRule",
    "SpellingWlasnieRule",
    "SpellingZebyRule",
    "TypoSpellingRule",
    "AgreementCopulaRule",
    "SyntaxCommaSpacingRule",
    "SyntaxListSpacingRule",
    "SyntaxQuoteSpacingRule",
    "RuleRegistration",
    "RuleRegistryError",
]
