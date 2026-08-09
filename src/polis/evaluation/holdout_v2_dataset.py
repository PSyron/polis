from __future__ import annotations

import hashlib
from typing import Final

from polis.evaluation.calibration_denominators import HOLDOUT_CASE_COUNT, counts_for
from polis.evaluation.calibration_freeze_models import (
    FrozenDatasetManifest,
    HoldoutV2Dataset,
)
from polis.evaluation.calibration_json import (
    document,
    exact_object,
    fail,
    strict_integer,
    strict_string,
)
from polis.evaluation.calibration_models import (
    CalibrationCase,
    CalibrationRole,
    ExpectedFinding,
    JsonValue,
)
from polis.evaluation.calibration_sources import SOURCE_ROWS

_ROOT_FIELDS: Final = frozenset(
    {"schema_id", "schema_version", "dataset_id", "language", "cases"}
)
_CASE_FIELDS: Final = frozenset(
    {"id", "role", "primary_source_identity", "text", "expected_findings"}
)
_FINDING_FIELDS: Final = frozenset(
    {"source", "category", "start", "end", "original", "suggestion"}
)


def _role(value: JsonValue) -> CalibrationRole:
    if value == "error":
        return "error"
    if value == "correct":
        return "correct"
    fail("holdout case role must be error or correct")


def _finding(value: JsonValue, text: str) -> ExpectedFinding:
    raw = exact_object(value, _FINDING_FIELDS, "expected finding")
    start = strict_integer(raw["start"], "finding start")
    end = strict_integer(raw["end"], "finding end")
    original_value = raw["original"]
    if not isinstance(original_value, str):
        fail("finding original must be a string")
    original = original_value
    suggestion_value = raw["suggestion"]
    if not isinstance(suggestion_value, str):
        fail("finding suggestion must be a string")
    suggestion = suggestion_value
    if (
        not 0 <= start <= end <= len(text)
        or (start == end) != (original == "")
        or text[start:end] != original
    ):
        fail("expected finding must match its Unicode half-open text span")
    if suggestion == original:
        fail("expected finding suggestion must differ from original")
    return ExpectedFinding(
        strict_string(raw["source"], "finding source"),
        strict_string(raw["category"], "finding category"),
        start,
        end,
        original,
        suggestion,
    )


def _case(
    value: JsonValue,
    expected_id: str,
    expected_source: str,
    expected_category: str,
    expected_role: CalibrationRole,
) -> CalibrationCase:
    raw = exact_object(value, _CASE_FIELDS, "holdout case")
    case_id = strict_string(raw["id"], "case id")
    role = _role(raw["role"])
    primary = strict_string(raw["primary_source_identity"], "primary source")
    text = strict_string(raw["text"], "case text")
    values = raw["expected_findings"]
    if not isinstance(values, list):
        fail("expected findings must be a list")
    findings = tuple(_finding(item, text) for item in values)
    if case_id != expected_id or role != expected_role or primary != expected_source:
        fail("holdout case order or primary identity is invalid")
    if role == "correct" and findings:
        fail("correct holdout case must contain no expected findings")
    if role == "error" and (
        len(findings) != 1
        or findings[0].source != primary
        or findings[0].category != expected_category
    ):
        fail("error holdout case must contain one finding for its primary source")
    return CalibrationCase(case_id, role, primary, text, findings)


def _expected_rows() -> tuple[tuple[str, str, str, CalibrationRole], ...]:
    return tuple(
        (
            f"hold-v2-{source_index:02d}-{role}-{case_index:02d}",
            row.source,
            row.category,
            role,
        )
        for source_index, row in enumerate(SOURCE_ROWS)
        for role, count in zip(
            ("error", "correct"), counts_for("holdout", row.source), strict=True
        )
        for case_index in range(count)
    )


def load_holdout_v2_dataset_bytes(
    raw_bytes: bytes, manifest: FrozenDatasetManifest
) -> HoldoutV2Dataset:
    if manifest.kind != "holdout":
        fail("holdout loader requires the frozen holdout manifest")
    raw = exact_object(document(raw_bytes, "holdout dataset"), _ROOT_FIELDS, "dataset")
    identity = (
        raw["schema_id"],
        strict_integer(raw["schema_version"], "dataset schema version"),
        raw["dataset_id"],
        raw["language"],
    )
    if identity != (
        "polis.a-b-holdout-v2.dataset",
        1,
        "polis-a-b-holdout-v2-v1",
        "pl",
    ):
        fail("holdout dataset identity is invalid")
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if (
        digest != manifest.dataset_sha256
        or len(raw_bytes) != manifest.dataset_size_bytes
    ):
        fail("holdout dataset does not match its frozen manifest")
    values = raw["cases"]
    expected = _expected_rows()
    if not isinstance(values, list) or len(values) != len(expected):
        fail(f"holdout dataset must contain exactly {HOLDOUT_CASE_COUNT} cases")
    cases = tuple(_case(value, *expected[index]) for index, value in enumerate(values))
    if len({case.id for case in cases}) != len(cases):
        fail("holdout case ids must be unique")
    return HoldoutV2Dataset(manifest.dataset_id, cases, digest)
