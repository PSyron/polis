"""Typing-only future public package surface approved by ADR-0003."""

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final, Literal, Self

from .core.models import (
    AnalysisOptions as AnalysisOptions,
    AnalysisResult as AnalysisResult,
    Category as Category,
    Confidence as Confidence,
    Finding as Finding,
    Severity as Severity,
    Source as Source,
    SourceKind as SourceKind,
)

ANALYSIS_SCHEMA_VERSION: Final[int]
__version__: str

class PolisError(Exception):
    code: str
    retryable: bool
    context: Mapping[str, str]

class ConfigurationError(PolisError): ...
class BackendUnavailableError(PolisError): ...
class AnalysisTimeoutError(PolisError): ...
class InvalidBackendResponseError(PolisError): ...
class CorrectionSelectionError(PolisError): ...
class UnknownFindingError(CorrectionSelectionError): ...
class UncorrectableFindingError(CorrectionSelectionError): ...
class CorrectionConflictError(CorrectionSelectionError): ...

class AnalyzerConfig:
    categories: frozenset[Category] | None
    minimum_confidence: float
    def __init__(
        self,
        categories: frozenset[Category] | None = None,
        minimum_confidence: float = 0.0,
    ) -> None: ...
    @classmethod
    def from_toml(cls, path: str | Path) -> Self: ...
    @classmethod
    def from_config(cls, path: str | Path) -> Self: ...

class CorrectionResult:
    original_text: str
    corrected_text: str
    applied_findings: tuple[Finding, ...]
    skipped_findings: tuple[Finding, ...]
    suggestion_outcomes: tuple[SuggestionOutcome, ...]
    source_policy_version: str
    def apply_suggestions(self, finding_ids: Iterable[str]) -> str: ...

SuggestionStatus = Literal["complete", "unavailable", "timed_out", "invalid_response"]

class SuggestionOutcome:
    status: SuggestionStatus
    backend: str
    operation: str
    suggestions: int
    model_calls: int
    protocol_versions: tuple[str, ...]
    operation_version: str
    source_policy_version: str

class Analyzer:
    def __init__(self, config: AnalyzerConfig) -> None: ...
    @classmethod
    def from_config(cls, path: str | Path) -> Self: ...
    def analyze(
        self, text: str, *, options: AnalysisOptions | None = None
    ) -> AnalysisResult: ...
    async def analyze_async(
        self, text: str, *, options: AnalysisOptions | None = None
    ) -> AnalysisResult: ...
    def correct(self, text: str) -> CorrectionResult: ...
    async def correct_async(self, text: str) -> CorrectionResult: ...
    @property
    def language_tool_process_start_count(self) -> int: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *args: object) -> None: ...

def analysis_result_to_json(result: AnalysisResult) -> str: ...
def analysis_result_from_json(value: str) -> AnalysisResult: ...
