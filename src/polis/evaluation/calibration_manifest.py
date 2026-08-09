from __future__ import annotations

from typing import Final

from polis.evaluation.calibration_denominators import (
    CALIBRATION_CASE_COUNT,
    CALIBRATION_CORRECT_COUNT,
    CALIBRATION_ERROR_COUNT,
    HOLDOUT_CASE_COUNT,
    HOLDOUT_CORRECT_COUNT,
    HOLDOUT_ERROR_COUNT,
    SOURCE_DENOMINATORS,
    counts_for,
)
from polis.evaluation.calibration_freeze_models import (
    DatasetKind,
    FrozenDatasetManifest,
    PerSourceCount,
)
from polis.evaluation.calibration_json import (
    document,
    exact_object,
    fail,
    strict_digest,
    strict_integer,
    strict_number,
    strict_string,
    strict_string_list,
)
from polis.evaluation.calibration_models import JsonObject, JsonValue
from polis.evaluation.calibration_roles import (
    ASSIGNMENT_FIELDS,
    expected_authors,
    expected_custodian,
    expected_reviewer,
    parse_assignment,
)
from polis.evaluation.calibration_sources import SOURCE_ROWS, SOURCE_SNAPSHOT_SHA256

_FIELDS: Final = (
    frozenset(
        {
            "schema_id",
            "schema_version",
            "experiment_id",
            "dataset_id",
            "language",
            "license",
            "provenance",
            "source_snapshot_sha256",
            "source_rows",
            "case_count",
            "error_case_count",
            "correct_case_count",
            "per_source_counts",
            "dataset_sha256",
            "dataset_size_bytes",
            "dataset_mode",
            "author_role",
            "author_identities",
            "custodian_role",
            "custodian_identity",
            "reviewer_role",
            "reviewer_identity",
            "review_status",
            "reviewed_case_count",
            "review_manifest_sha256",
            "review_payload_sha256",
            "pii_status",
            "pii_scan_sha256",
            "overlap_policy_id",
        }
    )
    | ASSIGNMENT_FIELDS
)
_SOURCE_FIELDS: Final = frozenset(
    {
        "source",
        "category",
        "operation",
        "behavior_version",
        "source_policy_version",
        "emitted_confidence",
        "current_policy_state",
    }
)
_COUNT_FIELDS: Final = frozenset(
    {
        "source_identity",
        "error_case_count",
        "correct_case_count",
        "preregistered_verdict",
    }
)


def _expected(kind: DatasetKind) -> tuple[str, str, int, int, int]:
    if kind == "calibration":
        return (
            "polis.a-b-calibration.dataset-manifest",
            "polis-a-b-calibration-v2-v1",
            CALIBRATION_CASE_COUNT,
            CALIBRATION_ERROR_COUNT,
            CALIBRATION_CORRECT_COUNT,
        )
    return (
        "polis.a-b-holdout-v2.dataset-manifest",
        "polis-a-b-holdout-v2-v1",
        HOLDOUT_CASE_COUNT,
        HOLDOUT_ERROR_COUNT,
        HOLDOUT_CORRECT_COUNT,
    )


def _source(raw: JsonValue, index: int) -> tuple[str, str]:
    value = exact_object(raw, _SOURCE_FIELDS, "source identity")
    row = SOURCE_ROWS[index]
    observed = (
        strict_string(value["source"], "source"),
        strict_string(value["category"], "category"),
        strict_string(value["operation"], "operation"),
        strict_string(value["behavior_version"], "behavior version"),
        strict_string(value["source_policy_version"], "source policy version"),
        strict_number(value["emitted_confidence"], "emitted confidence"),
        strict_string(value["current_policy_state"], "policy state"),
    )
    if observed != row.as_tuple():
        fail("source identity does not match the approved ordered snapshot")
    return row.source, row.category


def _sources(value: JsonValue) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list) or len(value) != len(SOURCE_ROWS):
        fail("source rows must contain the exact 20 approved identities")
    return tuple(_source(item, index) for index, item in enumerate(value))


