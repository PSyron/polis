from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Final, NoReturn

from polis.evaluation.calibration_models import (
    CalibrationConfig,
    CalibrationContractError,
    CalibrationManifest,
    CalibrationPaths,
    CalibrationThresholds,
    JsonObject,
    JsonValue,
)
from polis.evaluation.calibration_sources import (
    SOURCE_SNAPSHOT_SHA256,
    parse_source_rows,
)

_CONFIG_FIELDS: Final = {
    "schema_id",
    "schema_version",
    "experiment_id",
    "dataset_id",
    "source_snapshot_sha256",
    "source_rows",
    "threshold_profile",
    "thresholds",
    "warmup_repetitions",
    "measured_repetitions",
    "minimum_error_cases_per_key",
    "minimum_correct_cases_per_key",
    "paths",
}
_THRESHOLD_FIELDS: Final = {
    "precision",
    "recall",
    "f1",
    "exact_span_accuracy",
    "exact_correction_accuracy",
    "correct_sentence_false_alarm_rate",
}
_PATH_FIELDS: Final = {
    "dataset",
    "manifest",
    "raw_report",
    "normalized_report",
    "threshold_selection",
}
_MANIFEST_FIELDS: Final = {
    "schema_id",
    "schema_version",
    "dataset_id",
    "license",
    "provenance",
    "author_role",
    "reviewer_role",
    "review_status",
    "case_count",
    "reviewed_case_count",
    "dataset_sha256",
    "dataset_size_bytes",
    "pii_status",
}
_EXPECTED_THRESHOLDS: Final = (
    1.0,
    0.7142857142857143,
    0.8333333333333334,
    0.7142857142857143,
    1.0,
    0.0,
)
_EXPECTED_PATHS: Final = (
    ".omo/sealed/a-b-calibration-v2-v1/cases.json",
    "experiments/a-b-qualification-v2/calibration.dataset.manifest.json",
    "experiments/a-b-qualification-v2/calibration.report.json",
    "experiments/a-b-qualification-v2/calibration.normalized-report.json",
    "experiments/a-b-qualification-v2/threshold-selection.json",
)


def _fail(message: str) -> NoReturn:
    raise CalibrationContractError(message)


def _canonical(value: JsonValue) -> bytes:
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode()
    except ValueError as error:
        raise CalibrationContractError("document contains non-finite data") from error


def _document(raw_bytes: bytes, label: str) -> JsonObject:
    def reject_constant(value: str) -> NoReturn:
        _fail(f"{label} contains non-finite constant {value}")

    try:
        value = json.loads(raw_bytes, parse_constant=reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalibrationContractError(f"{label} is invalid JSON") from error
    if not isinstance(value, dict) or raw_bytes != _canonical(value):
        _fail(f"{label} must be a canonical JSON object")
    return value


def _object(value: JsonValue, fields: set[str], label: str) -> JsonObject:
    if not isinstance(value, dict) or set(value) != fields:
        _fail(f"{label} must contain exactly the required fields")
    return value


def _string(value: JsonValue, label: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{label} must be a non-empty string")
    return value


def _integer(value: JsonValue, label: str) -> int:
    if type(value) is not int:
        _fail(f"{label} must be an integer")
    return value


def _number(value: JsonValue, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        _fail(f"{label} must be a finite number")
    return float(value)


def parse_calibration_config(raw_bytes: bytes) -> CalibrationConfig:
    raw = _document(raw_bytes, "calibration config")
    if set(raw) != _CONFIG_FIELDS:
        _fail("calibration config must contain exactly the required fields")
    schema_version = _integer(raw["schema_version"], "config schema version")
    identity = tuple(
        raw[name]
        for name in (
            "schema_id",
            "experiment_id",
            "dataset_id",
            "source_snapshot_sha256",
            "threshold_profile",
        )
    )
    if (
        identity
        != (
            "polis.a-b-calibration.config",
            "polis-a-b-qualification-v2-v1",
            "polis-a-b-calibration-v2-v1",
            SOURCE_SNAPSHOT_SHA256,
            "active-baseline-v1",
        )
        or schema_version != 1
    ):
        _fail("calibration config identity does not match the approved contract")
    thresholds_raw = _object(raw["thresholds"], _THRESHOLD_FIELDS, "thresholds")
    thresholds_values = tuple(
        _number(thresholds_raw[name], name)
        for name in (
            "precision",
            "recall",
            "f1",
            "exact_span_accuracy",
            "exact_correction_accuracy",
            "correct_sentence_false_alarm_rate",
        )
    )
    if thresholds_values != _EXPECTED_THRESHOLDS:
        _fail("thresholds do not match active-baseline-v1")
    counts = tuple(
        _integer(raw[name], name)
        for name in (
            "warmup_repetitions",
            "measured_repetitions",
            "minimum_error_cases_per_key",
            "minimum_correct_cases_per_key",
        )
    )
    if counts != (1, 5, 20, 40):
        _fail("repetition and minimum counts must match the approved contract")
    paths_raw = _object(raw["paths"], _PATH_FIELDS, "paths")
    paths_values = tuple(
        _string(paths_raw[name], name)
        for name in (
            "dataset",
            "manifest",
            "raw_report",
            "normalized_report",
            "threshold_selection",
        )
    )
    if paths_values != _EXPECTED_PATHS:
        _fail("paths must match the approved repository layout")
    thresholds = CalibrationThresholds(*thresholds_values)
    paths = CalibrationPaths(*(Path(value) for value in paths_values))
    return CalibrationConfig(
        "polis-a-b-qualification-v2-v1",
        "polis-a-b-calibration-v2-v1",
        parse_source_rows(raw["source_rows"]),
        "active-baseline-v1",
        thresholds,
        *counts,
        paths,
    )


def parse_calibration_manifest(raw_bytes: bytes) -> CalibrationManifest:
    raw = _document(raw_bytes, "calibration manifest")
    if set(raw) != _MANIFEST_FIELDS:
        _fail("calibration manifest must contain exactly the required fields")
    case_count = _integer(raw["case_count"], "case count")
    reviewed = _integer(raw["reviewed_case_count"], "reviewed case count")
    size = _integer(raw["dataset_size_bytes"], "dataset size")
    digest = _string(raw["dataset_sha256"], "dataset digest")
    schema_version = _integer(raw["schema_version"], "manifest schema version")
    identity = tuple(
        raw[name]
        for name in (
            "schema_id",
            "dataset_id",
            "license",
            "provenance",
            "author_role",
            "reviewer_role",
            "review_status",
            "pii_status",
        )
    )
    if (
        identity
        != (
            "polis.a-b-calibration.dataset-manifest",
            "polis-a-b-calibration-v2-v1",
            "CC0-1.0",
            "public-synthetic",
            "calibration-dataset-author",
            "independent-calibration-reviewer",
            "approved",
            "absent",
        )
        or schema_version != 1
    ):
        _fail("calibration manifest review identity is invalid")
    if case_count != 1200 or reviewed != case_count or size <= 0:
        _fail("calibration manifest counts are invalid")
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        _fail("calibration manifest digest is invalid")
    return CalibrationManifest(
        "polis-a-b-calibration-v2-v1", case_count, reviewed, digest, size
    )
