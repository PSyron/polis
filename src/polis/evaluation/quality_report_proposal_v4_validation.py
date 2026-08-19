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
from polis.evaluation.quality_report_proposal_v4 import (
    _QUALITY_GATE_METRICS,
    expected_v4_gate_ids,
)
from polis.evaluation.quality_v4_measurement import source_snapshot_sha256

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
        if (
            set(decision)
            != {"status", "enforced", "approved_by", "approved_at", "rationale"}
            or decision.get("status") != "approved"
            or decision.get("enforced") is not True
            or not all(
                isinstance(decision.get(key), str) and decision[key]
                for key in ("approved_by", "approved_at", "rationale")
            )
        ):
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
    if proposal.wheel_filename != Path(proposal.wheel_path).name:
        raise QualityReportError("v4 proposal wheel filename/path mismatch")
    performance_artifacts: dict[str, dict[str, object]] = {}
    for profile, values in (
        ("default", proposal.default),
        ("morphology", proposal.morphology),
    ):
        for role, binding in (
            ("reference", values.performance_baseline),
            ("current", values.performance_result),
        ):
            performance_artifacts[f"{profile}:{role}"] = load_runtime_performance_v2(
                Path(binding.path),
                binding=binding,
                profile=profile,
                expected_dataset_id=default.dataset_id,
                expected_dataset_sha256=proposal.dataset_sha256,
                expected_manifest_sha256=proposal.manifest_sha256,
                expected_source_sha=proposal.source_git_sha,
                expected_source_snapshot_sha256=source_snapshot_sha256(
                    default.source_snapshot or ()
                ),
                expected_wheel_sha256=proposal.wheel_sha256,
                expected_wheel_filename=proposal.wheel_filename,
                expected_role=role,
            )
    _validate_gate_contract(proposal, default, morphology, performance_artifacts)


def _check_controls(report: Any) -> None:
    controls = report.diagnostics["controls"]
    if any(
        controls[name]["violations"] != 0 or controls[name]["predicted_findings"] != 0
        for name in ("conflict", "abstention")
    ):
        raise QualityReportError(
            "v4 proposal cannot use a baseline with control violations"
        )


def _validate_gate_contract(
    proposal: ThresholdProposalV4,
    default: Any,
    morphology: Any,
    performance_artifacts: dict[str, dict[str, object]],
) -> None:
    expected = set(expected_v4_gate_ids())
    for report, values in (
        (default, proposal.default),
        (morphology, proposal.morphology),
    ):
        actual = [f"{gate.scope}:{gate.metric}" for gate in values.gates]
        if set(actual) != expected or len(actual) != len(set(actual)):
            raise QualityReportError("v4 proposal gate coverage mismatch")
        _validate_gate_values(
            report,
            values,
            performance_artifacts[f"{report.run_identity.profile.id.value}:reference"],
        )
        if not values.gates:
            raise QualityReportError("v4 proposal gate contract is empty")
        for gate in values.gates:
            if gate.effective_schema_version != proposal.effective_schema_version:
                raise QualityReportError("v4 proposal gate schema version mismatch")
            if proposal.status == "pending_maintainer_approval" and (
                gate.maintainer_decision is not None
            ):
                raise QualityReportError(
                    "v4 comparison requires an explicitly approved and enforced "
                    "proposal; pending proposal gate must remain undecided"
                )
            if proposal.status == "approved" and (
                gate.maintainer_decision is None
                or set(gate.maintainer_decision)
                != {"status", "decided_by", "decided_at", "rationale"}
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


def _validate_gate_values(
    report: Any,
    values: ProfileThresholdProposalV4,
    performance_artifact: dict[str, object],
) -> None:
    diagnostics = report.diagnostics
    for gate in values.gates:
        baseline: object
        threshold: object
        if gate.scope.startswith("control:"):
            name = gate.scope.split(":")[1]
            baseline = diagnostics["controls"][name]["violations"]
            threshold = 0
        elif gate.scope in {"source", "source:exact-ordered-59-parity"}:
            baseline = _source_gate_baseline(report)
            threshold = True
        elif gate.scope in {"performance", "performance:performance"}:
            baseline, threshold = _performance_gate_values(
                values, gate.metric, performance_artifact
            )
        elif gate.scope.startswith("performance:"):
            baseline, threshold = _performance_gate_values(
                values, gate.metric, performance_artifact
            )
        else:
            raw: Any = diagnostics["aggregate"]
            if gate.scope.startswith("category:"):
                raw = diagnostics["category"][gate.scope.split(":")[1]]
            elif gate.scope.startswith("stratum:"):
                _, category, shape = gate.scope.split(":")
                raw = diagnostics["shape_strata"][category][shape]
            metric = next(
                (item for item in _QUALITY_GATE_METRICS if item[0] == gate.metric), None
            )
            if metric is None:
                raise QualityReportError("v4 proposal gate metric is unknown")
            baseline = raw[metric[1]]
            threshold = getattr(values.quality, metric[2])
            if gate.scope.startswith("category:"):
                threshold = getattr(
                    values.category_quality[gate.scope.split(":")[1]], metric[2]
                )
            elif gate.scope.startswith("stratum:"):
                _, category, shape = gate.scope.split(":")
                threshold = getattr(values.stratum_quality[category][shape], metric[2])
        if gate.measured_baseline != baseline or gate.proposed_threshold != threshold:
            raise QualityReportError(
                "v4 proposal gate values do not bind to measurements: "
                f"{gate.scope}:{gate.metric} "
                f"{gate.measured_baseline!r}/{baseline!r} "
                f"{gate.proposed_threshold!r}/{threshold!r}"
            )


def _source_gate_baseline(report: Any) -> bool:
    rows = report.diagnostics["source"]
    return isinstance(rows, list) and bool(rows)


def _performance_gate_values(
    values: ProfileThresholdProposalV4,
    metric: str,
    artifact: dict[str, object],
) -> tuple[object, object]:
    performance = values.performance
    raw_performance = artifact.get("performance")
    raw_rss = artifact.get("rss")
    if not isinstance(raw_performance, dict) or not isinstance(raw_rss, dict):
        raise QualityReportError("v4 performance artifact metrics are malformed")
    latency = raw_performance.get("latency_ns")
    throughput = raw_performance.get("throughput")
    if not isinstance(latency, dict) or not isinstance(throughput, dict):
        raise QualityReportError("v4 performance artifact metrics are malformed")
    if metric == "maximum_p95_latency_ns":
        return latency["p95"], performance.maximum_p95_latency_ns
    if metric == "minimum_throughput_cases_per_second":
        return throughput[
            "cases_per_second"
        ], performance.minimum_throughput_cases_per_second
    if metric == "maximum_worker_incremental_peak_rss_bytes":
        return (
            raw_rss["worker_measured_incremental_peak_rss_bytes"],
            performance.maximum_worker_incremental_peak_rss_bytes,
        )
    if metric == "reproducibility":
        reproducibility = artifact.get("reproducibility")
        if not isinstance(reproducibility, dict):
            raise QualityReportError("v4 performance reproducibility is malformed")
        hashes = reproducibility.get("repetition_hashes")
        if isinstance(hashes, list):
            if not hashes:
                raise QualityReportError(
                    "v4 performance repetition hashes are malformed"
                )
            return len(set(hashes)) == 1, True
        stable = reproducibility.get("stable_repetitions")
        measured = reproducibility.get("measured_repetitions")
        return stable == measured, True
    raise QualityReportError("v4 proposal performance gate metric is unknown")


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
