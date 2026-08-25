"""Repository-only parsers for post-change quality result reports."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Final

from polis.evaluation.quality_report_baseline import load_quality_report
from polis.evaluation.quality_report_models import QualityReport, QualityReportError
from polis.evaluation.quality_report_validation import (
    _integer,
    _load_json_object,
    _string,
)

_RESULT_SCHEMA_ID: Final = "polis.regression-result"
_LEGACY_RESULT_SCHEMA_ID: Final = "polis.quality-result"
_BASELINE_SCHEMA_ID: Final = "polis.regression-baseline"
_RESULT_SCHEMA_VERSION: Final = 1


def load_quality_result(path: Path) -> QualityReport:
    """Parse a post-change result report and reuse the baseline field contract."""

    root = _load_json_object(path, "quality result")
    schema_id = _string(root, "schema_id", "quality result")
    if schema_id not in {_RESULT_SCHEMA_ID, _LEGACY_RESULT_SCHEMA_ID}:
        raise QualityReportError("quality result schema_id mismatch")
    schema_version = root.get("schema_version")
    if schema_version != _RESULT_SCHEMA_VERSION:
        raise QualityReportError("quality result schema_version must be 1")

    dataset = root.get("dataset")
    if not isinstance(dataset, dict):
        raise QualityReportError("quality result dataset must be an object")
    dataset_schema_version = _integer(dataset, "schema_version", "dataset")
    if dataset_schema_version not in {2, 3, 4}:
        raise QualityReportError(
            "quality result dataset schema_version must be 2, 3, or 4"
        )

    # Result reports share the measured field contract with baselines of the
    # same dataset schema generation (v2, v3, or v4). A result must retain its
    # explicit result identity and cannot be silently accepted as a baseline.
    rewritten = dict(root)
    rewritten["schema_id"] = _BASELINE_SCHEMA_ID
    rewritten["schema_version"] = dataset_schema_version
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(
            json.dumps(rewritten, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    try:
        return load_quality_report(temporary)
    finally:
        temporary.unlink(missing_ok=True)


__all__ = ["load_quality_result"]
