from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from polis.evaluation.calibration_denominators import PreregisteredVerdict
from polis.evaluation.calibration_models import CalibrationCase
from polis.evaluation.calibration_roles import RoleAssignmentBinding

type DatasetKind = Literal["calibration", "holdout"]
type ApprovalVerdict = Literal["APPROVE", "BLOCK"]


@dataclass(frozen=True, slots=True)
class PerSourceCount:
    source: str
    category: str
    error_case_count: int
    correct_case_count: int
    preregistered_verdict: PreregisteredVerdict | None


@dataclass(frozen=True, slots=True)
class FrozenDatasetManifest:
    kind: DatasetKind
    dataset_id: str
    case_count: int
    error_case_count: int
    correct_case_count: int
    dataset_sha256: str
    dataset_size_bytes: int
    per_source_counts: tuple[PerSourceCount, ...]
    author_identities: tuple[str, ...]
    custodian_identity: str
    reviewer_identity: str
    review_manifest_sha256: str
    review_payload_sha256: str
    pii_scan_sha256: str
    assignment: RoleAssignmentBinding


@dataclass(frozen=True, slots=True)
class CaseReview:
    case_id: str
    author_identity: str
    case_payload_sha256: str


@dataclass(frozen=True, slots=True)
class DatasetReview:
    kind: DatasetKind
    dataset_id: str
    dataset_sha256: str
    case_reviews: tuple[CaseReview, ...]
    author_identities: tuple[str, ...]
    custodian_identity: str
    reviewer_identity: str
    review_payload_sha256: str
    review_payload_bytes: bytes
    approval_digest: str
    document_sha256: str
    assignment: RoleAssignmentBinding


@dataclass(frozen=True, slots=True)
class HoldoutV2Dataset:
    id: str
    cases: tuple[CalibrationCase, ...]
    sha256: str


@dataclass(frozen=True, slots=True)
class FiniteOverlapApproval:
    comment_id: int
    comment_url: str
    comment_author: str
    body_sha256: str


FINITE_OVERLAP_APPROVAL: Final = FiniteOverlapApproval(
    5234058206,
    "https://github.com/PSyron/polis/issues/269#issuecomment-5234058206",
    "PSyron",
    "e895bba130d5e13bedc02a49cff53eb43ec435e783ca539b7620c842f6a46b79",
)
PREREGISTERED_FINITE_EXACT_MATCHES: Final = 78


@dataclass(frozen=True, slots=True)
class FiniteOverlapHistogram:
    calibration_calibration: int
    calibration_public_quality: int
    calibration_public_v1: int
    calibration_public_conservative: int

    @property
    def total(self) -> int:
        return (
            self.calibration_calibration
            + self.calibration_public_quality
            + self.calibration_public_v1
            + self.calibration_public_conservative
        )


FINITE_OVERLAP_HISTOGRAM: Final = FiniteOverlapHistogram(18, 39, 21, 0)


@dataclass(frozen=True, slots=True)
class OverlapResult:
    unexpected_exact_collisions: int
    near_collisions: int
    comparison_count: int
    verdict: ApprovalVerdict
    preregistered_finite_exact_matches: int
    finite_match_histogram: FiniteOverlapHistogram
    approval: FiniteOverlapApproval

    @property
    def exact_collisions(self) -> int:
        return self.unexpected_exact_collisions


@dataclass(frozen=True, slots=True)
class PiiScanResult:
    email_count: int
    url_count: int
    phone_count: int
    national_id_count: int
    payment_card_count: int
    verdict: Literal["APPROVE"]


@dataclass(frozen=True, slots=True)
class FreezeInputs:
    calibration_manifest: FrozenDatasetManifest
    holdout_manifest: FrozenDatasetManifest
    calibration_review: DatasetReview
    holdout_review: DatasetReview
    overlap: OverlapResult
    overlap_custodian_identity: str
    freeze_verifier_a_identity: str
    freeze_verifier_b_identity: str


@dataclass(frozen=True, slots=True)
class FreezeVerification:
    role_identities: tuple[str, ...]
    verdict: Literal["APPROVE"]
