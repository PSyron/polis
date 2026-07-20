from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from polis import ANALYSIS_SCHEMA_VERSION, AnalysisResult
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
