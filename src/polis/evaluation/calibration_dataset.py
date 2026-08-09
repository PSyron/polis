from __future__ import annotations

import hashlib

from polis.evaluation.calibration_contract import (
    _document,
    _fail,
    _integer,
    _object,
    _string,
)
from polis.evaluation.calibration_models import (
    CalibrationCase,
    CalibrationConfig,
    CalibrationDataset,
    CalibrationManifest,
    CalibrationRole,
    ExpectedFinding,
    JsonValue,
)

_ROOT_FIELDS = {"schema_id", "schema_version", "dataset_id", "language", "cases"}
_CASE_FIELDS = {"id", "role", "primary_source_identity", "text", "expected_findings"}
_FINDING_FIELDS = {"source", "category", "start", "end", "original", "suggestion"}


def _role(value: JsonValue) -> CalibrationRole:
    if value == "error":
        return "error"
    if value == "correct":
        return "correct"
    _fail("calibration case role must be error or correct")


def _finding(value: JsonValue, text: str) -> ExpectedFinding:
    raw = _object(value, _FINDING_FIELDS, "expected finding")
    start = _integer(raw["start"], "finding start")
    end = _integer(raw["end"], "finding end")
    original = _string(raw["original"], "finding original")
    suggestion = _string(raw["suggestion"], "finding suggestion")
    if not 0 <= start < end <= len(text) or text[start:end] != original:
        _fail("expected finding must match its Unicode half-open text span")
    if suggestion == original:
        _fail("expected finding suggestion must differ from original")
    return ExpectedFinding(
        _string(raw["source"], "finding source"),
        _string(raw["category"], "finding category"),
        start,
        end,
        original,
        suggestion,
    )


def _case(value: JsonValue, categories: dict[str, str]) -> CalibrationCase:
    raw = _object(value, _CASE_FIELDS, "calibration case")
    case_id = _string(raw["id"], "case id")
    role = _role(raw["role"])
    primary = _string(raw["primary_source_identity"], "primary source identity")
    text = _string(raw["text"], "case text")
    if primary not in categories:
        _fail("calibration case primary source is unknown")
    values = raw["expected_findings"]
    if not isinstance(values, list):
        _fail("expected findings must be a list")
    findings = tuple(_finding(item, text) for item in values)
    if role == "correct" and findings:
        _fail("correct calibration case must contain no expected findings")
    if role == "error" and (
        len(findings) != 1
        or findings[0].source != primary
        or findings[0].category != categories[primary]
    ):
        _fail("error calibration case must contain one finding for its primary source")
    return CalibrationCase(case_id, role, primary, text, findings)


def load_calibration_dataset_bytes(
    raw_bytes: bytes,
    manifest: CalibrationManifest,
    config: CalibrationConfig,
) -> CalibrationDataset:
    raw = _document(raw_bytes, "calibration dataset")
    if set(raw) != _ROOT_FIELDS:
        _fail("calibration dataset must contain exactly the required fields")
    schema_version = _integer(raw["schema_version"], "dataset schema version")
    if (
        tuple(
            raw[name]
            for name in (
                "schema_id",
                "dataset_id",
                "language",
            )
        )
        != (
            "polis.a-b-calibration.dataset",
            config.dataset_id,
            "pl",
        )
        or schema_version != 1
    ):
        _fail("calibration dataset identity is invalid")
    digest = hashlib.sha256(raw_bytes).hexdigest()
    if (
        manifest.dataset_id != config.dataset_id
        or len(raw_bytes) != manifest.dataset_size_bytes
        or digest != manifest.dataset_sha256
    ):
        _fail("calibration dataset does not match its reviewed manifest")
    values = raw["cases"]
    if not isinstance(values, list) or len(values) != manifest.case_count:
        _fail("calibration dataset case count is invalid")
    categories = {row.source: row.category for row in config.source_rows}
    cases = tuple(_case(value, categories) for value in values)
    ids = [case.id for case in cases]
    if len(set(ids)) != len(ids):
        _fail("calibration dataset case ids must be unique")
    counts: dict[tuple[str, CalibrationRole], int] = {}
    for case in cases:
        key = (case.primary_source_identity, case.role)
        counts[key] = counts.get(key, 0) + 1
    for source in categories:
        if (
            counts.get((source, "error"), 0) < config.minimum_error_cases_per_key
            or counts.get((source, "correct"), 0) < config.minimum_correct_cases_per_key
        ):
            _fail("calibration dataset is below a per-source minimum")
    return CalibrationDataset(config.dataset_id, cases, digest)
