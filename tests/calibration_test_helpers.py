from __future__ import annotations

import hashlib
import json

from tests.denominator_test_constants import expected_counts

from polis.evaluation.calibration_models import JsonValue
from polis.evaluation.calibration_sources import SOURCE_ROWS, SOURCE_SNAPSHOT_SHA256

type JsonObject = dict[str, JsonValue]


def canonical_bytes(value: JsonValue) -> bytes:
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


def nonfinite_bytes(value: JsonValue) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=True,
        )
        + "\n"
    ).encode()


def source_rows_json() -> list[JsonValue]:
    return [list(row.as_tuple()) for row in SOURCE_ROWS]


def synthetic_config() -> JsonObject:
    return {
        "schema_id": "polis.a-b-calibration.config",
        "schema_version": 1,
        "experiment_id": "polis-a-b-qualification-v2-v1",
        "dataset_id": "polis-a-b-calibration-v2-v1",
        "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
        "source_rows": source_rows_json(),
        "threshold_profile": "active-baseline-v1",
        "thresholds": {
            "precision": 1.0,
            "recall": 0.7142857142857143,
            "f1": 0.8333333333333334,
            "exact_span_accuracy": 0.7142857142857143,
            "exact_correction_accuracy": 1.0,
            "correct_sentence_false_alarm_rate": 0.0,
        },
        "warmup_repetitions": 1,
        "measured_repetitions": 5,
        "minimum_error_cases_per_key": 20,
        "minimum_correct_cases_per_key": 40,
        "paths": {
            "dataset": ".omo/sealed/a-b-calibration-v2-v1/cases.json",
            "manifest": (
                "experiments/a-b-qualification-v2/calibration.dataset.manifest.json"
            ),
            "raw_report": ("experiments/a-b-qualification-v2/calibration.report.json"),
            "normalized_report": (
                "experiments/a-b-qualification-v2/calibration.normalized-report.json"
            ),
            "threshold_selection": (
                "experiments/a-b-qualification-v2/threshold-selection.json"
            ),
        },
    }


def synthetic_dataset() -> JsonObject:
    cases: list[JsonValue] = []
    for source_index, row in enumerate(SOURCE_ROWS):
        error_count, correct_count = expected_counts("calibration", row.source)
        for case_index in range(error_count):
            cases.append(
                {
                    "id": f"error-{source_index:02d}-{case_index:02d}",
                    "role": "error",
                    "primary_source_identity": row.source,
                    "text": f"Błąd🙂 {source_index}-{case_index}.",
                    "expected_findings": [
                        {
                            "source": row.source,
                            "category": row.category,
                            "start": 0,
                            "end": 4,
                            "original": "Błąd",
                            "suggestion": "Poprawa",
                        }
                    ],
                }
            )
        for case_index in range(correct_count):
            cases.append(
                {
                    "id": f"correct-{source_index:02d}-{case_index:02d}",
                    "role": "correct",
                    "primary_source_identity": row.source,
                    "text": f"Poprawne zdanie {source_index}-{case_index}.",
                    "expected_findings": [],
                }
            )
    return {
        "schema_id": "polis.a-b-calibration.dataset",
        "schema_version": 1,
        "dataset_id": "polis-a-b-calibration-v2-v1",
        "language": "pl",
        "cases": cases,
    }


def synthetic_manifest(dataset_bytes: bytes) -> JsonObject:
    return {
        "schema_id": "polis.a-b-calibration.dataset-manifest",
        "schema_version": 1,
        "dataset_id": "polis-a-b-calibration-v2-v1",
        "license": "CC0-1.0",
        "provenance": "public-synthetic",
        "author_role": "calibration-dataset-author",
        "reviewer_role": "independent-calibration-reviewer",
        "review_status": "approved",
        "case_count": 1073,
        "reviewed_case_count": 1073,
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "dataset_size_bytes": len(dataset_bytes),
        "pii_status": "absent",
    }
