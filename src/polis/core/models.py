"""Typed public models for Polis analysis results."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Self, cast

_SOURCE_NAME = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")
_FINDING_ID = re.compile(r"finding_[0-9a-f]{32}\Z")
_FINDING_ID_VERSION = 1


class Category(StrEnum):
    """A class of text issue that Polis can report."""

    INFLECTION = "inflection"
    AGREEMENT = "agreement"
    SYNTAX = "syntax"
    SPELLING = "spelling"
    PUNCTUATION = "punctuation"
    STYLE = "style"


class Severity(StrEnum):
    """How strongly a finding should be presented to a user."""

    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class SourceKind(StrEnum):
    """The analyzer family that produced a finding."""

    RULE = "rule"
    LLM = "llm"


@dataclass(frozen=True, slots=True)
class Source:
    """A stable analyzer source, represented on the wire as ``kind:name``."""

    kind: SourceKind
    name: str

    def __post_init__(self) -> None:
        if not isinstance(self.kind, SourceKind):
            raise TypeError("source kind must be a SourceKind")
        if not isinstance(self.name, str):
            raise TypeError("source name must be a string")
        if _SOURCE_NAME.fullmatch(self.name) is None:
            raise ValueError(
                "source name must start with an ASCII lowercase letter or digit "
                "and contain only lowercase letters, digits, '.', '_' or '-'"
            )

    def __str__(self) -> str:
        """Return the stable JSON representation."""

        return f"{self.kind.value}:{self.name}"

    @classmethod
    def parse(cls, value: str) -> Self:
        """Parse a strict ``kind:name`` source value."""

        if not isinstance(value, str):
            raise TypeError("source must be a string")
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("source must use the 'kind:name' form")
        kind_value, name = parts
        try:
            kind = SourceKind(kind_value)
        except ValueError as error:
            raise ValueError(f"unknown source kind: {kind_value!r}") from error
        return cls(kind=kind, name=name)


@dataclass(frozen=True, slots=True)
class Confidence:
    """A finite confidence value in the closed interval from zero to one."""

    value: float

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise TypeError("confidence must be a real number, not a boolean")
        try:
            normalized = float(self.value)
        except OverflowError as error:
            raise ValueError(
                "confidence must be finite and between 0.0 and 1.0"
            ) from error
        if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
            raise ValueError("confidence must be finite and between 0.0 and 1.0")
        if normalized == 0.0:
            normalized = 0.0
        object.__setattr__(self, "value", normalized)


@dataclass(frozen=True, slots=True)
class Finding:
    """One validated issue located in the original input text."""

    id: str
    category: Category
    severity: Severity
    message: str
    explanation: str
    original: str
    suggestion: str | None
    start: int
    end: int
    confidence: Confidence
    source: Source

    def __post_init__(self) -> None:
        if not isinstance(self.id, str):
            raise TypeError("finding id must be a string")
        if _FINDING_ID.fullmatch(self.id) is None:
            raise ValueError("finding id must use the 'finding_' stable-id format")
        if not isinstance(self.category, Category):
            raise TypeError("finding category must be a Category")
        if not isinstance(self.severity, Severity):
            raise TypeError("finding severity must be a Severity")
        _require_non_blank_text(self.message, "message")
        _require_non_blank_text(self.explanation, "explanation")
        if not isinstance(self.original, str):
            raise TypeError("original must be a string")
        if self.suggestion is not None and not isinstance(self.suggestion, str):
            raise TypeError("suggestion must be a string or None")
        if self.suggestion is not None and self.suggestion == self.original:
            raise ValueError("a non-None suggestion must differ from original")
        _require_offset(self.start, "start")
        _require_offset(self.end, "end")
        if self.end < self.start:
            raise ValueError("finding range must satisfy start <= end")
        if self.end - self.start != len(self.original):
            raise ValueError(
                "finding range length must equal the original Unicode code-point length"
            )
        if not isinstance(self.confidence, Confidence):
            raise TypeError("finding confidence must be a Confidence")
        if not isinstance(self.source, Source):
            raise TypeError("finding source must be a Source")
        expected_id = _stable_finding_id(
            category=self.category,
            source=self.source,
            start=self.start,
            end=self.end,
            original=self.original,
            suggestion=self.suggestion,
        )
        if self.id != expected_id:
            raise ValueError("finding id does not match the finding identity")

    @classmethod
    def create(
        cls,
        *,
        category: Category,
        severity: Severity,
        message: str,
        explanation: str,
        original: str,
        suggestion: str | None,
        start: int,
        end: int,
        confidence: Confidence,
        source: Source,
    ) -> Self:
        """Create a finding with a deterministic content-derived identifier.

        Presentation fields and confidence do not affect identity. This lets an
        analyzer improve its wording or confidence calibration without changing
        the identifier used to select the same underlying correction.
        """

        if not isinstance(category, Category):
            raise TypeError("finding category must be a Category")
        if not isinstance(source, Source):
            raise TypeError("finding source must be a Source")
        return cls(
            id=_stable_finding_id(
                category=category,
                source=source,
                start=start,
                end=end,
                original=original,
                suggestion=suggestion,
            ),
            category=category,
            severity=severity,
            message=message,
            explanation=explanation,
            original=original,
            suggestion=suggestion,
            start=start,
            end=end,
            confidence=confidence,
            source=source,
        )


@dataclass(frozen=True, slots=True, init=False)
class AnalysisOptions:
    """Filters requested for one analysis.

    ``categories=None`` selects every category. An empty collection explicitly
    selects no categories.
    """

    categories: frozenset[Category] | None
    minimum_confidence: Confidence

    def __init__(
        self,
        categories: Iterable[Category | str] | None = None,
        minimum_confidence: Confidence | float = 0.0,
    ) -> None:
        normalized_categories: frozenset[Category] | None
        if categories is None:
            normalized_categories = None
        else:
            if isinstance(categories, (str, bytes)):
                raise TypeError("categories must be an iterable of category values")
            normalized: set[Category] = set()
            for value in categories:
                if isinstance(value, Category):
                    normalized.add(value)
                    continue
                if not isinstance(value, str):
                    raise TypeError("each category must be a Category or string")
                try:
                    normalized.add(Category(value))
                except ValueError as error:
                    raise ValueError(f"unknown category: {value!r}") from error
            normalized_categories = frozenset(normalized)

        normalized_confidence = (
            minimum_confidence
            if isinstance(minimum_confidence, Confidence)
            else Confidence(minimum_confidence)
        )
        object.__setattr__(self, "categories", normalized_categories)
        object.__setattr__(self, "minimum_confidence", normalized_confidence)


@dataclass(frozen=True, slots=True, init=False)
class AnalysisResult:
    """Findings and effective options tied to one immutable source string."""

    text: str
    issues: tuple[Finding, ...]
    options: AnalysisOptions = field(default_factory=AnalysisOptions)

    def __init__(
        self,
        text: str,
        issues: Iterable[Finding] = (),
        options: AnalysisOptions | None = None,
    ) -> None:
        if not isinstance(text, str):
            raise TypeError("analysis text must be a string")
        if isinstance(issues, (str, bytes)):
            raise TypeError("issues must be an iterable of Finding values")
        normalized_issues = tuple(issues)
        for issue in normalized_issues:
            if not isinstance(issue, Finding):
                raise TypeError("every issue must be a Finding")
            if issue.end > len(text):
                raise ValueError(f"finding {issue.id!r} ends beyond the original text")
            if text[issue.start : issue.end] != issue.original:
                raise ValueError(
                    f"finding {issue.id!r} original does not match its text range"
                )
        ids = [issue.id for issue in normalized_issues]
        if len(ids) != len(set(ids)):
            raise ValueError("analysis result contains duplicate finding identifiers")
        if options is not None and not isinstance(options, AnalysisOptions):
            raise TypeError("options must be AnalysisOptions or None")
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "issues", normalized_issues)
        object.__setattr__(self, "options", options or AnalysisOptions())

    def to_json(self) -> str:
        """Serialize this result using the current canonical JSON schema."""

        from polis.core.serialization import analysis_result_to_json

        return cast(str, analysis_result_to_json(self))

    @staticmethod
    def from_json(value: str) -> AnalysisResult:
        """Deserialize and validate a result in a supported JSON schema."""

        from polis.core.serialization import analysis_result_from_json

        return cast(AnalysisResult, analysis_result_from_json(value))


def _require_non_blank_text(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} must not be blank")


def _stable_finding_id(
    *,
    category: Category,
    source: Source,
    start: int,
    end: int,
    original: str,
    suggestion: str | None,
) -> str:
    identity = {
        "category": category.value,
        "end": end,
        "id_version": _FINDING_ID_VERSION,
        "original": original,
        "source": str(source),
        "start": start,
        "suggestion": suggestion,
    }
    canonical = json.dumps(
        identity, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    digest = hashlib.blake2b(canonical, digest_size=16).hexdigest()
    return f"finding_{digest}"


def _require_offset(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer, not a boolean")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
