"""Fail-closed binding and gate checks for v4 threshold proposals."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from polis.evaluation.quality_protocol import InstallationProfile
from polis.evaluation.quality_report_baseline import (
    baseline_file_sha256,
    load_quality_report,
)
from polis.evaluation.quality_report_models import (
    ProfileThresholdProposalV4,
    QualityReportError,
    ThresholdProposalV4,
)

_CATEGORIES = ("agreement", "inflection", "punctuation", "spelling", "syntax")
_SHAPES = (
    "simple-local",
    "sentence-internal",
    "multi-sentence",
    "repeated-occurrence",
    "unicode-and-case",
    "quotation-or-literal",
    "conflict-or-abstention",
)


def validate_threshold_proposal_v4(
    proposal: ThresholdProposalV4,
    default_baseline_path: Path,
    morphology_baseline_path: Path | None,
) -> None:
    if morphology_baseline_path is None:
        raise QualityReportError("v4 threshold proposal requires both baselines")
    if proposal.status == "pending_maintainer_approval":
        if proposal.enforced or proposal.decision is not None:
            raise QualityReportError(
                "pending v4 threshold proposal must be unenforced and undecided"
            )
    elif proposal.status == "approved":
        decision = proposal.decision
        if not proposal.enforced or decision is None:
            raise QualityReportError(
                "approved v4 threshold proposal requires enforced decision metadata"
            )
        if decision.get("status") != "approved" or decision.get("enforced") is not True:
            raise QualityReportError("v4 approval decision is inconsistent")
    else:
        raise QualityReportError(
            "threshold proposal status must be pending_maintainer_approval or approved"
        )
    default = load_quality_report(default_baseline_path)
    morphology = load_quality_report(morphology_baseline_path)
    for report, path, profile, values in (
        (default, default_baseline_path, InstallationProfile.DEFAULT, proposal.default),
        (
            morphology,
            morphology_baseline_path,
            InstallationProfile.MORPHOLOGY,
            proposal.morphology,
        ),
    ):
        _bind_report(report, path, profile, values, proposal)
    if (
        default.dataset_sha256 != morphology.dataset_sha256
        or default.dataset_sha256 != proposal.dataset_sha256
    ):
        raise QualityReportError("v4 proposal dataset identity mismatch")
    if (
        default.run_identity.manifest_sha256 != morphology.run_identity.manifest_sha256
        or default.run_identity.manifest_sha256 != proposal.manifest_sha256
    ):
        raise QualityReportError("v4 proposal manifest identity mismatch")
    if (
        default.run_identity.source_sha != proposal.source_git_sha
        or morphology.run_identity.source_sha != proposal.source_git_sha
    ):
        raise QualityReportError("v4 proposal source SHA mismatch")
    if (
        default.run_identity.source_snapshot != proposal.source_snapshot
        or morphology.run_identity.source_snapshot != proposal.source_snapshot
    ):
        raise QualityReportError("v4 proposal source snapshot mismatch")
    if (
        default.artifact_sha256 != proposal.wheel_sha256
        or morphology.artifact_sha256 != proposal.wheel_sha256
    ):
        raise QualityReportError("v4 proposal wheel identity mismatch")


def _bind_report(
    report: Any,
    path: Path,
    profile: InstallationProfile,
    proposed: ProfileThresholdProposalV4,
    proposal: ThresholdProposalV4,
) -> None:
    if proposed.baseline_path != str(path):
        raise QualityReportError("v4 threshold proposal baseline_path mismatch")
    if baseline_file_sha256(path) != proposed.baseline_sha256:
        raise QualityReportError(f"v4 {profile.value} baseline byte identity mismatch")
    if report.run_identity.artifact_sha256 != proposal.wheel_sha256:
        raise QualityReportError("v4 proposal wheel identity mismatch")
    if (
        report.run_identity.profile is None
        or report.run_identity.profile.id is not profile
    ):
        raise QualityReportError(f"v4 {profile.value} profile identity mismatch")
    if report.run_identity.dataset_schema_version != 4 or report.diagnostics is None:
        raise QualityReportError("v4 proposal requires v4 diagnostics")
    if report.run_identity.artifact_sha256 == "0" * 64:
        raise QualityReportError("v4 baseline artifact hash must not be a placeholder")
    if report.run_identity.source_snapshot != proposal.source_snapshot:
        raise QualityReportError("v4 source snapshot mismatch")
    _check_floors(report.diagnostics["aggregate"], proposed.quality, "aggregate")
    category = report.diagnostics["category"]
    strata = report.diagnostics["shape_strata"]
    if not isinstance(category, dict) or not isinstance(strata, dict):
        raise QualityReportError("v4 diagnostics shape mismatch")
    for name in _CATEGORIES:
        _check_floors(
            category[name], proposed.category_quality[name], f"category:{name}"
        )
        for shape in _SHAPES:
            _check_floors(
                strata[name][shape],
                proposed.stratum_quality[name][shape],
                f"stratum:{name}:{shape}",
            )


def _check_floors(raw: object, floors: Any, scope: str) -> None:
    if not isinstance(raw, dict):
        raise QualityReportError(f"v4 {scope} counts are malformed")
    for key, minimum in (
        ("exact_edit_precision", floors.minimum_precision),
        ("exact_edit_recall", floors.minimum_recall),
        ("exact_edit_f1", floors.minimum_f1),
        ("span_accuracy", floors.minimum_exact_span_accuracy),
        ("suggestion_accuracy", floors.minimum_exact_correction_accuracy),
    ):
        actual = raw.get(key)
        if minimum is not None and (
            not isinstance(actual, int | float) or actual < minimum
        ):
            raise QualityReportError(f"v4 {scope} floor failed: {key}")
    actual_far = raw.get("correct_sentence_false_alarm_rate")
    if floors.maximum_false_alarm_rate is not None and (
        not isinstance(actual_far, int | float)
        or actual_far > floors.maximum_false_alarm_rate
    ):
        raise QualityReportError(f"v4 {scope} ceiling failed: false_alarm_rate")
