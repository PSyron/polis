from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from polis import ANALYSIS_SCHEMA_VERSION, AnalysisResult, Analyzer, AnalyzerConfig
from polis import __all__ as public_exports

EXPECTED_PUBLIC_EXPORTS = (
    "ANALYSIS_SCHEMA_VERSION",
    "Analyzer",
    "AnalyzerConfig",
    "CorrectionResult",
    "SuggestionOutcome",
    "SuggestionStatus",
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
)

EXPECTED_EVALUATION_EXPORTS = (
    "BaselineResult",
    "EvaluationDataset",
    "QualityCounts",
    "SAFETY_CORPUS_ID",
    "SAFETY_CORPUS_V2_ID",
    "SAFETY_REVIEW_CHECKLIST_VERSION",
    "SAFETY_REVIEW_CHECKLIST_V2_VERSION",
    "assert_no_cross_corpus_leakage",
    "evaluate_baseline",
    "findings_snapshot_for_run",
    "load_dataset",
    "load_safety_corpus_json",
    "load_safety_corpus_xml",
    "safety_corpus_digest",
    "safety_entity_catalog_ids",
    "select_safety_cases_for_purpose",
    "validate_dataset",
    "validate_safety_corpus",
)


def _load_snapshot() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "fixtures" / "public_api_snapshot.json"
    with path.open(encoding="utf-8") as stream:
        return cast(dict[str, Any], json.load(stream))


def test_public_api_snapshot_stability() -> None:
    snapshot = _load_snapshot()
    expected = sorted(snapshot["public_exports"])
    assert sorted(public_exports) == expected


def test_root_namespace_retains_the_exact_public_contract() -> None:
    assert tuple(public_exports) == EXPECTED_PUBLIC_EXPORTS


def test_schema_compatibility_constants_stay_stable() -> None:
    snapshot = _load_snapshot()
    assert snapshot["analysis_schema_version"] == ANALYSIS_SCHEMA_VERSION

    sample = AnalysisResult(
        text="To zdanie sprawdza zgodność.",
        issues=(),
        options=None,
    )
    payload = json.loads(sample.to_json())
    assert payload["schema_version"] == snapshot["result_schema_version"]


def test_correction_result_exposes_policy_identity_without_policy_internals() -> None:
    result = Analyzer(AnalyzerConfig()).correct("zeby")

    assert result.source_policy_version == "1.2"
    assert result.suggestion_outcomes == ()
    assert {
        "SOURCE_POLICY_VERSION",
        "SourceBehavior",
        "SourcePolicyKey",
        "is_automatic_correction_eligible",
    }.isdisjoint(public_exports)


def test_evaluation_namespace_retains_the_literal_1_0_contract() -> None:
    import polis.evaluation as evaluation

    assert tuple(evaluation.__all__) == EXPECTED_EVALUATION_EXPORTS


def test_quality_runner_is_not_exported_from_public_namespaces() -> None:
    import polis.evaluation as evaluation

    assert "quality_runner" not in public_exports
    assert "quality_runner" not in evaluation.__all__
