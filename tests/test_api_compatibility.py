from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from polis import ANALYSIS_SCHEMA_VERSION, AnalysisResult, Analyzer, AnalyzerConfig
from polis import __all__ as public_exports


def _load_snapshot() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "fixtures" / "public_api_snapshot.json"
    with path.open(encoding="utf-8") as stream:
        return cast(dict[str, Any], json.load(stream))


def test_public_api_snapshot_stability() -> None:
    snapshot = _load_snapshot()
    expected = sorted(snapshot["public_exports"])
    assert sorted(public_exports) == expected


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
    result = Analyzer(AnalyzerConfig(use_local_heuristic_backend=True)).correct("zeby")

    assert result.source_policy_version == "1.2"
    assert result.suggestion_outcomes
    assert all(
        outcome.source_policy_version == result.source_policy_version
        for outcome in result.suggestion_outcomes
    )
    assert {
        "SOURCE_POLICY_VERSION",
        "SourceBehavior",
        "SourcePolicyKey",
        "is_automatic_correction_eligible",
    }.isdisjoint(public_exports)


def test_evaluation_namespace_remains_compatible_for_the_0x_line() -> None:
    import polis.evaluation as evaluation

    assert callable(evaluation.load_dataset)
    assert callable(evaluation.validate_dataset)
