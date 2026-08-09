from __future__ import annotations

import hashlib
import json

from tests.denominator_test_constants import (
    DatasetKind,
    expected_counts,
    expected_verdict,
)

from polis.evaluation.calibration_models import JsonObject, JsonValue
from polis.evaluation.calibration_sources import SOURCE_ROWS, SOURCE_SNAPSHOT_SHA256

ASSIGNMENT = {
    "validator_implementer_identity": "polis-269-validator-v1",
    "role_assignment_comment_id": 5232770360,
    "role_assignment_comment_url": (
        "https://github.com/PSyron/polis/issues/269#issuecomment-5232770360"
    ),
    "role_assignment_comment_author": "PSyron",
    "role_assignment_body_sha256": (
        "dd48d332a74178094b466bf838bb4adf49d8f51e9baecce7634f8fa6b2325d06"
    ),
    "denominator_approval_comment_id": 5233051643,
    "denominator_approval_comment_url": (
        "https://github.com/PSyron/polis/issues/269#issuecomment-5233051643"
    ),
    "denominator_approval_comment_author": "PSyron",
    "denominator_approval_body_sha256": (
        "63484eb3feabe5f5a6c0aabf86107657170162b58a5c4a7a188406aaa785bdc9"
    ),
}
CAL_AUTHORS = [f"polis-269-calibration-author-{letter}-v1" for letter in "abcd"]
HOLD_AUTHORS = [f"polis-269-holdout-author-{letter}-v1" for letter in "abcd"]


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


def source_identity_json(index: int) -> JsonObject:
    row = SOURCE_ROWS[index]
    return {
        "source": row.source,
        "category": row.category,
        "operation": row.operation,
        "behavior_version": row.behavior_version,
        "source_policy_version": row.source_policy_version,
        "emitted_confidence": row.emitted_confidence,
        "current_policy_state": row.current_policy_state,
    }


def dataset_document(kind: DatasetKind) -> JsonObject:
    prefix = "cal-v2" if kind == "calibration" else "hold-v2"
    dataset_id = (
        "polis-a-b-calibration-v2-v1"
        if kind == "calibration"
        else "polis-a-b-holdout-v2-v1"
    )
    cases: list[JsonValue] = []
    for source_index, row in enumerate(SOURCE_ROWS):
        per_role = expected_counts(kind, row.source)
        for role, count in zip(("error", "correct"), per_role, strict=True):
            for case_index in range(count):
                text = f"Żółty🙂 przykład {source_index}-{role}-{case_index}."
                findings: list[JsonValue] = []
                if role == "error":
                    findings.append(
                        {
                            "source": row.source,
                            "category": row.category,
                            "start": 0,
                            "end": 5,
                            "original": "Żółty",
                            "suggestion": "Zielony",
                        }
                    )
                cases.append(
                    {
                        "id": f"{prefix}-{source_index:02d}-{role}-{case_index:02d}",
                        "role": role,
                        "primary_source_identity": row.source,
                        "text": text,
                        "expected_findings": findings,
                    }
                )
    schema = (
        "polis.a-b-calibration.dataset"
        if kind == "calibration"
        else "polis.a-b-holdout-v2.dataset"
    )
    return {
        "schema_id": schema,
        "schema_version": 1,
        "dataset_id": dataset_id,
        "language": "pl",
        "cases": cases,
    }


