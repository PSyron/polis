"""Fail-closed eligibility for automatic deterministic corrections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from polis.core import Category, Confidence, Finding, Source, SourceKind

SOURCE_POLICY_VERSION: Final[str] = "1.2"


def _require_non_blank(value: str, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be blank")


@dataclass(frozen=True, slots=True)
class SourceBehavior:
    """The qualified behavior identity of one deterministic source."""

    source: Source
    operation: str
    behavior_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source):
            raise TypeError("source must be a Source")
        _require_non_blank(self.operation, "operation")
        _require_non_blank(self.behavior_version, "behavior version")


@dataclass(frozen=True, slots=True)
class SourcePolicyKey:
    """The complete immutable identity used for automatic eligibility."""

    source: Source
    category: Category
    operation: str
    behavior_version: str
    source_policy_version: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, Source):
            raise TypeError("source must be a Source")
        if not isinstance(self.category, Category):
            raise TypeError("category must be a Category")
        _require_non_blank(self.operation, "operation")
        _require_non_blank(self.behavior_version, "behavior version")
        _require_non_blank(self.source_policy_version, "source policy version")


@dataclass(frozen=True, slots=True)
class _AutomaticCorrectionPolicyEntry:
    """One private exact-key policy entry and its confidence threshold."""

    key: SourcePolicyKey
    minimum_confidence: Confidence

    def __post_init__(self) -> None:
        if not isinstance(self.key, SourcePolicyKey):
            raise TypeError("key must be a SourcePolicyKey")
        if not isinstance(self.minimum_confidence, Confidence):
            raise TypeError("minimum confidence must be a Confidence")


def is_automatic_correction_eligible(
    finding: Finding,
    behavior: SourceBehavior | None,
    *,
    source_policy_version: str = SOURCE_POLICY_VERSION,
) -> bool:
    """Return whether a finding exactly matches the active automatic policy."""

    if finding.source.kind is SourceKind.LLM:
        return False
    if behavior is None or behavior.source != finding.source:
        return False

    key = SourcePolicyKey(
        source=finding.source,
        category=finding.category,
        operation=behavior.operation,
        behavior_version=behavior.behavior_version,
        source_policy_version=source_policy_version,
    )
    entry = _POLICY_BY_KEY.get(key)
    if entry is None:
        return False
    return bool(finding.confidence.value >= entry.minimum_confidence.value)


def _entry(
    source_name: str,
    category: Category,
    operation: str,
    behavior_version: str,
    minimum_confidence: float,
) -> _AutomaticCorrectionPolicyEntry:
    source = Source(SourceKind.RULE, source_name)
    return _AutomaticCorrectionPolicyEntry(
        key=SourcePolicyKey(
            source=source,
            category=category,
            operation=operation,
            behavior_version=behavior_version,
            source_policy_version=SOURCE_POLICY_VERSION,
        ),
        minimum_confidence=Confidence(minimum_confidence),
    )


_ACTIVE_POLICY_ENTRIES: Final[tuple[_AutomaticCorrectionPolicyEntry, ...]] = (
    _entry(
        "agreement.copula",
        Category.AGREEMENT,
        "replace.copula_form",
        "agreement-copula/1.0",
        0.9,
    ),
    _entry(
        "spelling.jestes",
        Category.SPELLING,
        "replace.common_typo",
        "spelling-jestes/1.0",
        0.9,
    ),
    _entry(
        "spelling.wlasnie",
        Category.SPELLING,
        "replace.common_typo",
        "spelling-wlasnie/1.0",
        0.9,
    ),
    _entry(
        "spelling.zeby",
        Category.SPELLING,
        "replace.common_typo",
        "spelling-zeby/1.0",
        0.9,
    ),
    _entry(
        "syntax.comma_space",
        Category.PUNCTUATION,
        "normalize.comma_spacing",
        "syntax-comma-space/1.0",
        0.9,
    ),
    _entry(
        "syntax.list_space",
        Category.SYNTAX,
        "normalize.list_marker_spacing",
        "syntax-list-space/1.0",
        0.9,
    ),
    _entry(
        "syntax.quote_space",
        Category.PUNCTUATION,
        "normalize.quote_spacing",
        "syntax-quote-space/1.0",
        0.9,
    ),
    _entry(
        "syntax.sentence_space",
        Category.PUNCTUATION,
        "normalize.sentence_spacing",
        "syntax-sentence-space/1.0",
        0.9,
    ),
    _entry(
        "languagetool.pl",
        Category.PUNCTUATION,
        "check.allowlisted_comma",
        "pl-6.8-five-rule-comma/1.0",
        0.85,
    ),
)

_POLICY_BY_KEY: Final[dict[SourcePolicyKey, _AutomaticCorrectionPolicyEntry]] = {
    entry.key: entry for entry in _ACTIVE_POLICY_ENTRIES
}

if len(_POLICY_BY_KEY) != len(_ACTIVE_POLICY_ENTRIES):
    raise ValueError("automatic correction policy contains duplicate keys")


__all__ = [
    "SOURCE_POLICY_VERSION",
    "SourceBehavior",
    "SourcePolicyKey",
    "is_automatic_correction_eligible",
]
