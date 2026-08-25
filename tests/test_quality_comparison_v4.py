from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from polis.evaluation.quality_comparison_v4 import compare_quality_v4
from polis.evaluation.quality_dataset import (
    QualityDatasetVersion,
    load_quality_dataset,
    quality_dataset_paths,
)
from polis.evaluation.quality_report import (
    QualityReportError,
    load_quality_comparison,
)
from polis.evaluation.quality_report_baseline import load_quality_report
from polis.evaluation.quality_report_models import ThresholdProposalV4
from polis.evaluation.quality_report_proposal import load_threshold_proposal
from polis.evaluation.quality_report_result import load_quality_result
from polis.evaluation.quality_v4_measurement import source_snapshot_sha256

ROOT = Path(__file__).resolve().parents[1]
DATASET = load_quality_dataset(version=QualityDatasetVersion.V4)
WHEEL_SHA = "a" * 64
SOURCE_SHA = "1" * 40
REPETITION_HASH = "b" * 64
PROFILE_PROVIDER = {
    "provider": "morfeusz2",
    "package_version": "1.99.15",
    "dictionary_id": "pl.sgjp.sgjp-2026.06.01",
    "dictionary_notice_sha256": (
        "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
    ),
}
CATEGORIES = ("agreement", "inflection", "punctuation", "spelling", "syntax")
SHAPES = (
    "simple-local",
    "sentence-internal",
    "multi-sentence",
    "repeated-occurrence",
    "unicode-and-case",
    "quotation-or-literal",
    "conflict-or-abstention",
)


def _snapshot() -> list[dict[str, str]]:
    payload = json.loads(
        (ROOT / "docs/quality-result-v4-default.json").read_text(encoding="utf-8")
    )
    frozen_snapshot = payload["source_snapshot"]
    assert isinstance(frozen_snapshot, list)
    return [
        {
            "source": item["source"],
            "operation": item["operation"],
            "behavior_version": item["behavior_version"],
        }
        for item in frozen_snapshot
        if isinstance(item, dict)
    ]


def _counts(expected: int) -> dict[str, object]:
    return {
        "expected_findings": expected,
        "predicted_findings": expected,
        "true_positives": expected,
        "false_positives": 0,
        "false_negatives": 0,
        "span_matches": expected,
        "correction_matches": expected,
        "correct_cases": expected,
        "alarmed_correct_cases": 0,
    }


def _diag_counts(expected: int) -> dict[str, object]:
    value = _counts(expected)
    value.update(
        {
            "exact_edit_precision": 1.0 if expected else None,
            "exact_edit_recall": 1.0 if expected else None,
            "exact_edit_f1": 1.0 if expected else None,
            "span_accuracy": 1.0 if expected else None,
            "suggestion_accuracy": 1.0 if expected else None,
            "false_discovery_proportion": 0.0 if expected else None,
            "correct_sentence_false_alarm_rate": 0.0 if expected else None,
        }
    )
    return value


