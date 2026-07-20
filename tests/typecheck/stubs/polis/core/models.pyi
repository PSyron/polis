"""Typing mirror of the existing public result models used by contract checks."""

from collections.abc import Iterable
from enum import StrEnum
from typing import Self


class Category(StrEnum):
    INFLECTION = "inflection"
    AGREEMENT = "agreement"
    SYNTAX = "syntax"
    SPELLING = "spelling"
    PUNCTUATION = "punctuation"
    STYLE = "style"


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    SUGGESTION = "suggestion"


class SourceKind(StrEnum):
    RULE = "rule"
    LLM = "llm"


class Source:
    kind: SourceKind
    name: str

    def __init__(self, kind: SourceKind, name: str) -> None: ...
    def __str__(self) -> str: ...

    @classmethod
    def parse(cls, value: str) -> Self: ...


class Confidence:
    value: float

    def __init__(self, value: float) -> None: ...


class Finding:
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
    ) -> Self: ...


class AnalysisOptions:
    categories: frozenset[Category] | None
    minimum_confidence: Confidence

    def __init__(
        self,
        categories: Iterable[Category | str] | None = None,
        minimum_confidence: Confidence | float = 0.0,
    ) -> None: ...


class AnalysisResult:
    text: str
    issues: tuple[Finding, ...]
    options: AnalysisOptions

    def __init__(
        self,
        text: str,
        issues: Iterable[Finding] = (),
        options: AnalysisOptions | None = None,
    ) -> None: ...

    def to_json(self) -> str: ...

    @staticmethod
    def from_json(value: str) -> AnalysisResult: ...

    def apply(self, issue_ids: Iterable[str]) -> str: ...
