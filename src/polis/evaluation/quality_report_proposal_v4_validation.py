"""Fail-closed binding and gate checks for v4 threshold proposals."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from polis.evaluation.quality_performance_artifact import load_runtime_performance_v2
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
    _validate_gate_contract(proposal)
    for profile, values in (
        ("default", proposal.default),
        ("morphology", proposal.morphology),
    ):
        for binding in (values.performance_baseline, values.performance_result):
            load_runtime_performance_v2(
                Path(binding.path),
                binding=binding,
                profile=profile,
                expected_dataset_id=default.dataset_id,
                expected_dataset_sha256=proposal.dataset_sha256,
                expected_manifest_sha256=proposal.manifest_sha256,
                expected_source_sha=proposal.source_git_sha,
                expected_wheel_sha256=proposal.wheel_sha256,
            )


def _check_controls(report: Any) -> None:
    controls = report.diagnostics["controls"]
    if any(controls[name]["violations"] != 0 for name in ("conflict", "abstention")):
        raise QualityReportError(
            "v4 proposal cannot use a baseline with control violations"
        )


def _validate_gate_contract(proposal: ThresholdProposalV4) -> None:
    for values in (proposal.default, proposal.morphology):
        if not values.gates:
            raise QualityReportError("v4 proposal gate contract is empty")
        for gate in values.gates:
            if gate.effective_schema_version != proposal.effective_schema_version:
                raise QualityReportError("v4 proposal gate schema version mismatch")
            if proposal.status == "approved" and (
                gate.maintainer_decision is None
                or gate.maintainer_decision.get("status") != "approved"
                or not gate.maintainer_decision.get("decided_by")
                or not gate.maintainer_decision.get("decided_at")
                or not gate.maintainer_decision.get("rationale")
            ):
                raise QualityReportError(
                    "approved v4 proposal gate lacks complete decision metadata"
                )
            if not gate.rationale or not gate.regression_risk:
                raise QualityReportError("v4 proposal gate rationale is incomplete")


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
    _check_controls(report)
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
