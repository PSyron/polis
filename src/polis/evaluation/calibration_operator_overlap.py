from __future__ import annotations

from polis.evaluation.calibration_freeze_models import (
    FINITE_OVERLAP_APPROVAL,
    FINITE_OVERLAP_HISTOGRAM,
    PREREGISTERED_FINITE_EXACT_MATCHES,
    FiniteOverlapApproval,
    FiniteOverlapHistogram,
    OverlapResult,
)
from polis.evaluation.calibration_json import (
    document,
    exact_object,
    fail,
    strict_integer,
    strict_string,
)
from polis.evaluation.calibration_models import JsonValue

_RESULT_FIELDS = frozenset(
    {
        "schema_id",
        "schema_version",
        "status",
        "calibration_sha256",
        "holdout_sha256",
        "representation_count",
        "comparison_count",
        "preregistered_finite_exact_matches",
        "finite_match_histogram",
        "unexpected_exact_collisions",
        "near_collisions",
        "finite_overlap_approval",
        "output_mode",
        "verdict",
    }
)
_HISTOGRAM_FIELDS = frozenset(
    {
        "calibration_calibration",
        "calibration_public_quality",
        "calibration_public_v1",
        "calibration_public_conservative",
    }
)
_APPROVAL_FIELDS = frozenset(
    {"comment_id", "comment_url", "comment_author", "body_sha256"}
)


def _histogram(value: JsonValue) -> FiniteOverlapHistogram:
    raw = exact_object(value, _HISTOGRAM_FIELDS, "finite match histogram")
    return FiniteOverlapHistogram(
        strict_integer(raw["calibration_calibration"], "calibration matches"),
        strict_integer(raw["calibration_public_quality"], "quality matches"),
        strict_integer(raw["calibration_public_v1"], "v1 matches"),
        strict_integer(raw["calibration_public_conservative"], "fixture matches"),
    )


def _approval(value: JsonValue) -> FiniteOverlapApproval:
    raw = exact_object(value, _APPROVAL_FIELDS, "finite overlap approval")
    return FiniteOverlapApproval(
        strict_integer(raw["comment_id"], "approval comment id"),
        strict_string(raw["comment_url"], "approval comment URL"),
        strict_string(raw["comment_author"], "approval comment author"),
        strict_string(raw["body_sha256"], "approval body digest"),
    )


def parse_overlap(raw: bytes) -> OverlapResult:
    value = exact_object(
        document(raw, "overlap oracle"), _RESULT_FIELDS, "overlap oracle"
    )
    histogram = _histogram(value["finite_match_histogram"])
    approval = _approval(value["finite_overlap_approval"])
    finite_exact = strict_integer(
        value["preregistered_finite_exact_matches"], "preregistered finite matches"
    )
    unexpected = strict_integer(
        value["unexpected_exact_collisions"], "unexpected exact collisions"
    )
    near = strict_integer(value["near_collisions"], "near collisions")
    if (
        value["schema_id"] != "polis.a-b-qualification-v2.overlap-oracle"
        or value["schema_version"] != 1
        or value["status"] != "APPROVE"
        or value["output_mode"] != "0600"
        or value["verdict"] != "APPROVE"
        or finite_exact != PREREGISTERED_FINITE_EXACT_MATCHES
        or histogram != FINITE_OVERLAP_HISTOGRAM
        or unexpected != 0
        or near != 0
        or approval != FINITE_OVERLAP_APPROVAL
    ):
        fail("overlap oracle identity is invalid")
    return OverlapResult(
        unexpected,
        near,
        strict_integer(value["comparison_count"], "comparison count"),
        "APPROVE",
        finite_exact,
        histogram,
        approval,
    )
