from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from polis.evaluation.calibration_json import fail, strict_integer, strict_string
from polis.evaluation.calibration_models import JsonObject

type DatasetKind = Literal["calibration", "holdout"]

VALIDATOR_IDENTITY: Final = "polis-269-validator-v1"
COMMENT_ID: Final = 5232770360
COMMENT_URL: Final = (
    "https://github.com/PSyron/polis/issues/269#issuecomment-5232770360"
)
COMMENT_AUTHOR: Final = "PSyron"
COMMENT_BODY_SHA256: Final = (
    "dd48d332a74178094b466bf838bb4adf49d8f51e9baecce7634f8fa6b2325d06"
)
DENOMINATOR_COMMENT_ID: Final = 5233051643
DENOMINATOR_COMMENT_URL: Final = (
    "https://github.com/PSyron/polis/issues/269#issuecomment-5233051643"
)
DENOMINATOR_COMMENT_AUTHOR: Final = "PSyron"
DENOMINATOR_BODY_SHA256: Final = (
    "63484eb3feabe5f5a6c0aabf86107657170162b58a5c4a7a188406aaa785bdc9"
)
ASSIGNMENT_FIELDS: Final = frozenset(
    {
        "validator_implementer_identity",
        "role_assignment_comment_id",
        "role_assignment_comment_url",
        "role_assignment_comment_author",
        "role_assignment_body_sha256",
        "denominator_approval_comment_id",
        "denominator_approval_comment_url",
        "denominator_approval_comment_author",
        "denominator_approval_body_sha256",
    }
)
CALIBRATION_AUTHORS: Final = tuple(
    f"polis-269-calibration-author-{letter}-v1" for letter in "abcd"
)
HOLDOUT_AUTHORS: Final = tuple(
    f"polis-269-holdout-author-{letter}-v1" for letter in "abcd"
)
ALL_ROLE_IDENTITIES: Final = (
    VALIDATOR_IDENTITY,
    "polis-269-calibration-custodian-v1",
    *CALIBRATION_AUTHORS,
    "polis-269-calibration-reviewer-v1",
    "polis-269-holdout-custodian-v1",
    *HOLDOUT_AUTHORS,
    "polis-269-holdout-reviewer-v1",
    "polis-269-overlap-custodian-v1",
    "polis-269-freeze-verifier-a-v1",
    "polis-269-freeze-verifier-b-v1",
)


@dataclass(frozen=True, slots=True)
class RoleAssignmentBinding:
    validator_implementer_identity: str
    role_assignment_comment_id: int
    role_assignment_comment_url: str
    role_assignment_comment_author: str
    role_assignment_body_sha256: str
    denominator_approval_comment_id: int
    denominator_approval_comment_url: str
    denominator_approval_comment_author: str
    denominator_approval_body_sha256: str


def expected_authors(kind: DatasetKind) -> tuple[str, ...]:
    return CALIBRATION_AUTHORS if kind == "calibration" else HOLDOUT_AUTHORS


def expected_custodian(kind: DatasetKind) -> str:
    return f"polis-269-{kind}-custodian-v1"


def expected_reviewer(kind: DatasetKind) -> str:
    return f"polis-269-{kind}-reviewer-v1"


def parse_assignment(raw: JsonObject) -> RoleAssignmentBinding:
    binding = RoleAssignmentBinding(
        strict_string(raw["validator_implementer_identity"], "validator identity"),
        strict_integer(raw["role_assignment_comment_id"], "assignment comment id"),
        strict_string(raw["role_assignment_comment_url"], "assignment comment URL"),
        strict_string(
            raw["role_assignment_comment_author"], "assignment comment author"
        ),
        strict_string(raw["role_assignment_body_sha256"], "assignment body digest"),
        strict_integer(
            raw["denominator_approval_comment_id"], "denominator approval comment id"
        ),
        strict_string(
            raw["denominator_approval_comment_url"], "denominator approval comment URL"
        ),
        strict_string(
            raw["denominator_approval_comment_author"],
            "denominator approval comment author",
        ),
        strict_string(
            raw["denominator_approval_body_sha256"],
            "denominator approval body digest",
        ),
    )
    expected = RoleAssignmentBinding(
        VALIDATOR_IDENTITY,
        COMMENT_ID,
        COMMENT_URL,
        COMMENT_AUTHOR,
        COMMENT_BODY_SHA256,
        DENOMINATOR_COMMENT_ID,
        DENOMINATOR_COMMENT_URL,
        DENOMINATOR_COMMENT_AUTHOR,
        DENOMINATOR_BODY_SHA256,
    )
    if binding != expected:
        fail("protocol binding does not match the approved issue comments")
    return binding
