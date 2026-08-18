"""Parsing and pending-policy validation for quality threshold proposals."""

from __future__ import annotations

from pathlib import Path
from typing import Final, assert_never

from polis.evaluation.quality_report_baseline import (
    baseline_file_sha256,
    load_quality_report,
)
from polis.evaluation.quality_report_models import (
    JsonObject,
    QualityReportError,
    ThresholdProposal,
    ThresholdProposalArtifact,
    ThresholdProposalV2,
    ThresholdProposalV3,
    ThresholdProposalV4,
)
from polis.evaluation.quality_report_proposal_v2 import parse_threshold_proposal_v2
from polis.evaluation.quality_report_proposal_v2_validation import (
    validate_threshold_proposal_v2,
)
from polis.evaluation.quality_report_proposal_v3 import parse_threshold_proposal_v3
from polis.evaluation.quality_report_proposal_v3_validation import (
    validate_threshold_proposal_v3,
)
from polis.evaluation.quality_report_proposal_v4 import parse_threshold_proposal_v4
from polis.evaluation.quality_report_proposal_v4_validation import (
    validate_threshold_proposal_v4,
)
from polis.evaluation.quality_report_validation import (
    _boolean,
    _exact,
    _integer,
    _load_json_object,
    _nested,
    _ratio,
    _schema,
    _sha,
    _string,
)

_PROPOSAL_SCHEMA_ID: Final = "polis.quality-threshold-proposal"
_PENDING_STATUS: Final = "pending_maintainer_approval"


def load_threshold_proposal(path: Path) -> ThresholdProposalArtifact:
    """Parse a threshold proposal without granting approval or enforcement."""

    root = _load_json_object(path, "threshold proposal")
    schema_version = _integer(root, "schema_version", "threshold proposal")
    match schema_version:
        case 1:
            return _load_threshold_proposal_v1(root)
        case 2:
            if _string(root, "schema_id", "threshold proposal") != _PROPOSAL_SCHEMA_ID:
                raise QualityReportError("threshold proposal schema_id mismatch")
            return parse_threshold_proposal_v2(root)
        case 3:
            if _string(root, "schema_id", "threshold proposal") != _PROPOSAL_SCHEMA_ID:
                raise QualityReportError("threshold proposal schema_id mismatch")
            return parse_threshold_proposal_v3(root)
        case 4:
            if _string(root, "schema_id", "threshold proposal") != _PROPOSAL_SCHEMA_ID:
                raise QualityReportError("threshold proposal schema_id mismatch")
            return parse_threshold_proposal_v4(root)
        case _:
            raise QualityReportError(
                "threshold proposal schema_version must be 1, 2, 3, or 4"
            )


def _load_threshold_proposal_v1(root: JsonObject) -> ThresholdProposal:
    _exact(
        root,
        {
            "schema_id",
            "schema_version",
            "baseline_path",
            "baseline_sha256",
            "dataset_sha256",
            "proposed_thresholds",
            "status",
            "enforced",
        },
        "threshold proposal",
    )
    _schema(root, _PROPOSAL_SCHEMA_ID, "threshold proposal")
    values = _nested(
        root,
        "proposed_thresholds",
        {
            "minimum_precision",
            "minimum_recall",
            "minimum_f1",
            "minimum_span_accuracy",
            "minimum_correction_accuracy",
            "maximum_false_alarm_rate",
        },
    )
    return ThresholdProposal(
        baseline_path=_string(root, "baseline_path", "threshold proposal"),
        baseline_sha256=_sha(root, "baseline_sha256", "threshold proposal"),
        dataset_sha256=_sha(root, "dataset_sha256", "threshold proposal"),
        minimum_precision=_ratio(values, "minimum_precision"),
        minimum_recall=_ratio(values, "minimum_recall"),
        minimum_f1=_ratio(values, "minimum_f1"),
        minimum_span_accuracy=_ratio(values, "minimum_span_accuracy"),
        minimum_correction_accuracy=_ratio(values, "minimum_correction_accuracy"),
        maximum_false_alarm_rate=_ratio(values, "maximum_false_alarm_rate"),
        status=_string(root, "status", "threshold proposal"),
        enforced=_boolean(root, "enforced", "threshold proposal"),
    )


def validate_threshold_proposal(
    proposal: ThresholdProposalArtifact,
    *,
    baseline_path: Path,
    morphology_baseline_path: Path | None = None,
) -> None:
    """Require exact baseline binding, measured values, and pending policy."""

    match proposal:
        case ThresholdProposal():
            if morphology_baseline_path is not None:
                raise QualityReportError("v1 threshold proposal accepts one baseline")
            _validate_threshold_proposal_v1(proposal, baseline_path)
        case ThresholdProposalV2():
            validate_threshold_proposal_v2(
                proposal, baseline_path, morphology_baseline_path
            )
        case ThresholdProposalV3():
            validate_threshold_proposal_v3(
                proposal, baseline_path, morphology_baseline_path
            )
        case ThresholdProposalV4():
            validate_threshold_proposal_v4(
                proposal, baseline_path, morphology_baseline_path
            )
        case unreachable:
            assert_never(unreachable)


def _validate_threshold_proposal_v1(
    proposal: ThresholdProposal, baseline_path: Path
) -> None:

    if proposal.baseline_path != str(baseline_path):
        raise QualityReportError("threshold proposal baseline_path mismatch")
    if proposal.baseline_sha256 != baseline_file_sha256(baseline_path):
        raise QualityReportError("threshold proposal baseline_sha256 mismatch")
    baseline = load_quality_report(baseline_path)
    if proposal.dataset_sha256 != baseline.dataset_sha256:
        raise QualityReportError("threshold proposal dataset_sha256 mismatch")
    if proposal.status != _PENDING_STATUS:
        raise QualityReportError(
            "threshold proposal status must be pending_maintainer_approval"
        )
    if proposal.enforced:
        raise QualityReportError("threshold proposal must not be enforced")
    comparisons = (
        ("minimum_precision", proposal.minimum_precision, baseline.quality_precision),
        ("minimum_recall", proposal.minimum_recall, baseline.quality_recall),
        ("minimum_f1", proposal.minimum_f1, baseline.quality_f1),
        (
            "minimum_span_accuracy",
            proposal.minimum_span_accuracy,
            baseline.quality_span_accuracy,
        ),
        (
            "minimum_correction_accuracy",
            proposal.minimum_correction_accuracy,
            baseline.quality_correction_accuracy,
        ),
        (
            "maximum_false_alarm_rate",
            proposal.maximum_false_alarm_rate,
            baseline.quality_false_alarm_rate,
        ),
    )
    for name, proposed, measured in comparisons:
        if proposed != measured:
            raise QualityReportError(f"threshold proposal {name} mismatch")
