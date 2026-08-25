"""Executable fail-closed comparison for v4 quality artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from polis.evaluation.quality_performance_artifact import load_runtime_performance_v2
from polis.evaluation.quality_report_baseline import (
    baseline_file_sha256,
    load_quality_report,
)
from polis.evaluation.quality_report_models import (
    ProfileThresholdProposalV4,
    QualityReport,
    QualityReportError,
    ThresholdProposalV4,
)
from polis.evaluation.quality_report_proposal import (
    load_threshold_proposal,
    validate_threshold_proposal,
)
from polis.evaluation.quality_report_result import load_quality_result
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
_PROTOCOL_SHA256 = "runtime-performance-protocol-v2"
_WORKER_SHA256 = "runtime-performance-worker-v2"
_COUNT_FIELDS = (
    "expected_findings",
    "predicted_findings",
    "true_positives",
    "false_positives",
    "false_negatives",
    "span_matches",
    "correction_matches",
    "correct_cases",
    "alarmed_correct_cases",
)
_DERIVED_FIELDS = (
    "exact_edit_precision",
    "exact_edit_recall",
    "exact_edit_f1",
    "span_accuracy",
    "suggestion_accuracy",
    "false_discovery_proportion",
    "correct_sentence_false_alarm_rate",
)


def compare_quality_v4(
    *,
    baseline_default: Path,
    baseline_morphology: Path,
    result_default: Path,
    result_morphology: Path,
    proposal: Path,
    output: Path,
    replace: bool = False,
) -> dict[str, Any]:
    """Validate two v4 profiles and write a canonical comparison artifact."""

    proposal_value = load_threshold_proposal(proposal)
    if not isinstance(proposal_value, ThresholdProposalV4):
        raise QualityReportError("v4 comparison requires a v4 threshold proposal")
    validate_threshold_proposal(
        proposal_value,
        baseline_path=baseline_default,
        morphology_baseline_path=baseline_morphology,
    )
    if proposal_value.status != "approved" or not proposal_value.enforced:
        raise QualityReportError(
            "v4 comparison requires an explicitly approved and enforced proposal"
        )
    baseline = {
        "default": load_quality_report(baseline_default),
        "morphology": load_quality_report(baseline_morphology),
    }
    result = {
        "default": load_quality_result(result_default),
        "morphology": load_quality_result(result_morphology),
    }
    paths = {
        "default": (baseline_default, result_default),
        "morphology": (baseline_morphology, result_morphology),
    }
    profile_payload: dict[str, Any] = {}
    verdicts: list[str] = []
    for profile_id in ("default", "morphology"):
        _validate_identity(
            baseline[profile_id], result[profile_id], proposal_value, profile_id
        )
        _validate_artifact_snapshot(baseline[profile_id])
        _validate_artifact_snapshot(result[profile_id])
        _validate_diagnostics(baseline[profile_id])
        _validate_diagnostics(result[profile_id])
        _validate_controls(baseline[profile_id])
        _validate_controls(result[profile_id])
        _validate_performance_identity(baseline[profile_id], result[profile_id])
        isolated_reference = _validate_isolated_performance(
            proposal_value,
            profile_id,
            expected_role="reference",
            report=baseline[profile_id],
        )
        isolated_current = _validate_isolated_performance(
            proposal_value,
            profile_id,
            expected_role="current",
            report=result[profile_id],
        )
        floors = getattr(proposal_value, profile_id)
        _validate_performance_environment_binding(
            isolated_reference,
            isolated_current,
            baseline[profile_id],
            result[profile_id],
            tuple(floors.performance.required_environment_match) + ("package_version",),
        )
        gates = _quality_gates(result[profile_id], floors)
        category_gates = _category_gates(result[profile_id], floors)
        stratum_gates = _stratum_gates(result[profile_id], floors)
        control_gates = [
            {
                "gate": f"control:{name}:zero-violations",
                "pass": baseline[profile_id].diagnostics["controls"][name]["violations"]
                == 0
                and result[profile_id].diagnostics["controls"][name]["violations"] == 0,
                "detail": "control violations must remain zero",
            }
            for name in ("conflict", "abstention")
        ]
        source_gate = {
            "gate": "source:exact-ordered-59-parity",
            "pass": _source_rows_reconcile(baseline[profile_id])
            and _source_rows_reconcile(result[profile_id]),
            "detail": "source diagnostics reconcile with the live snapshot",
        }
        performance_gates = _performance_gates(
            isolated_reference, isolated_current, floors.performance
        )
        all_gates = [
            *gates,
            *category_gates,
            *stratum_gates,
            *control_gates,
            source_gate,
            *performance_gates,
        ]
        passed = all(gate["pass"] for gate in all_gates)
        verdict = "pass" if passed else "fail"
        verdicts.append(verdict)
        profile_payload[profile_id] = {
            "profile_id": profile_id,
            "baseline_path": str(paths[profile_id][0]),
            "baseline_sha256": baseline_file_sha256(paths[profile_id][0]),
            "result_path": str(paths[profile_id][1]),
            "result_sha256": baseline_file_sha256(paths[profile_id][1]),
            "quality_counts_baseline": _counts(
                baseline[profile_id].diagnostics["aggregate"]
            ),
            "quality_counts_result": _counts(
                result[profile_id].diagnostics["aggregate"]
            ),
            "metric_deltas": _metric_deltas(baseline[profile_id], result[profile_id]),
            "gates": [*gates, *control_gates, source_gate, *performance_gates],
            "category_gates": category_gates,
            "stratum_gates": stratum_gates,
            "source_parity": _source_parity(result[profile_id]),
            "performance": {
                "baseline": _performance_payload(baseline[profile_id]),
                "result": _performance_payload(result[profile_id]),
            },
            "verdict": verdict,
        }
    canonical_inputs = all(
        path.name.startswith("regression-")
        for path in (
            baseline_default,
            baseline_morphology,
            result_default,
            result_morphology,
            proposal,
        )
    )
    root: dict[str, Any] = {
        "schema_id": (
            "polis.regression-comparison"
            if canonical_inputs
            else "polis.quality-comparison"
        ),
        "schema_version": 4,
        "proposal_path": str(proposal),
        "proposal_sha256": baseline_file_sha256(proposal),
        "dataset_sha256": proposal_value.dataset_sha256,
        "manifest_sha256": proposal_value.manifest_sha256,
        "source_git_sha": proposal_value.source_git_sha,
        "artifacts": {
            "wheel_sha256": proposal_value.wheel_sha256,
            "sdist_sha256": None,
            "wheel_filename": proposal_value.wheel_filename,
            "sdist_filename": None,
        },
        "environment_result": {
            key: _environment(result[key]) for key in ("default", "morphology")
        },
        "environment_baseline": {
            key: _environment(baseline[key]) for key in ("default", "morphology")
        },
        "profiles": profile_payload,
        "aggregate_verdict": "pass" if all(v == "pass" for v in verdicts) else "fail",
        "notes": ["v4 comparison is fail-closed and category/shape aware."],
    }
    mode = "w" if replace else "x"
    with output.open(mode, encoding="utf-8", newline="\n") as stream:
        stream.write(
            json.dumps(root, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        )
    return root


def _validate_performance_environment_binding(
    reference: dict[str, Any],
    current: dict[str, Any],
    baseline: QualityReport,
    result: QualityReport,
    fields: tuple[str, ...],
) -> None:
    reference_environment = reference.get("environment")
    current_environment = current.get("environment")
    if not isinstance(reference_environment, dict) or not isinstance(
        current_environment, dict
    ):
        raise QualityReportError("v4 performance environment identity mismatch")
    report_environments = (
        _environment(baseline),
        _environment(result),
    )
    for field in fields:
        if field not in reference_environment or field not in current_environment:
            raise QualityReportError(
                f"v4 performance required environment field is missing: {field}"
            )
        values = (reference_environment[field], current_environment[field])
        if len(set(values)) != 1:
            raise QualityReportError(f"v4 performance environment mismatch: {field}")
    quality_fields = {
        "package_version",
        "python_version",
        "platform_system",
        "platform_release",
        "platform_machine",
    }
    for field in quality_fields.intersection(fields):
        reference_quality = report_environments[0].get(field)
        current_quality = report_environments[1].get(field)
        if (
            reference_quality is not None
            and reference_environment[field] != reference_quality
        ):
            raise QualityReportError(
                f"v4 quality/performance environment mismatch: {field}"
            )
        if (
            current_quality is not None
            and current_environment[field] != current_quality
        ):
            raise QualityReportError(
                f"v4 quality/performance environment mismatch: {field}"
            )


def _validate_isolated_performance(
    proposal: ThresholdProposalV4,
    profile_id: str,
    *,
    expected_role: str,
    report: QualityReport,
) -> dict[str, Any]:
    values = getattr(proposal, profile_id)
    binding = (
        values.performance_baseline
        if expected_role == "reference"
        else values.performance_result
    )
    artifact = load_runtime_performance_v2(
        Path(binding.path),
        binding=binding,
        profile=profile_id,
        expected_dataset_id=report.dataset_id,
        expected_dataset_sha256=proposal.dataset_sha256,
        expected_manifest_sha256=proposal.manifest_sha256,
        expected_source_sha=proposal.source_git_sha,
        expected_source_snapshot_sha256=source_snapshot_sha256(
            report.source_snapshot or ()
        ),
        expected_wheel_sha256=proposal.wheel_sha256,
        expected_wheel_filename=proposal.wheel_filename,
        expected_role=expected_role,
    )
    return dict(artifact)


def _validate_controls(report: QualityReport) -> None:
    controls = report.diagnostics["controls"]
    for name in ("conflict", "abstention"):
        value = controls[name]
        if value["violations"] != 0 or value["violation_case_ids"]:
            raise QualityReportError(f"v4 {name} control gate failed")
        if name == "conflict" and value["predicted_findings"] != 0:
            raise QualityReportError(
                "v4 conflict control predicted findings are nonzero"
            )


def _validate_performance_identity(
    baseline: QualityReport, result: QualityReport
) -> None:
    if baseline.warmup_repetitions != result.warmup_repetitions:
        raise QualityReportError("v4 performance warmup identity mismatch")
    if baseline.measured_repetitions != result.measured_repetitions:
        raise QualityReportError("v4 performance repetition identity mismatch")
    if baseline.run_identity.profile != result.run_identity.profile:
        raise QualityReportError("v4 performance profile identity mismatch")
    environment_fields = (
        "python_version",
        "platform_system",
        "platform_release",
        "platform_machine",
    )
    if any(
        getattr(baseline.run_identity, field) != getattr(result.run_identity, field)
        for field in environment_fields
    ):
        raise QualityReportError("v4 performance environment identity mismatch")


def _performance_gates(
    baseline: dict[str, Any],
    result: dict[str, Any],
    performance: Any,
) -> list[dict[str, Any]]:
    checks = (
        (
            "performance.maximum_p95_latency_ns",
            result["performance"]["latency_ns"]["p95"]
            <= performance.maximum_p95_latency_ns,
            (
                f"measured={result['performance']['latency_ns']['p95']}, "
                f"maximum={performance.maximum_p95_latency_ns}"
            ),
        ),
        (
            "performance.minimum_throughput_cases_per_second",
            result["performance"]["throughput"]["cases_per_second"]
            >= performance.minimum_throughput_cases_per_second,
            (
                f"measured={result['performance']['throughput']['cases_per_second']}, "
                f"minimum={performance.minimum_throughput_cases_per_second}"
            ),
        ),
        (
            "performance.maximum_worker_incremental_peak_rss_bytes",
            result["rss"]["worker_measured_incremental_peak_rss_bytes"]
            <= performance.maximum_worker_incremental_peak_rss_bytes,
            (
                "measured="
                f"{result['rss']['worker_measured_incremental_peak_rss_bytes']}, "
                f"maximum={performance.maximum_worker_incremental_peak_rss_bytes}"
            ),
        ),
        (
            "performance.reproducibility",
            baseline["reproducibility"]["findings_sha256"]
            == result["reproducibility"]["findings_sha256"]
            and result["reproducibility"]["measured_repetitions"]
            == performance.required_measured_repetitions
            and result["reproducibility"]["warmup_repetitions"]
            == performance.required_warmup_repetitions,
            "repetition, warmup, and measured counts match the approved protocol",
        ),
    )
    return [
        {"gate": gate, "pass": passed, "detail": detail}
        for gate, passed, detail in checks
    ]


def _validate_identity(
    baseline: QualityReport,
    result: QualityReport,
    proposal: ThresholdProposalV4,
    profile_id: str,
) -> None:
    if (
        baseline.dataset_sha256 != proposal.dataset_sha256
        or result.dataset_sha256 != proposal.dataset_sha256
    ):
        raise QualityReportError("v4 comparison dataset identity mismatch")
    if (
        baseline.run_identity.manifest_sha256 != proposal.manifest_sha256
        or result.run_identity.manifest_sha256 != proposal.manifest_sha256
    ):
        raise QualityReportError("v4 comparison manifest identity mismatch")
    for report in (baseline, result):
        identity = report.run_identity
        if (
            identity.dataset_schema_version != 4
            or identity.source_sha != proposal.source_git_sha
        ):
            raise QualityReportError("v4 comparison source identity mismatch")
        if identity.artifact_sha256 != proposal.wheel_sha256:
            raise QualityReportError("v4 comparison wheel identity mismatch")
        if identity.profile is None or identity.profile.id.value != profile_id:
            raise QualityReportError("v4 comparison profile identity mismatch")
        if identity.source_snapshot != proposal.source_snapshot:
            raise QualityReportError("v4 comparison source snapshot mismatch")
    if (
        baseline.counts != result.counts
        or baseline.repetition_hashes != result.repetition_hashes
    ):
        raise QualityReportError(
            "v4 comparison result is not a deterministic remeasurement"
        )


def _validate_artifact_snapshot(report: QualityReport) -> None:
    snapshot = report.source_snapshot
    if snapshot is None or len(snapshot) != 59:
        raise QualityReportError(
            "v4 source snapshot must contain exactly 59 artifact identities"
        )
    sources = tuple(item["source"] for item in snapshot)
    if len(set(sources)) != len(sources) or any(
        not source.startswith("rule:") for source in sources
    ):
        raise QualityReportError("v4 artifact source snapshot has invalid sources")
    if any(not item["operation"] or not item["behavior_version"] for item in snapshot):
        raise QualityReportError(
            "v4 artifact source snapshot has incomplete identities"
        )
    if report.run_identity.source_snapshot != snapshot:
        raise QualityReportError("v4 artifact source snapshot identity is inconsistent")


def _validate_diagnostics(report: QualityReport) -> None:
    diagnostics = report.diagnostics
    if diagnostics is None:
        raise QualityReportError("v4 diagnostics are missing")
    aggregate = _validate_counts(diagnostics["aggregate"])
    categories = diagnostics["category"]
    if not isinstance(categories, dict) or set(categories) != set(_CATEGORIES):
        raise QualityReportError("v4 category diagnostics are incomplete")
    category_total = {field: 0 for field in _COUNT_FIELDS}
    for value in categories.values():
        parsed = _validate_counts(value)
        for field in _COUNT_FIELDS:
            category_total[field] += parsed[field]
    if category_total != aggregate:
        raise QualityReportError("v4 aggregate/category arithmetic mismatch")
    strata = diagnostics["shape_strata"]
    if not isinstance(strata, dict) or set(strata) != set(_CATEGORIES):
        raise QualityReportError("v4 shape diagnostics are incomplete")
    for category in _CATEGORIES:
        values = strata[category]
        if not isinstance(values, dict) or set(values) != set(_SHAPES):
            raise QualityReportError(f"v4 missing required shape stratum: {category}")
        stratum_total = {field: 0 for field in _COUNT_FIELDS}
        for value in values.values():
            parsed = _validate_counts(value)
            for field in _COUNT_FIELDS:
                stratum_total[field] += parsed[field]
        if stratum_total != _counts(categories[category]):
            raise QualityReportError(
                f"v4 category/stratum arithmetic mismatch: {category}"
            )
    source = diagnostics["source"]
    if not isinstance(source, list) or len(source) != 59:
        raise QualityReportError("v4 source diagnostics must contain 59 rows")
    if any(
        not isinstance(row, dict)
        or set(row)
        != {
            "source",
            "category",
            "status",
            "operation",
            "behavior_version",
            "profile",
            "predicted_count",
            "expected_count",
            "exact_match_count",
            "false_positive_count",
            "false_negative_count",
            "case_ids",
        }
        for row in source
    ):
        raise QualityReportError("v4 source diagnostics row is malformed")
    if len({row["source"] for row in source if isinstance(row, dict)}) != 59:
        raise QualityReportError("v4 source diagnostics contain duplicate rows")
    if [row["source"] for row in source if isinstance(row, dict)] != [
        row["source"] for row in report.source_snapshot or ()
    ]:
        raise QualityReportError("v4 source diagnostics do not reconcile with snapshot")
    profile_id = (
        report.run_identity.profile.id.value if report.run_identity.profile else None
    )
    for row in source:
        assert isinstance(row, dict)
        if row["profile"] != profile_id:
            raise QualityReportError("v4 source diagnostics profile mismatch")
        for field in (
            "predicted_count",
            "expected_count",
            "exact_match_count",
            "false_positive_count",
            "false_negative_count",
        ):
            if (
                not isinstance(row[field], int)
                or isinstance(row[field], bool)
                or row[field] < 0
            ):
                raise QualityReportError("v4 source diagnostics counts are invalid")


def _validate_counts(raw: object) -> dict[str, int]:
    if (
        not isinstance(raw, dict)
        or set(raw) != {*_COUNT_FIELDS, *_DERIVED_FIELDS}
        or not all(
            isinstance(raw.get(field), int) and not isinstance(raw.get(field), bool)
            for field in _COUNT_FIELDS
        )
    ):
        raise QualityReportError("v4 diagnostics counts are malformed")
    for field in _DERIVED_FIELDS:
        value = raw.get(field)
        if value is not None and (
            not isinstance(value, int | float)
            or isinstance(value, bool)
            or not __import__("math").isfinite(float(value))
            or not 0.0 <= float(value) <= 1.0
        ):
            raise QualityReportError("v4 diagnostics derived metric is malformed")
    values = {field: int(raw[field]) for field in _COUNT_FIELDS}
    expected_derived = {
        "exact_edit_precision": _ratio(
            values["true_positives"], values["predicted_findings"]
        ),
        "exact_edit_recall": _ratio(
            values["true_positives"], values["expected_findings"]
        ),
        "exact_edit_f1": _f1(values),
        "span_accuracy": _ratio(values["span_matches"], values["expected_findings"]),
        "suggestion_accuracy": _ratio(
            values["correction_matches"], values["span_matches"]
        ),
        "false_discovery_proportion": _ratio(
            values["false_positives"], values["predicted_findings"]
        ),
        "correct_sentence_false_alarm_rate": _ratio(
            values["alarmed_correct_cases"], values["correct_cases"]
        ),
    }
    if any(raw[field] != value for field, value in expected_derived.items()):
        raise QualityReportError("v4 diagnostics derived metric arithmetic mismatch")
    if (
        values["expected_findings"]
        != values["true_positives"] + values["false_negatives"]
    ):
        raise QualityReportError("v4 expected count arithmetic mismatch")
    if (
        values["predicted_findings"]
        != values["true_positives"] + values["false_positives"]
    ):
        raise QualityReportError("v4 predicted count arithmetic mismatch")
    if values["correction_matches"] != values["true_positives"] or values[
        "span_matches"
    ] > min(values["expected_findings"], values["predicted_findings"]):
        raise QualityReportError("v4 match count arithmetic mismatch")
    if values["alarmed_correct_cases"] > values["correct_cases"]:
        raise QualityReportError("v4 correct-case arithmetic mismatch")
    if any(value < 0 for value in values.values()):
        raise QualityReportError("v4 diagnostics counts must be non-negative")
    return values


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _f1(values: dict[str, int]) -> float | None:
    denominator = (
        2 * values["true_positives"]
        + values["false_positives"]
        + values["false_negatives"]
    )
    return None if denominator == 0 else 2 * values["true_positives"] / denominator


def _counts(raw: object) -> dict[str, int]:
    return _validate_counts(raw)


def _metric_deltas(
    baseline: QualityReport, result: QualityReport
) -> list[dict[str, Any]]:
    metrics = (
        ("precision", baseline.quality_precision, result.quality_precision, True),
        ("recall", baseline.quality_recall, result.quality_recall, True),
        ("f1", baseline.quality_f1, result.quality_f1, True),
        (
            "false_alarm_rate",
            baseline.quality_false_alarm_rate,
            result.quality_false_alarm_rate,
            False,
        ),
    )
    return [
        {
            "metric": name,
            "baseline": old,
            "result": new,
            "delta": new - old,
            "higher_is_better": better,
        }
        for name, old, new, better in metrics
        if old is not None and new is not None
    ]


def _quality_gates(
    report: QualityReport, proposal: ProfileThresholdProposalV4
) -> list[dict[str, Any]]:
    return _floor_gate(report.diagnostics["aggregate"], proposal.quality, "aggregate")


def _category_gates(
    report: QualityReport, proposal: ProfileThresholdProposalV4
) -> list[dict[str, Any]]:
    return [
        gate
        for category in _CATEGORIES
        for gate in _floor_gate(
            report.diagnostics["category"][category],
            proposal.category_quality[category],
            f"category:{category}",
        )
    ]


def _stratum_gates(
    report: QualityReport, proposal: ProfileThresholdProposalV4
) -> list[dict[str, Any]]:
    return [
        gate
        for category in _CATEGORIES
        for shape in _SHAPES
        for gate in _floor_gate(
            report.diagnostics["shape_strata"][category][shape],
            proposal.stratum_quality[category][shape],
            f"stratum:{category}:{shape}",
        )
    ]


def _floor_gate(raw: object, floors: Any, scope: str) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        raise QualityReportError(f"v4 {scope} diagnostics are malformed")
    gates: list[dict[str, Any]] = []
    for key, value, threshold, higher in (
        ("precision", raw.get("exact_edit_precision"), floors.minimum_precision, True),
        ("recall", raw.get("exact_edit_recall"), floors.minimum_recall, True),
        ("f1", raw.get("exact_edit_f1"), floors.minimum_f1, True),
        (
            "false_alarm_rate",
            raw.get("correct_sentence_false_alarm_rate"),
            floors.maximum_false_alarm_rate,
            False,
        ),
    ):
        if threshold is None:
            continue
        passed = isinstance(value, int | float) and (
            value >= threshold if higher else value <= threshold
        )
        gates.append(
            {
                "gate": f"{scope}:{key}",
                "pass": passed,
                "detail": f"measured={value!r}, threshold={threshold!r}",
            }
        )
    return gates


def _source_arithmetic(row: dict[str, Any]) -> bool:
    fields = (
        "predicted_count",
        "expected_count",
        "exact_match_count",
        "false_positive_count",
        "false_negative_count",
    )
    values = [row.get(field) for field in fields]
    if not all(
        isinstance(value, int) and not isinstance(value, bool) for value in values
    ):
        return False
    typed_values = tuple(value for value in values if isinstance(value, int))
    if len(typed_values) != 5:
        return False
    predicted, expected, exact, false_positive, false_negative = typed_values
    return bool(
        predicted == exact + false_positive and expected == exact + false_negative
    )


def _source_rows_reconcile(report: QualityReport) -> bool:
    diagnostics = report.diagnostics
    rows = diagnostics["source"]
    aggregate = diagnostics["aggregate"]
    categories = diagnostics["category"]
    if (
        not isinstance(rows, list)
        or not isinstance(aggregate, dict)
        or not isinstance(categories, dict)
        or report.source_snapshot is None
        or len(rows) != 59
    ):
        return False
    if [row.get("source") for row in rows if isinstance(row, dict)] != [
        item["source"] for item in report.source_snapshot
    ]:
        return False
    fields = (
        ("predicted_count", "predicted_findings"),
        ("expected_count", "expected_findings"),
        ("exact_match_count", "true_positives"),
        ("false_positive_count", "false_positives"),
        ("false_negative_count", "false_negatives"),
    )
    for row, snapshot in zip(rows, report.source_snapshot, strict=True):
        if not isinstance(row, dict):
            return False
        if (
            row.get("operation") != snapshot["operation"]
            or row.get("behavior_version") != snapshot["behavior_version"]
            or not _source_arithmetic(row)
        ):
            return False
        status = row["status"]
        counters = tuple(int(row[field]) for field, _ in fields)
        if status in {"abstained", "control", "unmeasured"} and any(counters):
            return False
        if status == "unmeasured" and row["case_ids"]:
            return False
        if status in {"measured", "abstained", "control"} and not row["case_ids"]:
            return False
        if status == "measured" and row["category"] is None:
            return False
    for source_field, aggregate_field in fields:
        if sum(
            int(row[source_field]) for row in rows if row["status"] == "measured"
        ) != int(aggregate[aggregate_field]):
            return False
    for category, values in categories.items():
        if not isinstance(values, dict):
            return False
        for source_field, aggregate_field in fields:
            if sum(
                int(row[source_field])
                for row in rows
                if row["status"] == "measured" and row["category"] == category
            ) != int(values[aggregate_field]):
                return False
    return True


def _source_parity(report: QualityReport) -> dict[str, Any]:
    return {
        "row_count": len(report.diagnostics["source"]),
        "profile": report.run_identity.profile.id.value
        if report.run_identity.profile
        else None,
        "source_sha": report.run_identity.source_sha,
        "snapshot_sha256": source_snapshot_sha256(report.source_snapshot or ()),
    }


def _performance_payload(report: QualityReport) -> dict[str, Any]:
    return {
        "p95_latency_ns": report.latency.p95_ns,
        "throughput_cases_per_second": report.throughput.cases_per_second,
        "peak_rss_bytes": report.resources.peak_rss_bytes,
        "warmup_repetitions": report.warmup_repetitions,
        "measured_repetitions": report.measured_repetitions,
        "repetition_hashes": list(report.repetition_hashes),
    }


def _environment(report: QualityReport) -> dict[str, str]:
    identity = report.run_identity
    return {
        field: str(getattr(identity, field))
        for field in (
            "package_version",
            "python_version",
            "platform_system",
            "platform_release",
            "platform_machine",
        )
    }
