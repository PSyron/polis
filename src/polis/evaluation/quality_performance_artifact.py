"""Strict bindings for isolated runtime-performance-v2 evidence."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from polis.evaluation.quality_report_models import (
    PerformanceArtifactBinding,
    QualityReportError,
)

_SOURCE_SNAPSHOT_SHA256 = (
    "64b68c0c889aa0777b56e4730f0a1ec6ab82f4944512b05affc329cae2337a9c"
)
_PROVIDER = {
    "provider": "morfeusz2",
    "package_version": "1.99.15",
    "dictionary_id": "pl.sgjp.sgjp-2026.06.01",
    "dictionary_notice_sha256": (
        "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
    ),
}
_ROOT_FIELDS = {
    "schema_id",
    "schema_version",
    "protocol_version",
    "dataset_version",
    "role",
    "profile",
    "source",
    "artifact",
    "protocol_implementation",
    "dataset",
    "identity",
    "environment",
    "morphology_provider",
    "rss",
    "performance",
    "quality",
    "reproducibility",
}


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_runtime_performance_v2(
    path: Path,
    *,
    binding: PerformanceArtifactBinding,
    profile: str,
    expected_dataset_id: str,
    expected_dataset_sha256: str,
    expected_manifest_sha256: str,
    expected_source_sha: str,
    expected_wheel_sha256: str,
    expected_wheel_filename: str | None = None,
    expected_role: str | None = None,
) -> dict[str, Any]:
    """Load one v4 performance artifact and verify every identity boundary."""

    if binding.path != str(path) or file_sha256(path) != binding.sha256:
        raise QualityReportError("v4 performance artifact path or digest mismatch")
    try:
        root = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise QualityReportError("v4 performance artifact is not valid JSON") from error
    if not isinstance(root, dict) or set(root) != _ROOT_FIELDS:
        raise QualityReportError("v4 performance artifact fields mismatch")
    if (
        root["schema_id"] != "polis.runtime-performance-result"
        or root["schema_version"] != 1
    ):
        raise QualityReportError("v4 performance artifact schema mismatch")
    if root["protocol_version"] != 2 or root["dataset_version"] != "v4":
        raise QualityReportError("v4 performance artifact protocol or dataset mismatch")
    role = _string(root, "role")
    if root["profile"] != profile:
        raise QualityReportError("v4 performance profile identity mismatch")
    if expected_role is not None and role != expected_role:
        raise QualityReportError("v4 performance artifact role mismatch")
    source = _object(root["source"], "source")
    if source != {"git_sha": expected_source_sha}:
        raise QualityReportError("v4 performance artifact source identity mismatch")
    artifact = _exact_object(
        root["artifact"], {"wheel_filename", "wheel_sha256"}, "artifact"
    )
    protocol_implementation = _exact_object(
        root["protocol_implementation"],
        {
            "overlay_applied",
            "runtime_performance_protocol_sha256",
            "runtime_performance_worker_sha256",
        },
        "protocol_implementation",
    )
    dataset = _object(root["dataset"], "dataset")
    identity = _object(root["identity"], "identity")
    if (
        not isinstance(artifact["wheel_filename"], str)
        or not artifact["wheel_filename"].endswith(".whl")
        or not isinstance(artifact["wheel_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", artifact["wheel_sha256"])
    ):
        raise QualityReportError("v4 performance artifact wheel identity is malformed")
    if artifact["wheel_sha256"] != expected_wheel_sha256:
        raise QualityReportError("v4 performance artifact wheel identity mismatch")
    if (
        expected_wheel_filename is not None
        and artifact["wheel_filename"] != expected_wheel_filename
    ):
        raise QualityReportError("v4 performance artifact wheel filename mismatch")
    if identity != {
        "profile": profile,
        "provider": _provider(root, profile),
        "source_git_sha": expected_source_sha,
        "wheel_sha256": expected_wheel_sha256,
        "dataset_sha256": expected_dataset_sha256,
        "manifest_sha256": expected_manifest_sha256,
    }:
        raise QualityReportError("v4 performance artifact identity mismatch")
    if dataset["id"] != expected_dataset_id or dataset["schema_version"] != 4:
        raise QualityReportError("v4 performance artifact dataset identity mismatch")
    if dataset != {
        "id": expected_dataset_id,
        "schema_id": "polis.quality-development-dataset",
        "schema_version": 4,
        "sha256": expected_dataset_sha256,
        "manifest_sha256": expected_manifest_sha256,
        "cases": 124,
        "source_snapshot_sha256": _SOURCE_SNAPSHOT_SHA256,
    }:
        raise QualityReportError("v4 performance artifact dataset identity mismatch")
    implementation = protocol_implementation
    if (
        not isinstance(implementation["overlay_applied"], bool)
        or not _is_sha256(implementation["runtime_performance_protocol_sha256"])
        or not _is_sha256(implementation["runtime_performance_worker_sha256"])
    ):
        raise QualityReportError("v4 performance protocol identity is malformed")
    if implementation["runtime_performance_protocol_sha256"] != binding.protocol_sha256:
        raise QualityReportError("v4 performance protocol identity mismatch")
    if implementation["runtime_performance_worker_sha256"] != binding.worker_sha256:
        raise QualityReportError("v4 performance worker identity mismatch")
    if implementation["overlay_applied"] is not False:
        raise QualityReportError(
            "v4 performance artifact must use the unmodified v2 protocol"
        )
    if binding.protocol_version != 2:
        raise QualityReportError("v4 performance artifact protocol version mismatch")
    _validate_environment(root["environment"])
    if root["morphology_provider"] != _provider(root, profile):
        raise QualityReportError("v4 performance provider identity mismatch")
    _validate_reproducibility(root["reproducibility"])
    _validate_performance(root["performance"], root["rss"])
    _validate_quality(root["quality"])
    return root


def _provider(root: dict[str, Any], profile: str) -> dict[str, str] | None:
    if profile == "default":
        return None
    if profile == "morphology":
        return _PROVIDER
    raise QualityReportError("v4 performance profile is unsupported")


def _object(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise QualityReportError(f"v4 performance {name} must be an object")
    return value


def _string(value: dict[str, Any], name: str) -> str:
    result = value.get(name)
    if not isinstance(result, str) or not result:
        raise QualityReportError(f"v4 performance {name} is malformed")
    return result


def _validate_environment(value: object) -> None:
    raw = _object(value, "environment")
    if set(raw) != {
        "package_version",
        "platform_machine",
        "platform_release",
        "platform_system",
        "python_version",
    } or not all(isinstance(item, str) and item for item in raw.values()):
        raise QualityReportError("v4 performance environment identity mismatch")


def _validate_reproducibility(value: object) -> None:
    raw = _object(value, "reproducibility")
    if set(raw) != {
        "warmup_repetitions",
        "measured_repetitions",
        "stable_repetitions",
        "findings_sha256",
    }:
        raise QualityReportError("v4 performance reproducibility fields mismatch")
    if (
        raw["warmup_repetitions"] != 1
        or raw["measured_repetitions"] != 5
        or raw["stable_repetitions"] != 5
    ):
        raise QualityReportError("v4 performance repetition identity mismatch")
    digest = raw["findings_sha256"]
    if not _is_sha256(digest):
        raise QualityReportError("v4 performance findings digest is malformed")


def _validate_performance(value: object, rss_value: object) -> None:
    performance = _exact_object(value, {"latency_ns", "throughput"}, "performance")
    latency = _exact_object(
        performance["latency_ns"],
        {"sample_count", "min", "mean", "p50", "p95", "max"},
        "latency_ns",
    )
    throughput = _exact_object(
        performance["throughput"],
        {
            "measured_cases",
            "measured_code_points",
            "total_duration_ns",
            "cases_per_second",
            "code_points_per_second",
        },
        "throughput",
    )
    rss = _exact_object(
        rss_value,
        {
            "harness_peak_rss_bytes",
            "worker_startup_rss_bytes",
            "worker_measurement_start_rss_bytes",
            "worker_peak_rss_bytes",
            "worker_measured_incremental_peak_rss_bytes",
        },
        "rss",
    )
    required_latency = {"sample_count", "min", "mean", "p50", "p95", "max"}
    if not all(_nonnegative_int(latency[k]) for k in required_latency):
        raise QualityReportError("v4 performance latency metrics are malformed")
    if latency["sample_count"] != 620 or not (
        latency["min"] <= latency["p50"] <= latency["p95"] <= latency["max"]
    ):
        raise QualityReportError("v4 performance latency identity mismatch")
    if (
        not _nonnegative_int(throughput["measured_cases"])
        or not _nonnegative_int(throughput["measured_code_points"])
        or not _nonnegative_int(throughput["total_duration_ns"])
        or not _nonnegative_number(throughput["cases_per_second"])
        or not _nonnegative_number(throughput["code_points_per_second"])
    ):
        raise QualityReportError("v4 performance throughput metrics are malformed")
    if (
        throughput["measured_cases"] != 620
        or throughput["measured_code_points"] <= 0
        or throughput["total_duration_ns"] <= 0
        or throughput["cases_per_second"] <= 0
        or throughput["code_points_per_second"] <= 0
    ):
        raise QualityReportError("v4 performance throughput identity mismatch")
    expected_cases_per_second = (
        throughput["measured_cases"] * 1_000_000_000 / throughput["total_duration_ns"]
    )
    expected_code_points_per_second = (
        throughput["measured_code_points"]
        * 1_000_000_000
        / throughput["total_duration_ns"]
    )
    if not math.isclose(
        float(throughput["cases_per_second"]), expected_cases_per_second, rel_tol=1e-9
    ) or not math.isclose(
        float(throughput["code_points_per_second"]),
        expected_code_points_per_second,
        rel_tol=1e-9,
    ):
        raise QualityReportError("v4 performance throughput arithmetic mismatch")
    if not all(_nonnegative_int(rss[k]) for k in rss):
        raise QualityReportError("v4 performance RSS metrics are malformed")
    if (
        rss["worker_startup_rss_bytes"] > rss["worker_measurement_start_rss_bytes"]
        or rss["worker_measurement_start_rss_bytes"] > rss["worker_peak_rss_bytes"]
        or rss["worker_measured_incremental_peak_rss_bytes"]
        != rss["worker_peak_rss_bytes"] - rss["worker_measurement_start_rss_bytes"]
    ):
        raise QualityReportError("v4 performance RSS arithmetic mismatch")


def _validate_quality(value: object) -> None:
    quality = _exact_object(
        value,
        {
            "precision",
            "recall",
            "f1",
            "span_accuracy",
            "correction_accuracy",
            "false_alarm_rate",
            "counts",
        },
        "quality",
    )
    counts = _exact_object(
        quality["counts"],
        {
            "expected_findings",
            "predicted_findings",
            "true_positives",
            "false_positives",
            "false_negatives",
            "span_matches",
            "correction_matches",
            "correct_cases",
            "alarmed_correct_cases",
        },
        "quality counts",
    )
    if not all(_nonnegative_int(counts[field]) for field in counts):
        raise QualityReportError("v4 performance quality counts are malformed")
    for field in (
        "precision",
        "recall",
        "f1",
        "span_accuracy",
        "correction_accuracy",
        "false_alarm_rate",
    ):
        if not _nonnegative_number(quality[field]) or quality[field] > 1:
            raise QualityReportError("v4 performance quality metrics are malformed")
    if (
        counts["expected_findings"]
        != counts["true_positives"] + counts["false_negatives"]
        or counts["predicted_findings"]
        != counts["true_positives"] + counts["false_positives"]
        or counts["correction_matches"] != counts["true_positives"]
        or counts["span_matches"]
        > min(counts["expected_findings"], counts["predicted_findings"])
        or counts["alarmed_correct_cases"] > counts["correct_cases"]
    ):
        raise QualityReportError("v4 performance quality arithmetic mismatch")


def _exact_object(value: object, fields: set[str], name: str) -> dict[str, Any]:
    raw = _object(value, name)
    if set(raw) != fields:
        raise QualityReportError(f"v4 performance {name} fields mismatch")
    return raw


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _nonnegative_number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and value >= 0
    )


__all__ = ["file_sha256", "load_runtime_performance_v2"]