def _counts(
    value: JsonValue, sources: tuple[tuple[str, str], ...], kind: DatasetKind
) -> tuple[PerSourceCount, ...]:
    if not isinstance(value, list) or len(value) != len(sources):
        fail("per-source counts must contain exactly 20 rows")
    parsed: list[PerSourceCount] = []
    for index, item in enumerate(value):
        raw = exact_object(item, _COUNT_FIELDS, "per-source count")
        identity = _source(raw["source_identity"], index)
        counts = (
            strict_integer(raw["error_case_count"], "error case count"),
            strict_integer(raw["correct_case_count"], "correct case count"),
        )
        policy = SOURCE_DENOMINATORS[index]
        if (
            counts != counts_for(kind, policy.source)
            or identity != sources[index]
            or raw["preregistered_verdict"] != policy.preregistered_verdict
        ):
            fail("per-source counts do not match the frozen denominator")
        parsed.append(PerSourceCount(*identity, *counts, policy.preregistered_verdict))
    return tuple(parsed)


def _validate_identity(raw: JsonObject, kind: DatasetKind) -> None:
    schema, dataset_id, case_count, errors, correct = _expected(kind)
    identity = (
        raw["schema_id"],
        strict_integer(raw["schema_version"], "manifest schema version"),
        raw["experiment_id"],
        raw["dataset_id"],
        raw["language"],
        raw["license"],
        raw["provenance"],
        raw["source_snapshot_sha256"],
        raw["dataset_mode"],
        raw["review_status"],
        raw["pii_status"],
        raw["overlap_policy_id"],
    )
    expected = (
        schema,
        2,
        "polis-a-b-qualification-v2-v1",
        dataset_id,
        "pl",
        "CC0-1.0",
        "independently-authored",
        SOURCE_SNAPSHOT_SHA256,
        "0600",
        "APPROVE",
        "absent",
        "keyed-unicode-fivegram-jaccard-v1",
    )
    counts = tuple(
        strict_integer(raw[name], name)
        for name in (
            "case_count",
            "error_case_count",
            "correct_case_count",
            "reviewed_case_count",
        )
    )
    if identity != expected or counts != (case_count, errors, correct, case_count):
        fail("dataset manifest identity or aggregate counts are invalid")


def parse_frozen_dataset_manifest(
    raw_bytes: bytes, kind: DatasetKind
) -> FrozenDatasetManifest:
    raw = exact_object(document(raw_bytes, "dataset manifest"), _FIELDS, "manifest")
    _validate_identity(raw, kind)
    sources = _sources(raw["source_rows"])
    per_source = _counts(raw["per_source_counts"], sources, kind)
    authors = strict_string_list(raw["author_identities"], "author identities")
    custodian = strict_string(raw["custodian_identity"], "custodian identity")
    reviewer = strict_string(raw["reviewer_identity"], "reviewer identity")
    expected_roles = (
        f"{kind}-author",
        f"{kind}-custodian",
        f"{kind}-reviewer",
    )
    if (
        authors != expected_authors(kind)
        or custodian != expected_custodian(kind)
        or reviewer != expected_reviewer(kind)
        or tuple(
            raw[name] for name in ("author_role", "custodian_role", "reviewer_role")
        )
        != expected_roles
        or len({*authors, custodian, reviewer}) != 6
    ):
        fail("dataset manifest roles do not match the approved assignment")
    _, dataset_id, case_count, errors, correct = _expected(kind)
    size = strict_integer(raw["dataset_size_bytes"], "dataset size")
    if size <= 0:
        fail("dataset size must be positive")
    return FrozenDatasetManifest(
        kind,
        dataset_id,
        case_count,
        errors,
        correct,
        strict_digest(raw["dataset_sha256"], "dataset digest"),
        size,
        per_source,
        authors,
        custodian,
        reviewer,
        strict_digest(raw["review_manifest_sha256"], "review manifest digest"),
        strict_digest(raw["review_payload_sha256"], "review payload digest"),
        strict_digest(raw["pii_scan_sha256"], "PII scan digest"),
        parse_assignment(raw),
    )
