from __future__ import annotations

from polis.evaluation.holdout_json import (
    fail,
    integer_value,
    object_value,
    string_value,
)
from polis.evaluation.holdout_models import DatasetIdentity, JsonValue
from polis.evaluation.holdout_preregistration import DATASET_SHA256

_DATASET_FIELDS = {
    "sha256",
    "size_bytes",
    "case_count",
    "source_count",
    "license",
    "provenance",
    "review_status",
    "reviewed_case_count",
    "mode",
}


def parse_dataset_identity(value: JsonValue) -> DatasetIdentity:
    raw = object_value(value, _DATASET_FIELDS, "dataset")
    dataset = DatasetIdentity(
        string_value(raw["sha256"], "dataset sha256"),
        integer_value(raw["size_bytes"], "dataset size_bytes"),
        integer_value(raw["case_count"], "dataset case_count"),
        integer_value(raw["source_count"], "dataset source_count"),
        string_value(raw["license"], "dataset license"),
        string_value(raw["provenance"], "dataset provenance"),
        string_value(raw["review_status"], "independent review"),
        integer_value(raw["reviewed_case_count"], "review coverage"),
        string_value(raw["mode"], "dataset mode"),
    )
    if dataset.license != "CC0-1.0":
        fail("unapproved dataset license")
    if dataset.review_status != "APPROVE":
        fail("independent review is required")
    if dataset.reviewed_case_count != dataset.case_count:
        fail("review coverage must be complete")
    if (
        dataset.sha256,
        dataset.size_bytes,
        dataset.case_count,
        dataset.source_count,
        dataset.provenance,
        dataset.mode,
    ) != (
        DATASET_SHA256,
        17370,
        52,
        20,
        "project-authored-independent-review",
        "0600",
    ):
        fail("dataset identity does not match the approved sealed metadata")
    return dataset
