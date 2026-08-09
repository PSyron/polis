from __future__ import annotations

import hashlib
from typing import Final

from polis.evaluation.calibration_denominators import expected_case_rows
from polis.evaluation.calibration_freeze_models import (
    CaseReview,
    DatasetKind,
    DatasetReview,
)
from polis.evaluation.calibration_json import (
    canonical_bytes,
    document,
    exact_object,
    fail,
    strict_digest,
    strict_integer,
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
from polis.evaluation.calibration_sources import SOURCE_SNAPSHOT_SHA256

_FIELDS: Final = (
    frozenset(
        {
            "schema_id",
            "schema_version",
            "experiment_id",
            "dataset_id",
            "dataset_sha256",
            "source_snapshot_sha256",
            "checklist_version",
            "author_role",
            "author_identities",
            "custodian_role",
            "custodian_identity",
            "reviewer_role",
            "reviewer_identity",
            "independence_status",
            "review_status",
            "reviewed_case_count",
            "case_reviews",
            "review_payload_sha256",
            "approval_digest",
        }
    )
    | ASSIGNMENT_FIELDS
)
_CASE_FIELDS: Final = frozenset(
    {
        "case_id",
        "author_identity",
        "case_payload_sha256",
        "license",
        "provenance",
        "role_semantics",
        "linguistic_validity",
        "minimal_correction",
        "span_validity",
        "source_binding",
        "pii_status",
        "review_status",
    }
)


def _expected_case_ids(kind: DatasetKind) -> tuple[str, ...]:
    return tuple(row.case_id for row in expected_case_rows(kind))


def _review_case(
    value: JsonValue, expected_id: str, authors: tuple[str, ...]
) -> CaseReview:
    raw = exact_object(value, _CASE_FIELDS, "case review")
    case_id = strict_string(raw["case_id"], "reviewed case id")
    author = strict_string(raw["author_identity"], "case author identity")
    verdicts = tuple(
        raw[name]
        for name in (
            "role_semantics",
            "linguistic_validity",
            "minimal_correction",
            "span_validity",
            "source_binding",
            "review_status",
        )
    )
    if (
        case_id != expected_id
        or author not in authors
        or raw["license"] != "CC0-1.0"
        or raw["provenance"] != "independently-authored"
        or verdicts != ("APPROVE",) * 6
        or raw["pii_status"] != "absent"
    ):
        fail("case review does not match the approved independent checklist")
    return CaseReview(
        case_id,
        author,
        strict_digest(raw["case_payload_sha256"], "reviewed case payload digest"),
    )


def _approval_digest(raw: JsonObject) -> str:
    payload: JsonObject = {}
    for key, value in raw.items():
        if key != "approval_digest":
            payload[key] = value
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def parse_dataset_review(
    raw_bytes: bytes, kind: DatasetKind, review_payload_bytes: bytes
) -> DatasetReview:
    raw = exact_object(document(raw_bytes, "dataset review"), _FIELDS, "review")
    expected_ids = _expected_case_ids(kind)
    dataset_id = (
        "polis-a-b-calibration-v2-v1"
        if kind == "calibration"
        else "polis-a-b-holdout-v2-v1"
    )
    identity = (
        raw["schema_id"],
        strict_integer(raw["schema_version"], "review schema version"),
        raw["experiment_id"],
        raw["dataset_id"],
        raw["source_snapshot_sha256"],
        raw["checklist_version"],
        raw["independence_status"],
        raw["review_status"],
    )
    expected_identity = (
        "polis.a-b-qualification-v2.dataset-review",
        1,
        "polis-a-b-qualification-v2-v1",
        dataset_id,
        SOURCE_SNAPSHOT_SHA256,
        "independent-dataset-review-v1",
        "APPROVE",
        "APPROVE",
    )
    reviewed = strict_integer(raw["reviewed_case_count"], "reviewed case count")
    if identity != expected_identity or reviewed != len(expected_ids):
        fail("dataset review identity or coverage is invalid")
    authors = strict_string_list(raw["author_identities"], "author identities")
    custodian = strict_string(raw["custodian_identity"], "custodian identity")
    reviewer = strict_string(raw["reviewer_identity"], "reviewer identity")
    if (
        authors != expected_authors(kind)
        or custodian != expected_custodian(kind)
        or reviewer != expected_reviewer(kind)
        or tuple(
            raw[name] for name in ("author_role", "custodian_role", "reviewer_role")
        )
        != (f"{kind}-author", f"{kind}-custodian", f"{kind}-reviewer")
        or len({*authors, custodian, reviewer}) != 6
    ):
        fail("dataset review roles do not match the approved assignment")
    values = raw["case_reviews"]
    if not isinstance(values, list) or len(values) != len(expected_ids):
        fail("case reviews must cover every case exactly once")
    payload_digest = hashlib.sha256(review_payload_bytes).hexdigest()
    if (
        review_payload_bytes != canonical_bytes(values)
        or raw["review_payload_sha256"] != payload_digest
    ):
        fail("review payload must match the complete canonical review records")
    cases = tuple(
        _review_case(value, expected_ids[index], authors)
        for index, value in enumerate(values)
    )
    approval = strict_digest(raw["approval_digest"], "approval digest")
    if approval != _approval_digest(raw):
        fail("dataset review approval digest does not match its canonical payload")
    return DatasetReview(
        kind,
        dataset_id,
        strict_digest(raw["dataset_sha256"], "reviewed dataset digest"),
        cases,
        authors,
        custodian,
        reviewer,
        strict_digest(raw["review_payload_sha256"], "review payload digest"),
        review_payload_bytes,
        approval,
        hashlib.sha256(raw_bytes).hexdigest(),
        parse_assignment(raw),
    )
