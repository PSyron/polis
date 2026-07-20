"""Typing-only future public package surface approved by ADR-0003."""

from collections.abc import Mapping
from pathlib import Path
from typing import Final, Self

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
    def __init__(self) -> None: ...

    @classmethod
    def from_toml(cls, path: str | Path) -> Self: ...


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


def analysis_result_to_json(result: AnalysisResult) -> str: ...
def analysis_result_from_json(value: str) -> AnalysisResult: ...
