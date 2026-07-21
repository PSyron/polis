"""Polis public package namespace."""

from importlib.metadata import version

from polis.analyzer import Analyzer, AnalyzerConfig, CorrectionResult
from polis.core import (
    ANALYSIS_SCHEMA_VERSION,
    AnalysisOptions,
    AnalysisResult,
    AnalysisTimeoutError,
    BackendUnavailableError,
    Category,
    Confidence,
    ConfigurationError,
    CorrectionConflictError,
    CorrectionSelectionError,
    Finding,
    InvalidBackendResponseError,
    PolisError,
    Severity,
    Source,
    SourceKind,
    UncorrectableFindingError,
    UnknownFindingError,
    analysis_result_from_json,
    analysis_result_to_json,
)

__version__ = version("polis-nlp")

__all__ = [
    "ANALYSIS_SCHEMA_VERSION",
    "Analyzer",
    "AnalyzerConfig",
    "CorrectionResult",
    "AnalysisOptions",
    "AnalysisResult",
    "Category",
    "Confidence",
    "PolisError",
    "AnalysisTimeoutError",
    "BackendUnavailableError",
    "ConfigurationError",
    "InvalidBackendResponseError",
    "CorrectionSelectionError",
    "UnknownFindingError",
    "UncorrectableFindingError",
    "CorrectionConflictError",
    "Finding",
    "Severity",
    "Source",
    "SourceKind",
    "__version__",
    "analysis_result_from_json",
    "analysis_result_to_json",
]
