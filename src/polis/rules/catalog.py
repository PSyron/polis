"""Immutable metadata and catalog contracts for deterministic rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from polis.core import Category, Source, SourceKind


class RuleCatalogError(ValueError):
    """Base error for invalid rule catalog contracts."""


class InvalidRuleMetadataError(RuleCatalogError):
    """Raised when rule metadata violates its contract."""


class DuplicateRuleMetadataError(RuleCatalogError):
    """Raised when a catalog contains a duplicate rule source."""


class RuleAvailability(StrEnum):
    """Static installation availability of a rule implementation."""

    BUILT_IN = "built_in"
    REQUIRES_CONFIGURATION = "requires_configuration"


@dataclass(frozen=True, slots=True)
class RuleMetadata:
    """Immutable descriptive metadata for one deterministic rule source."""

    source: Source
    operation: str
    behavior_version: str
    categories: frozenset[Category]
    enabled_by_default: bool
    availability: RuleAvailability
    description: str

    def __post_init__(self) -> None:
        if (
            type(self.source) is not Source
            or self.source.kind is not SourceKind.RULE
            or type(self.source.name) is not str
        ):
            _invalid("source")

        for field_name in ("operation", "behavior_version", "description"):
            value = getattr(self, field_name)
            if type(value) is not str or not value or value != value.strip():
                _invalid(field_name)

        if (
            type(self.categories) is not frozenset
            or not self.categories
            or any(not isinstance(category, Category) for category in self.categories)
        ):
            _invalid("categories")

        if type(self.enabled_by_default) is not bool:
            _invalid("enabled_by_default")

        if not isinstance(self.availability, RuleAvailability):
            _invalid("availability")


@dataclass(frozen=True, slots=True, init=False)
class RuleCatalog:
    """An immutable, insertion-ordered collection of rule metadata."""

    _entries: tuple[RuleMetadata, ...]

    def __init__(self, entries: tuple[RuleMetadata, ...]) -> None:
        if type(entries) is not tuple:
            raise RuleCatalogError("catalog entries must be an ordered tuple")

        seen: set[Source] = set()
        for entry in entries:
            if type(entry) is not RuleMetadata:
                raise RuleCatalogError(
                    "catalog entries must contain RuleMetadata values"
                )
            if entry.source in seen:
                raise DuplicateRuleMetadataError(
                    f"duplicate rule metadata source: {entry.source}"
                )
            seen.add(entry.source)

        object.__setattr__(self, "_entries", entries)

    def entries(self) -> tuple[RuleMetadata, ...]:
        """Return metadata in its declared deterministic order."""

        return self._entries

    def get(self, source: Source) -> RuleMetadata | None:
        """Return metadata for an exact source identity, when present."""

        if type(source) is not Source or type(source.name) is not str:
            raise RuleCatalogError("catalog lookup source must be a Source")
        return next(
            (entry for entry in self._entries if entry.source == source),
            None,
        )


def _invalid(field_name: str) -> None:
    raise InvalidRuleMetadataError(f"invalid rule metadata field: {field_name}")


__all__ = [
    "DuplicateRuleMetadataError",
    "InvalidRuleMetadataError",
    "RuleAvailability",
    "RuleCatalog",
    "RuleCatalogError",
    "RuleMetadata",
]