def _source_rows(
    snapshot: list[dict[str, str]], profile: str
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, item in enumerate(snapshot):
        measured = index < len(CATEGORIES)
        rows.append(
            {
                "source": item["source"],
                "category": CATEGORIES[index] if measured else "agreement",
                "status": "measured" if measured else "unmeasured",
                "operation": item["operation"],
                "behavior_version": item["behavior_version"],
                "profile": profile,
                "predicted_count": 7 if measured else 0,
                "expected_count": 7 if measured else 0,
                "exact_match_count": 7 if measured else 0,
                "false_positive_count": 0,
                "false_negative_count": 0,
                "case_ids": [f"measured-case-{index}"] if measured else [],
            }
        )
    return rows


def _proposal_gates(profile: str) -> list[dict[str, object]]:
    decision = {
        "status": "approved",
        "decided_by": "test maintainer",
        "decided_at": "2026-01-01T00:00:00Z",
        "rationale": "test-only approval",
    }
    gates: list[dict[str, object]] = []

    def add(scope: str, metric: str, baseline: object, threshold: object) -> None:
        gates.append(
            {
                "scope": scope,
                "metric": metric,
                "measured_baseline": baseline,
                "proposed_threshold": threshold,
                "rationale": "test quality gate",
                "allowed_variation": 0.0,
                "regression_risk": "test regression",
                "maintainer_decision": decision,
                "effective_schema_version": 4,
            }
        )

    metrics = (
        ("precision", "exact_edit_precision"),
        ("recall", "exact_edit_recall"),
        ("f1", "exact_edit_f1"),
        ("span_accuracy", "span_accuracy"),
        ("suggestion_accuracy", "suggestion_accuracy"),
        ("false_alarm_rate", "correct_sentence_false_alarm_rate"),
    )
    for metric, field in metrics:
        value = 0.0 if field == "correct_sentence_false_alarm_rate" else 1.0
        add("aggregate", metric, value, 1.0)
    for category in CATEGORIES:
        for metric, field in metrics:
            value = 0.0 if field == "correct_sentence_false_alarm_rate" else 1.0
            add(f"category:{category}", metric, value, 1.0)
    for category in CATEGORIES:
        for shape in SHAPES:
            for metric, field in metrics:
                value = 0.0 if field == "correct_sentence_false_alarm_rate" else 1.0
                add(f"stratum:{category}:{shape}", metric, value, 1.0)
    add("source", "exact-ordered-59-parity", True, True)
    add("control:conflict", "zero-violations", 0, 0)
    add("control:abstention", "zero-violations", 0, 0)
    add("performance", "maximum_p95_latency_ns", 100, 100)
    add(
        "performance", "minimum_throughput_cases_per_second", 10_000_000.0, 10_000_000.0
    )
    add("performance", "maximum_worker_incremental_peak_rss_bytes", 0, 0)
    add("performance", "reproducibility", True, True)
    return gates


def _diagnostics(snapshot: list[dict[str, str]], profile: str) -> dict[str, object]:
    control_abstention_ids = [
        "v4_control_abstain_01",
        "v4_control_abstain_02",
        "v4_control_abstain_03",
    ]
    if profile == "default":
        control_abstention_ids.extend(
            [
                "v4_agreement_positive_05",
                "v4_agreement_positive_07",
                "v4_agreement_positive_08",
                "v4_agreement_negative_09",
                "v4_agreement_negative_13",
                "v4_inflection_positive_02",
                "v4_inflection_positive_05",
                "v4_inflection_positive_08",
                "v4_inflection_negative_09",
            ]
        )
    category: dict[str, dict[str, object]] = {}
    strata: dict[str, dict[str, dict[str, object]]] = {}
    category_cases: dict[str, dict[str, int]] = {}
    stratum_cases: dict[str, dict[str, dict[str, int]]] = {}
    for name in CATEGORIES:
        category[name] = _diag_counts(7)
        category_cases[name] = {"cases": 24, "eligible_cases": 24, "excluded_cases": 0}
        strata[name] = {shape: _diag_counts(1) for shape in SHAPES}
        stratum_cases[name] = {
            shape: {"cases": 1, "eligible_cases": 1, "excluded_cases": 0}
            for shape in SHAPES
        }
    return {
        "aggregate": _diag_counts(35),
        "category": category,
        "shape_strata": strata,
        "category_cases": category_cases,
        "stratum_cases": stratum_cases,
        "source": _source_rows(snapshot, profile),
        "controls": {
            "conflict": {
                "case_count": 1,
                "case_ids": ["v4_control_conflict_punctuation"],
                "predicted_findings": 0,
                "violations": 0,
                "violation_case_ids": [],
            },
            "abstention": {
                "case_count": len(control_abstention_ids),
                "predicted_findings": 0,
                "case_ids": control_abstention_ids,
                "violations": 0,
                "violation_case_ids": [],
            },
        },
    }


def _report(profile: str, *, result: bool) -> dict[str, object]:
    snapshot = _snapshot()
    samples = len(DATASET.cases) * 2
    total = samples * 100
    return {
        "schema_id": "polis.quality-result" if result else "polis.quality-baseline",
        "schema_version": 1 if result else 4,
        "analyzer": "Analyzer(AnalyzerConfig())",
        "artifact": {"sha256": WHEEL_SHA},
        "dataset": {
            "id": DATASET.id,
            "schema_id": DATASET.schema_id,
            "schema_version": 4,
            "sha256": DATASET.canonical_sha256,
            "cases": len(DATASET.cases),
            "source": f"quality:{DATASET.id}@4",
            "manifest": {
                "schema_id": "polis.quality-development-manifest",
                "schema_version": 4,
                "sha256": hashlib.sha256(
                    (
                        ROOT / "src/polis/evaluation/datasets/quality/v4/manifest.json"
                    ).read_bytes()
                ).hexdigest(),
            },
        },
        "quality": {
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
            "span_accuracy": 1.0,
            "correction_accuracy": 1.0,
            "false_alarm_rate": 0.0,
            "counts": _counts(35),
        },
        "performance": {
            "latency_ns": {
                "sample_count": samples,
                "min": 100,
                "mean": 100,
                "p50": 100,
                "p95": 100,
                "max": 100,
            },
            "throughput": {
                "measured_cases": samples,
                "measured_code_points": samples * 10,
                "total_duration_ns": total,
                "cases_per_second": samples * 1_000_000_000 / total,
                "code_points_per_second": samples * 10 * 1_000_000_000 / total,
            },
            "peak_rss_bytes": 1000,
        },
        "environment": {
            "package_version": "0.2.0",
            "python_version": "3.13.12",
            "platform_system": "Darwin",
            "platform_release": "24.3.0",
            "platform_machine": "arm64",
        },
        "reproducibility": {
            "warmup_repetitions": 1,
            "measured_repetitions": 2,
            "stable_repetitions": 2,
            "repetition_hashes": [REPETITION_HASH, REPETITION_HASH],
        },
        "source": {"git_sha": SOURCE_SHA},
        "profile": {
            "id": profile,
            "morphology_provider": (
                PROFILE_PROVIDER if profile == "morphology" else None
            ),
            "planned_morphology_source_semantics": (
                "provider-absent-abstention"
                if profile == "default"
                else "qualified-provider-exercised-sources-not-implemented"
            ),
            "planned_non_morphology_source_semantics": "sources-not-implemented",
        },
        "diagnostics": _diagnostics(snapshot, profile),
        "source_snapshot": snapshot,
    }


def _floors(value: float | None = 0.0) -> dict[str, object]:
    return {
        "minimum_precision": value,
        "minimum_recall": value,
        "minimum_f1": value,
        "minimum_exact_span_accuracy": value,
        "minimum_exact_correction_accuracy": value,
        "maximum_false_alarm_rate": 1.0,
    }


def _performance_artifact(
    profile: str, source_sha: str = SOURCE_SHA, role: str = "reference"
) -> dict[str, object]:
    provider = PROFILE_PROVIDER if profile == "morphology" else None
    return {
        "schema_id": "polis.runtime-performance-result",
        "schema_version": 1,
        "protocol_version": 2,
        "dataset_version": "v4",
        "role": role,
        "profile": profile,
        "source": {"git_sha": source_sha},
        "artifact": {
            "wheel_filename": "polis_nlp-0.2.0-py3-none-any.whl",
            "wheel_sha256": WHEEL_SHA,
        },
        "protocol_implementation": {
            "overlay_applied": False,
            "runtime_performance_protocol_sha256": WHEEL_SHA,
            "runtime_performance_worker_sha256": WHEEL_SHA,
        },
        "dataset": {
            "id": DATASET.id,
            "schema_id": "polis.quality-development-dataset",
            "schema_version": 4,
            "sha256": DATASET.canonical_sha256,
            "manifest_sha256": hashlib.sha256(
                (
                    ROOT / "src/polis/evaluation/datasets/quality/v4/manifest.json"
                ).read_bytes()
            ).hexdigest(),
            "cases": 124,
            "source_snapshot_sha256": source_snapshot_sha256(tuple(_snapshot())),
        },
        "identity": {
            "profile": profile,
            "provider": provider,
            "source_git_sha": source_sha,
            "wheel_sha256": WHEEL_SHA,
            "dataset_sha256": DATASET.canonical_sha256,
            "manifest_sha256": hashlib.sha256(
                (
                    ROOT / "src/polis/evaluation/datasets/quality/v4/manifest.json"
                ).read_bytes()
            ).hexdigest(),
        },
        "environment": {
            "package_version": "0.2.0",
            "platform_machine": "arm64",
            "platform_release": "24.3.0",
            "platform_system": "Darwin",
            "python_version": "3.13.12",
        },
        "morphology_provider": provider,
        "rss": {
            "harness_peak_rss_bytes": 1000,
            "worker_startup_rss_bytes": 1000,
            "worker_measurement_start_rss_bytes": 1000,
            "worker_peak_rss_bytes": 1000,
            "worker_measured_incremental_peak_rss_bytes": 0,
        },
        "performance": {
            "latency_ns": {
                "sample_count": 620,
                "min": 100,
                "mean": 100,
                "p50": 100,
                "p95": 100,
                "max": 100,
            },
            "throughput": {
                "measured_cases": 620,
                "measured_code_points": 6200,
                "total_duration_ns": 62000,
                "cases_per_second": 10000000.0,
                "code_points_per_second": 100000000.0,
            },
        },
        "quality": {
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
            "span_accuracy": 1.0,
            "correction_accuracy": 1.0,
            "false_alarm_rate": 0.0,
            "counts": _counts(35),
        },
        "reproducibility": {
            "warmup_repetitions": 1,
            "measured_repetitions": 5,
            "stable_repetitions": 5,
            "findings_sha256": REPETITION_HASH,
        },
    }


def _proposal(
    paths: dict[str, Path], digests: dict[str, str], *, approved: bool = True
) -> dict[str, object]:
    performance = {
        "maximum_p95_latency_ns": 100,
        "minimum_throughput_cases_per_second": 10_000_000.0,
        "maximum_peak_rss_bytes": 1000,
        "maximum_worker_incremental_peak_rss_bytes": 0,
        "required_warmup_repetitions": 1,
        "required_measured_repetitions": 5,
        "require_identical_repetition_hashes": True,
        "required_environment_match": [
            "python_version",
            "platform_system",
            "platform_release",
            "platform_machine",
        ],
        "allowed_regression_fraction": 0.0,
        "missing_metric": "fail",
        "nondeterminism": "fail",
        "environment_mismatch": "fail",
        "performance_regression": "fail",
    }

    def profile(name: str) -> dict[str, object]:
        return {
            "baseline_path": str(paths[name]),
            "baseline_sha256": digests[name],
            "quality_floors": _floors(1.0),
            "category_floors": {category: _floors(1.0) for category in CATEGORIES},
            "stratum_floors": {
                category: {shape: _floors(1.0) for shape in SHAPES}
                for category in CATEGORIES
            },
            "performance_comparison": performance,
            "performance_artifact": {
                "path": str(paths[name].with_name(f"performance-{name}.json")),
                "sha256": hashlib.sha256(
                    paths[name].with_name(f"performance-{name}.json").read_bytes()
                ).hexdigest(),
                "protocol_version": 2,
                "protocol_sha256": WHEEL_SHA,
                "worker_sha256": WHEEL_SHA,
            },
            "performance_result_artifact": {
                "path": str(paths[name].with_name(f"performance-result-{name}.json")),
                "sha256": hashlib.sha256(
                    paths[name]
                    .with_name(f"performance-result-{name}.json")
                    .read_bytes()
                ).hexdigest(),
                "protocol_version": 2,
                "protocol_sha256": WHEEL_SHA,
                "worker_sha256": WHEEL_SHA,
            },
            "gates": _proposal_gates(name),
        }

    return {
        "schema_id": "polis.quality-threshold-proposal",
        "schema_version": 4,
        "effective_schema_version": 4,
        "dataset_sha256": DATASET.canonical_sha256,
        "manifest_sha256": hashlib.sha256(
            (
                ROOT / "src/polis/evaluation/datasets/quality/v4/manifest.json"
            ).read_bytes()
        ).hexdigest(),
        "source_git_sha": SOURCE_SHA,
        "wheel_sha256": WHEEL_SHA,
        "wheel_filename": "polis_nlp-0.2.0-py3-none-any.whl",
        "wheel_path": "/tmp/polis_nlp-0.2.0-py3-none-any.whl",
        "source_snapshot": _snapshot(),
        "profiles": {
            "default": profile("default"),
            "morphology": profile("morphology"),
        },
        "status": "approved" if approved else "pending_maintainer_approval",
        "enforced": approved,
        "decision": (
            {
                "status": "approved",
                "enforced": True,
                "approved_by": "Polis maintainer",
                "approved_at": "2026-01-01T00:00:00Z",
                "rationale": "test-only explicit approval",
            }
            if approved
            else None
        ),
    }


def _write_artifacts(tmp_path: Path, *, approved: bool = True) -> dict[str, Path]:
    paths = {
        "default": tmp_path / "baseline-default.json",
        "morphology": tmp_path / "baseline-morphology.json",
        "result-default": tmp_path / "result-default.json",
        "result-morphology": tmp_path / "result-morphology.json",
        "proposal": tmp_path / "proposal.json",
        "comparison": tmp_path / "comparison.json",
    }
    for profile in ("default", "morphology"):
        performance_path = tmp_path / f"performance-{profile}.json"
        performance_path.write_text(
            json.dumps(_performance_artifact(profile), sort_keys=True), encoding="utf-8"
        )
        result_performance_path = tmp_path / f"performance-result-{profile}.json"
        result_performance_path.write_text(
            json.dumps(_performance_artifact(profile, role="current"), sort_keys=True),
            encoding="utf-8",
        )
        paths[profile].write_text(
            json.dumps(_report(profile, result=False), sort_keys=True), encoding="utf-8"
        )
        paths[f"result-{profile}"].write_text(
            json.dumps(_report(profile, result=True), sort_keys=True), encoding="utf-8"
        )
    digests = {
        name: hashlib.sha256(paths[name].read_bytes()).hexdigest()
        for name in ("default", "morphology")
    }
    paths["proposal"].write_text(
        json.dumps(_proposal(paths, digests, approved=approved), sort_keys=True),
        encoding="utf-8",
    )
    return paths


def _compare(paths: dict[str, Path]) -> dict[str, object]:
    value = compare_quality_v4(
        baseline_default=paths["default"],
        baseline_morphology=paths["morphology"],
        result_default=paths["result-default"],
        result_morphology=paths["result-morphology"],
        proposal=paths["proposal"],
        output=paths["comparison"],
    )
    assert isinstance(value, dict)
    return value


def test_quality_comparison_v4_valid_artifacts_round_trip(tmp_path: Path) -> None:
    paths = _write_artifacts(tmp_path)
    root = _compare(paths)
    comparison = load_quality_comparison(paths["comparison"])
    assert root["aggregate_verdict"] == "pass"
    assert comparison.v4 is True
    assert comparison.aggregate_verdict == "pass"
    assert comparison.sdist_sha256 is None
    for profile in comparison.profiles.values():
        assert profile.verdict == "pass"
        assert profile.performance is not None
        assert any(gate.gate.startswith("performance.") for gate in profile.gates)
        assert profile.source_parity is not None


def test_quality_comparison_v4_result_and_proposal_loaders_are_explicit(
    tmp_path: Path,
) -> None:
    paths = _write_artifacts(tmp_path)
    assert (
        load_quality_report(paths["default"]).run_identity.dataset_schema_version == 4
    )
    assert (
        load_quality_result(paths["result-default"]).run_identity.dataset_schema_version
        == 4
    )
    proposal = load_threshold_proposal(paths["proposal"])
    assert isinstance(proposal, ThresholdProposalV4)
    assert proposal.status == "approved"
    assert proposal.enforced is True


@pytest.mark.parametrize(
    "mutation",
    (
        "dataset_sha256",
        "manifest_sha256",
        "profile",
        "source_snapshot",
        "category_count",
        "stratum_count",
        "precision",
        "false_alarm_rate",
        "stale_result",
        "performance",
    ),
)
def test_quality_comparison_v4_mutations_fail_closed(
    tmp_path: Path, mutation: str
) -> None:
    paths = _write_artifacts(tmp_path)
    if mutation == "dataset_sha256":
        payload = json.loads(paths["default"].read_text())
        payload["dataset"]["sha256"] = "c" * 64
        paths["default"].write_text(json.dumps(payload))
    elif mutation == "manifest_sha256":
        payload = json.loads(paths["default"].read_text())
        payload["dataset"]["manifest"]["sha256"] = "c" * 64
        paths["default"].write_text(json.dumps(payload))
    elif mutation == "profile":
        payload = json.loads(paths["morphology"].read_text())
        payload["profile"]["id"] = "default"
        paths["morphology"].write_text(json.dumps(payload))
    elif mutation == "source_snapshot":
        payload = json.loads(paths["default"].read_text())
        payload["source_snapshot"][0]["source"] = "rule:syntax.changed"
        paths["default"].write_text(json.dumps(payload))
    elif mutation == "category_count":
        payload = json.loads(paths["default"].read_text())
        payload["diagnostics"]["category"]["syntax"]["expected_findings"] = 8
        paths["default"].write_text(json.dumps(payload))
    elif mutation == "stratum_count":
        payload = json.loads(paths["default"].read_text())
        payload["diagnostics"]["shape_strata"]["syntax"][SHAPES[0]][
            "expected_findings"
        ] = 2
        paths["default"].write_text(json.dumps(payload))
    elif mutation == "precision":
        payload = json.loads(paths["default"].read_text())
        payload["diagnostics"]["aggregate"]["exact_edit_precision"] = 0.5
        paths["default"].write_text(json.dumps(payload))
    elif mutation == "false_alarm_rate":
        payload = json.loads(paths["default"].read_text())
        payload["diagnostics"]["aggregate"]["correct_sentence_false_alarm_rate"] = 0.5
        paths["default"].write_text(json.dumps(payload))
    elif mutation == "stale_result":
        payload = json.loads(paths["result-default"].read_text())
        payload["reproducibility"]["repetition_hashes"] = ["d" * 64, "d" * 64]
        paths["result-default"].write_text(json.dumps(payload))
    elif mutation == "performance":
        payload = json.loads(paths["result-default"].read_text())
        payload["performance"]["latency_ns"]["p95"] = 101
        payload["performance"]["throughput"]["total_duration_ns"] = 101 * 248
        payload["performance"]["throughput"]["cases_per_second"] = (
            248 * 1_000_000_000 / (101 * 248)
        )
        payload["performance"]["throughput"]["code_points_per_second"] = (
            2480 * 1_000_000_000 / (101 * 248)
        )
        paths["result-default"].write_text(json.dumps(payload))
    else:
        raise AssertionError(mutation)
    with pytest.raises((QualityReportError, ValueError)):
        _compare(paths)


def test_quality_comparison_v4_rejects_malformed_nested_performance_payload(
    tmp_path: Path,
) -> None:
    paths = _write_artifacts(tmp_path)
    performance = paths["morphology"].with_name("performance-result-morphology.json")
    payload = json.loads(performance.read_text())
    payload["artifact"].pop("wheel_filename")
    payload["artifact"]["unexpected"] = True
    payload["performance"]["throughput"].update(
        measured_code_points="nonsense",
        code_points_per_second=123.0,
    )
    payload["reproducibility"]["findings_sha256"] = "Z" * 64
    performance.write_text(json.dumps(payload, sort_keys=True))
    proposal = json.loads(paths["proposal"].read_text())
    proposal["profiles"]["morphology"]["performance_result_artifact"]["sha256"] = (
        hashlib.sha256(performance.read_bytes()).hexdigest()
    )
    paths["proposal"].write_text(json.dumps(proposal, sort_keys=True))
    with pytest.raises(QualityReportError, match="artifact fields mismatch"):
        _compare(paths)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("mean", "latency arithmetic mismatch"),
        ("precision", "quality metric arithmetic mismatch"),
    ),
)
def test_quality_comparison_v4_rejects_rebound_arithmetic_mutations(
    tmp_path: Path, mutation: str, message: str
) -> None:
    paths = _write_artifacts(tmp_path)
    performance = paths["default"].with_name("performance-result-default.json")
    payload = json.loads(performance.read_text())
    if mutation == "mean":
        payload["performance"]["latency_ns"]["mean"] = 0
    else:
        payload["quality"]["precision"] = 0.123
    performance.write_text(json.dumps(payload, sort_keys=True))
    proposal = json.loads(paths["proposal"].read_text())
    proposal["profiles"]["default"]["performance_result_artifact"]["sha256"] = (
        hashlib.sha256(performance.read_bytes()).hexdigest()
    )
    paths["proposal"].write_text(json.dumps(proposal, sort_keys=True))

    with pytest.raises(QualityReportError, match=message):
        _compare(paths)


