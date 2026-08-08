from __future__ import annotations

import re
from dataclasses import dataclass

from polis.evaluation.holdout_json import integer_value, object_value, string_value
from polis.evaluation.holdout_models import (
    HoldoutConfig,
    HoldoutContractError,
    JsonObject,
)

_REVIEW_MANIFEST_SHA256 = (
    "f58f7c81ee46cb25968ca84e1f0ce6a842b14181c6151f041a4f30225aab3e4d"
)
_REVIEW_PAYLOAD_SHA256 = (
    "f5312a257d634f240301dbdfe47fad3b0897e4a4e7f11f10af3a51df0a777cd0"
)
_SHA256 = re.compile(r"[0-9a-f]{64}")
_ROOT_FIELDS = {
    "schema_id",
    "schema_version",
    "dataset_id",
    "dataset_schema",
    "sha256",
    "size_bytes",
    "mode",
    "case_count",
    "source_count",
    "expected_finding_count",
    "role_counts",
    "license",
    "provenance",
    "review",
    "plaintext_in_repository",
}
_REVIEW_FIELDS = {
    "reviewer_role",
    "verdict",
    "reviewed_case_count",
    "total_case_count",
    "reviewed_source_count",
    "review_manifest_sha256",
    "review_payload_sha256",
    "analyzer_executed",
    "protected_artifacts_used",
}


@dataclass(frozen=True, slots=True)
class DatasetReviewIdentity:
    reviewer_role: str
    reviewed_case_count: int
    total_case_count: int
    review_manifest_sha256: str
    review_payload_sha256: str


def parse_dataset_manifest(
    raw: JsonObject, config: HoldoutConfig
) -> DatasetReviewIdentity:
    root = object_value(raw, _ROOT_FIELDS, "dataset manifest")
    review = object_value(root["review"], _REVIEW_FIELDS, "independent review")
    identity = DatasetReviewIdentity(
        string_value(review["reviewer_role"], "independent review reviewer_role"),
        integer_value(
            review["reviewed_case_count"], "independent review reviewed_case_count"
        ),
        integer_value(
            review["total_case_count"], "independent review total_case_count"
        ),
        string_value(
            review["review_manifest_sha256"], "independent review manifest digest"
        ),
        string_value(
            review["review_payload_sha256"], "independent review payload digest"
        ),
    )
    root_identity = (
        string_value(root["schema_id"], "dataset manifest schema_id"),
        integer_value(root["schema_version"], "dataset manifest schema_version"),
        string_value(root["dataset_id"], "dataset manifest dataset_id"),
        string_value(root["dataset_schema"], "dataset manifest dataset_schema"),
        string_value(root["sha256"], "dataset manifest sha256"),
        integer_value(root["size_bytes"], "dataset manifest size_bytes"),
        string_value(root["mode"], "dataset manifest mode"),
        integer_value(root["case_count"], "dataset manifest case_count"),
        integer_value(root["source_count"], "dataset manifest source_count"),
        string_value(root["license"], "dataset manifest license"),
        string_value(root["provenance"], "dataset manifest provenance"),
        root["plaintext_in_repository"],
    )
    expected_root = (
        "polis.a-b-one-shot.dataset-manifest",
        1,
        config.experiment_id,
        "polis.a-b-one-shot.dataset/1",
        config.dataset.sha256,
        config.dataset.size_bytes,
        config.dataset.mode,
        config.dataset.case_count,
        config.dataset.source_count,
        config.dataset.license,
        config.dataset.provenance,
        False,
    )
    role_counts = object_value(
        root["role_counts"], {"error", "correct", "abstain", "conflict"}, "role counts"
    )
    role_identity = {
        name: integer_value(role_counts[name], f"role count {name}")
        for name in ("error", "correct", "abstain", "conflict")
    }
    if type(root["plaintext_in_repository"]) is not bool:
        raise _review_error()
    if (
        root_identity != expected_root
        or integer_value(
            root["expected_finding_count"], "dataset manifest expected finding count"
        )
        != 19
    ):
        raise _review_error()
    if role_identity != {"error": 14, "correct": 27, "abstain": 10, "conflict": 1}:
        raise _review_error()
    if (
        identity.reviewer_role != "independent-dataset-reviewer"
        or string_value(review["verdict"], "independent review verdict") != "APPROVE"
        or identity.reviewed_case_count != 52
        or identity.total_case_count != 52
        or integer_value(
            review["reviewed_source_count"], "independent review source count"
        )
        != 20
        or review["analyzer_executed"] is not False
        or review["protected_artifacts_used"] is not False
        or identity.review_manifest_sha256 != _REVIEW_MANIFEST_SHA256
        or identity.review_payload_sha256 != _REVIEW_PAYLOAD_SHA256
        or _SHA256.fullmatch(identity.review_manifest_sha256) is None
        or _SHA256.fullmatch(identity.review_payload_sha256) is None
    ):
        raise _review_error()
    return identity


def _review_error() -> HoldoutContractError:
    return HoldoutContractError("independent review manifest does not match approval")
