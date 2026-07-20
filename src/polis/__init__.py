"""Polis public package namespace."""

from importlib.metadata import version

from polis.core import (
    ANALYSIS_SCHEMA_VERSION,
    AnalysisOptions,
    AnalysisResult,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
    analysis_result_from_json,
    analysis_result_to_json,
)

__version__ = version("polis-nlp")

__all__ = [
    "ANALYSIS_SCHEMA_VERSION",
    "AnalysisOptions",
    "AnalysisResult",
    "Category",
    "Confidence",
    "Finding",
    "Severity",
    "Source",
    "SourceKind",
    "__version__",
    "analysis_result_from_json",
    "analysis_result_to_json",
]