def test_runtime_performance_validator_cli_uses_v4_manifest_by_default(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "runtime-performance-v2-current-default.json"
    artifact.write_text(
        json.dumps(_performance_artifact("default", role="current"), sort_keys=True),
        encoding="utf-8",
    )
    command = [
        sys.executable,
        str(ROOT / "scripts/validate_runtime_performance_v2.py"),
        "--artifact",
        str(artifact),
        "--profile",
        "default",
        "--role",
        "current",
        "--source-sha",
        SOURCE_SHA,
        "--wheel-sha256",
        WHEEL_SHA,
        "--protocol-sha256",
        WHEEL_SHA,
        "--worker-sha256",
        WHEEL_SHA,
    ]
    result = subprocess.run(
        command, cwd=ROOT, check=False, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert str(artifact) in result.stdout


def test_runtime_performance_validator_cli_rejects_wrong_manifest(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "runtime-performance-v2-current-default.json"
    artifact.write_text(
        json.dumps(_performance_artifact("default", role="current"), sort_keys=True),
        encoding="utf-8",
    )
    _, v1_manifest = quality_dataset_paths(QualityDatasetVersion.V1)
    command = [
        sys.executable,
        str(ROOT / "scripts/validate_runtime_performance_v2.py"),
        "--artifact",
        str(artifact),
        "--profile",
        "default",
        "--role",
        "current",
        "--manifest-sha256",
        hashlib.sha256(v1_manifest.read_bytes()).hexdigest(),
        "--source-sha",
        SOURCE_SHA,
        "--wheel-sha256",
        WHEEL_SHA,
        "--protocol-sha256",
        WHEEL_SHA,
        "--worker-sha256",
        WHEEL_SHA,
    ]
    result = subprocess.run(
        command, cwd=ROOT, check=False, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "identity mismatch" in result.stderr


def test_quality_comparison_v4_rejects_performance_environment_drift(
    tmp_path: Path,
) -> None:
    paths = _write_artifacts(tmp_path)
    performance = paths["morphology"].with_name("performance-result-morphology.json")
    payload = json.loads(performance.read_text())
    payload["environment"]["python_version"] = "9.9.9"
    performance.write_text(json.dumps(payload, sort_keys=True))
    proposal = json.loads(paths["proposal"].read_text())
    proposal["profiles"]["morphology"]["performance_result_artifact"]["sha256"] = (
        hashlib.sha256(performance.read_bytes()).hexdigest()
    )
    paths["proposal"].write_text(json.dumps(proposal, sort_keys=True))
    with pytest.raises(QualityReportError, match="environment mismatch"):
        _compare(paths)


def test_quality_comparison_v4_approval_decision_rejects_extra_field(
    tmp_path: Path,
) -> None:
    paths = _write_artifacts(tmp_path)
    proposal = json.loads(paths["proposal"].read_text())
    proposal["decision"]["unexpected"] = True
    paths["proposal"].write_text(json.dumps(proposal, sort_keys=True))
    with pytest.raises(QualityReportError, match="decision"):
        load_threshold_proposal(paths["proposal"])


def test_quality_comparison_v4_gate_decision_rejects_extra_field(
    tmp_path: Path,
) -> None:
    paths = _write_artifacts(tmp_path)
    proposal = json.loads(paths["proposal"].read_text())
    proposal["profiles"]["default"]["gates"][0]["maintainer_decision"]["unexpected"] = (
        True
    )
    paths["proposal"].write_text(json.dumps(proposal, sort_keys=True))
    with pytest.raises(QualityReportError, match="decision"):
        load_threshold_proposal(paths["proposal"])


def test_quality_comparison_v4_pending_proposal_cannot_authorize_comparison(
    tmp_path: Path,
) -> None:
    paths = _write_artifacts(tmp_path, approved=False)
    with pytest.raises(QualityReportError, match="approved and enforced"):
        _compare(paths)


def test_quality_runner_generated_proposal_loads_and_validates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from polis.evaluation import quality_runner

    paths = _write_artifacts(tmp_path)
    args = SimpleNamespace(
        baseline=paths["default"],
        morphology_baseline=paths["morphology"],
        wheel_filename="polis_nlp-0.2.0-py3-none-any.whl",
        wheel_path=tmp_path / "polis_nlp-0.2.0-py3-none-any.whl",
        protocol_sha256=WHEEL_SHA,
        worker_sha256=WHEEL_SHA,
        performance_default_reference=tmp_path / "performance-default.json",
        performance_default_reference_sha256=hashlib.sha256(
            (tmp_path / "performance-default.json").read_bytes()
        ).hexdigest(),
        performance_default_current=tmp_path / "performance-result-default.json",
        performance_default_current_sha256=hashlib.sha256(
            (tmp_path / "performance-result-default.json").read_bytes()
        ).hexdigest(),
        performance_morphology_reference=tmp_path / "performance-morphology.json",
        performance_morphology_reference_sha256=hashlib.sha256(
            (tmp_path / "performance-morphology.json").read_bytes()
        ).hexdigest(),
        performance_morphology_current=tmp_path / "performance-result-morphology.json",
        performance_morphology_current_sha256=hashlib.sha256(
            (tmp_path / "performance-result-morphology.json").read_bytes()
        ).hexdigest(),
        default_maximum_p95_latency_ns=100,
        default_minimum_throughput_cases_per_second=10_000_000.0,
        default_maximum_worker_incremental_peak_rss_bytes=0,
        morphology_maximum_p95_latency_ns=100,
        morphology_minimum_throughput_cases_per_second=10_000_000.0,
        morphology_maximum_worker_incremental_peak_rss_bytes=0,
        output=tmp_path / "generated-proposal.json",
        replace=False,
    )
    monkeypatch.setattr(quality_runner, "_validate_wheel_file", lambda *_: None)
    quality_runner._pending_v4_proposal(args)
    generated_payload = json.loads(args.output.read_text(encoding="utf-8"))
    assert generated_payload["schema_id"] == "polis.regression-threshold-proposal"
    generated = load_threshold_proposal(args.output)
    assert isinstance(generated, ThresholdProposalV4)
    assert generated.status == "pending_maintainer_approval"
    assert generated.default.performance.maximum_worker_incremental_peak_rss_bytes == 0
    assert generated.default.performance_baseline.protocol_sha256 == WHEEL_SHA


def test_quality_comparison_v4_isolated_rss_over_cap_fails(
    tmp_path: Path,
) -> None:
    paths = _write_artifacts(tmp_path)
    performance = paths["morphology"].with_name("performance-result-morphology.json")
    payload = json.loads(performance.read_text())
    payload["rss"]["worker_peak_rss_bytes"] = 1999
    payload["rss"]["worker_measured_incremental_peak_rss_bytes"] = 999
    performance.write_text(json.dumps(payload, sort_keys=True))
    proposal = json.loads(paths["proposal"].read_text())
    binding = proposal["profiles"]["morphology"]["performance_result_artifact"]
    binding["sha256"] = hashlib.sha256(performance.read_bytes()).hexdigest()
    paths["proposal"].write_text(json.dumps(proposal, sort_keys=True))
    comparison = _compare(paths)
    profiles = comparison["profiles"]
    assert isinstance(profiles, dict)
    morphology = profiles["morphology"]
    assert isinstance(morphology, dict)
    gates = morphology["gates"]
    assert isinstance(gates, list)
    rss_gate = next(
        gate
        for gate in gates
        if gate["gate"] == "performance.maximum_worker_incremental_peak_rss_bytes"
    )
    assert rss_gate == {
        "gate": "performance.maximum_worker_incremental_peak_rss_bytes",
        "pass": False,
        "detail": "measured=999, maximum=0",
    }
    assert comparison["aggregate_verdict"] == "fail"


@pytest.mark.parametrize(
    ("metric", "mutate"),
    [
        (
            "p95",
            lambda payload: payload["performance"]["latency_ns"].update(
                p95=101, max=101
            ),
        ),
        (
            "throughput",
            lambda payload: (
                payload["performance"]["throughput"].update(
                    total_duration_ns=124000,
                    cases_per_second=5_000_000.0,
                    code_points_per_second=50_000_000.0,
                )
                or payload["performance"]["latency_ns"].update(
                    mean=200, min=100, p50=200, p95=200, max=200
                )
            ),
        ),
    ],
)
def test_quality_comparison_v4_isolated_performance_caps_fail(
    tmp_path: Path, metric: str, mutate: object
) -> None:
    paths = _write_artifacts(tmp_path)
    performance = paths["morphology"].with_name("performance-result-morphology.json")
    payload = json.loads(performance.read_text())
    assert callable(mutate)
    mutate(payload)
    performance.write_text(json.dumps(payload, sort_keys=True))
    proposal = json.loads(paths["proposal"].read_text())
    binding = proposal["profiles"]["morphology"]["performance_result_artifact"]
    binding["sha256"] = hashlib.sha256(performance.read_bytes()).hexdigest()
    paths["proposal"].write_text(json.dumps(proposal, sort_keys=True))
    comparison = _compare(paths)
    gate_name = (
        "performance.maximum_p95_latency_ns"
        if metric == "p95"
        else "performance.minimum_throughput_cases_per_second"
    )
    profiles = comparison["profiles"]
    assert isinstance(profiles, dict)
    morphology = profiles["morphology"]
    assert isinstance(morphology, dict)
    gates = morphology["gates"]
    assert isinstance(gates, list)
    gate = next(gate for gate in gates if gate["gate"] == gate_name)
    assert gate["pass"] is False
    assert comparison["aggregate_verdict"] == "fail"


def test_published_quality_comparison_v4_is_reproducible(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(ROOT)
    output = tmp_path / "quality-comparison-v4.json"
    comparison = compare_quality_v4(
        baseline_default=Path("docs/quality-baseline-v4-default.json"),
        baseline_morphology=Path("docs/quality-baseline-v4-morphology.json"),
        result_default=Path("docs/quality-result-v4-default.json"),
        result_morphology=Path("docs/quality-result-v4-morphology.json"),
        proposal=Path("docs/quality-threshold-proposal-v4.json"),
        output=output,
        replace=False,
    )
    assert comparison["aggregate_verdict"] == "pass"
    assert output.read_bytes() == Path("docs/quality-comparison-v4.json").read_bytes()
    assert hashlib.sha256(output.read_bytes()).hexdigest() == (
        "b59a4fe78d5fa69fc18e00301809e52036f3f6ed343352eda5005fdefaaeb190"
    )


@pytest.mark.parametrize(
    "field", ["protocol_implementation", "profile", "dataset", "source", "artifact"]
)
def test_quality_comparison_v4_isolated_identity_mismatch_fails(
    tmp_path: Path, field: str
) -> None:
    paths = _write_artifacts(tmp_path)
    performance = paths["morphology"].with_name("performance-result-morphology.json")
    payload = json.loads(performance.read_text())
    if field == "protocol_implementation":
        payload[field]["runtime_performance_protocol_sha256"] = "c" * 64
    elif field == "profile":
        payload[field] = "default"
    elif field == "dataset":
        payload[field]["sha256"] = "c" * 64
    elif field == "source":
        payload[field]["git_sha"] = "2" * 40
    else:
        payload[field]["wheel_sha256"] = "c" * 64
    performance.write_text(json.dumps(payload, sort_keys=True))
    proposal = json.loads(paths["proposal"].read_text())
    binding = proposal["profiles"]["morphology"]["performance_result_artifact"]
    binding["sha256"] = hashlib.sha256(performance.read_bytes()).hexdigest()
    paths["proposal"].write_text(json.dumps(proposal, sort_keys=True))
    with pytest.raises((QualityReportError, ValueError)):
        _compare(paths)


def test_quality_comparison_v4_source_total_drift_fails(
    tmp_path: Path,
) -> None:
    paths = _write_artifacts(tmp_path)
    payload = json.loads(paths["default"].read_text())
    payload["diagnostics"]["source"][0]["exact_match_count"] += 1
    payload["diagnostics"]["source"][0]["predicted_count"] += 1
    paths["default"].write_text(json.dumps(payload, sort_keys=True))
    proposal = json.loads(paths["proposal"].read_text())
    proposal["profiles"]["default"]["baseline_sha256"] = hashlib.sha256(
        paths["default"].read_bytes()
    ).hexdigest()
    paths["proposal"].write_text(json.dumps(proposal, sort_keys=True))
    with pytest.raises(QualityReportError, match="source"):
        _compare(paths)


def test_quality_comparison_v4_incomplete_gate_coverage_fails(
    tmp_path: Path,
) -> None:
    paths = _write_artifacts(tmp_path)
    proposal = json.loads(paths["proposal"].read_text())
    proposal["profiles"]["default"]["gates"].pop()
    paths["proposal"].write_text(json.dumps(proposal, sort_keys=True))
    with pytest.raises(QualityReportError):
        _compare(paths)


def test_quality_comparison_v4_snapshot_hash_is_canonical() -> None:
    snapshot = tuple(_snapshot())
    assert source_snapshot_sha256(snapshot) == (
        "64b68c0c889aa0777b56e4730f0a1ec6ab82f4944512b05affc329cae2337a9c"
    )