def dataset_manifest(kind: DatasetKind, dataset_bytes: bytes) -> JsonObject:
    calibration = kind == "calibration"
    dataset_id = (
        "polis-a-b-calibration-v2-v1" if calibration else "polis-a-b-holdout-v2-v1"
    )
    author_ids = CAL_AUTHORS if calibration else HOLD_AUTHORS
    stem = "calibration" if calibration else "holdout"
    kind = "calibration" if calibration else "holdout"
    return {
        "schema_id": (
            "polis.a-b-calibration.dataset-manifest"
            if calibration
            else "polis.a-b-holdout-v2.dataset-manifest"
        ),
        "schema_version": 2,
        "experiment_id": "polis-a-b-qualification-v2-v1",
        "dataset_id": dataset_id,
        "language": "pl",
        "license": "CC0-1.0",
        "provenance": "independently-authored",
        "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
        "source_rows": [source_identity_json(index) for index in range(20)],
        "case_count": 1073 if calibration else 530,
        "error_case_count": 273 if calibration else 130,
        "correct_case_count": 800 if calibration else 400,
        "per_source_counts": [
            {
                "source_identity": source_identity_json(index),
                "error_case_count": expected_counts(kind, row.source)[0],
                "correct_case_count": expected_counts(kind, row.source)[1],
                "preregistered_verdict": expected_verdict(row.source),
            }
            for index, row in enumerate(SOURCE_ROWS)
        ],
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "dataset_size_bytes": len(dataset_bytes),
        "dataset_mode": "0600",
        "author_role": f"{stem}-author",
        "author_identities": author_ids,
        "custodian_role": f"{stem}-custodian",
        "custodian_identity": f"polis-269-{stem}-custodian-v1",
        "reviewer_role": f"{stem}-reviewer",
        "reviewer_identity": f"polis-269-{stem}-reviewer-v1",
        "review_status": "APPROVE",
        **ASSIGNMENT,
        "reviewed_case_count": 1073 if calibration else 530,
        "review_manifest_sha256": "1" * 64,
        "review_payload_sha256": "2" * 64,
        "pii_status": "absent",
        "pii_scan_sha256": "3" * 64,
        "overlap_policy_id": "keyed-unicode-fivegram-jaccard-v1",
    }


def dataset_review(kind: DatasetKind, dataset_bytes: bytes) -> JsonObject:
    calibration = kind == "calibration"
    document: JsonValue = json.loads(dataset_bytes)
    assert isinstance(document, dict)
    cases = document["cases"]
    assert isinstance(cases, list)
    author_ids = CAL_AUTHORS if calibration else HOLD_AUTHORS
    stem = "calibration" if calibration else "holdout"
    review: JsonObject = {
        "schema_id": "polis.a-b-qualification-v2.dataset-review",
        "schema_version": 1,
        "experiment_id": "polis-a-b-qualification-v2-v1",
        "dataset_id": document["dataset_id"],
        "dataset_sha256": hashlib.sha256(dataset_bytes).hexdigest(),
        "source_snapshot_sha256": SOURCE_SNAPSHOT_SHA256,
        "checklist_version": "independent-dataset-review-v1",
        "author_role": f"{stem}-author",
        "author_identities": author_ids,
        "custodian_role": f"{stem}-custodian",
        "custodian_identity": f"polis-269-{stem}-custodian-v1",
        "reviewer_role": f"{stem}-reviewer",
        "reviewer_identity": f"polis-269-{stem}-reviewer-v1",
        **ASSIGNMENT,
        "independence_status": "APPROVE",
        "review_status": "APPROVE",
        "reviewed_case_count": len(cases),
        "case_reviews": [
            {
                "case_id": case["id"] if isinstance(case, dict) else "",
                "author_identity": author_ids[index % 4],
                "case_payload_sha256": (
                    hashlib.sha256(canonical_bytes(case)).hexdigest()
                    if isinstance(case, dict)
                    else ""
                ),
                "license": "CC0-1.0",
                "provenance": "independently-authored",
                "role_semantics": "APPROVE",
                "linguistic_validity": "APPROVE",
                "minimal_correction": "APPROVE",
                "span_validity": "APPROVE",
                "source_binding": "APPROVE",
                "pii_status": "absent",
                "review_status": "APPROVE",
            }
            for index, case in enumerate(cases)
        ],
        "review_payload_sha256": "",
        "approval_digest": "",
    }
    review["review_payload_sha256"] = hashlib.sha256(
        review_payload_bytes(review)
    ).hexdigest()
    recompute_review_approval(review)
    return review


def review_payload_bytes(review: JsonObject) -> bytes:
    return canonical_bytes(review["case_reviews"])


def recompute_review_approval(review: JsonObject) -> None:
    payload: JsonObject = {}
    for key, value in review.items():
        if key != "approval_digest":
            payload[key] = value
    review["approval_digest"] = hashlib.sha256(canonical_bytes(payload)).hexdigest()
