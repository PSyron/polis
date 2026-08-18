"""Deterministic quality and performance measurements for the active dataset."""

from __future__ import annotations

import hashlib
import json
import platform
import resource
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum

from polis.core import Finding
from polis.evaluation.dataset import EvaluationDataset
from polis.evaluation.metrics import BaselineResult, evaluate_baseline


@dataclass(frozen=True, slots=True)
class RunIdentity:
    """Installed artifact, analyzer, dataset schema, and host identity for one run."""

    analyzer: str
    artifact_sha256: str
    package_version: str
    python_version: str
    platform_system: str
    platform_release: str
    platform_machine: str
    dataset_schema_id: str
    dataset_schema_version: int
    manifest_schema_id: str
    manifest_schema_version: int
    manifest_sha256: str
    source_sha: str | None = None
    profile: RunProfile | None = None
    source_snapshot: tuple[dict[str, str], ...] | None = None


class InstallationProfile(StrEnum):
    DEFAULT = "default"
    MORPHOLOGY = "morphology"


@dataclass(frozen=True, slots=True)
class MorphologyProviderIdentity:
    provider: str
    package_version: str
    dictionary_id: str
    dictionary_notice_sha256: str


@dataclass(frozen=True, slots=True)
class RunProfile:
    id: InstallationProfile
    morphology_provider: MorphologyProviderIdentity | None
    planned_morphology_source_semantics: str
    planned_non_morphology_source_semantics: str


@dataclass(frozen=True, slots=True)
class LatencyMetrics:
    """Integer nanosecond latency distribution over measured analyzer calls."""

    sample_count: int
    min_ns: int
    mean_ns: int
    p50_ns: int
    p95_ns: int
    max_ns: int


@dataclass(frozen=True, slots=True)
class ThroughputMetrics:
    """Measured workload totals and rates derived from summed latency."""

    measured_cases: int
    measured_code_points: int
    total_duration_ns: int
    cases_per_second: float
    code_points_per_second: float


@dataclass(frozen=True, slots=True)
class ResourceMetrics:
    """Current-process resource measurements captured after the run."""

    peak_rss_bytes: int


@dataclass(frozen=True, slots=True)
class QualityProtocolResult:
    """Complete reproducible output from one quality protocol execution."""

    run_identity: RunIdentity
    dataset_id: str
    dataset_sha256: str
    warmup_repetitions: int
    measured_repetitions: int
    repetition_hashes: tuple[str, ...]
    baseline: BaselineResult
    latency: LatencyMetrics
    throughput: ThroughputMetrics
    resources: ResourceMetrics
    v4_diagnostics: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class UnsupportedRssPlatformError(Exception):
    """Raised when the host does not define a supported ``ru_maxrss`` unit."""

    platform_name: str

    def __str__(self) -> str:
        return f"peak RSS measurement is unsupported on platform: {self.platform_name}"


@dataclass(frozen=True, slots=True)
class NonDeterministicBaselineError(Exception):
    """Raised when measured repetitions produce different finding identities."""

    baseline_hash: str
    changed_hash: str
    repetition: int

    def __str__(self) -> str:
        return "baseline findings changed between measured repetitions"


def peak_rss_bytes() -> int:
    """Return current-process peak RSS in bytes on Darwin and Linux."""

    system = platform.system()
    if system != "Darwin" and system != "Linux":
        raise UnsupportedRssPlatformError(platform_name=system)
    raw_peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if system == "Darwin":
        return raw_peak_rss
    return raw_peak_rss * 1024


def run_quality_protocol(
    *,
    dataset: EvaluationDataset,
    analyzer: Callable[[str], tuple[Finding, ...]],
    run_identity: RunIdentity,
    warmup_repetitions: int,
    measured_repetitions: int,
    clock_ns: Callable[[], int] = time.perf_counter_ns,
    rss_probe: Callable[[], int] = peak_rss_bytes,
) -> QualityProtocolResult:
    """Measure deterministic analyzer quality, latency, throughput, and peak RSS."""

    for _ in range(warmup_repetitions):
        for case in dataset.cases:
            analyzer(case.text)

    durations_ns: list[int] = []
    repetition_hashes: list[str] = []
    first_findings: tuple[tuple[Finding, ...], ...] | None = None
    for repetition in range(measured_repetitions):
        measured_findings: list[tuple[Finding, ...]] = []
        for case in dataset.cases:
            started_ns = clock_ns()
            findings = tuple(analyzer(case.text))
            finished_ns = clock_ns()
            durations_ns.append(finished_ns - started_ns)
            measured_findings.append(findings)

        findings_by_case = tuple(measured_findings)
        repetition_hash = _findings_snapshot_sha256(dataset, findings_by_case)
        repetition_hashes.append(repetition_hash)
        if first_findings is None:
            first_findings = findings_by_case
        elif repetition_hash != repetition_hashes[0]:
            raise NonDeterministicBaselineError(
                baseline_hash=repetition_hashes[0],
                changed_hash=repetition_hash,
                repetition=repetition,
            )

    assert first_findings is not None
    baseline_findings = iter(first_findings)
    baseline = evaluate_baseline(
        dataset=dataset,
        analyzer=lambda _text: next(baseline_findings),
        run_label="quality-protocol",
        run_reference=run_identity.artifact_sha256,
        configuration=run_identity.analyzer,
    )
    total_duration_ns = sum(durations_ns)
    measured_cases = len(dataset.cases) * measured_repetitions
    measured_code_points = (
        sum(len(case.text) for case in dataset.cases) * measured_repetitions
    )
    return QualityProtocolResult(
        run_identity=run_identity,
        dataset_id=dataset.id,
        dataset_sha256=dataset.canonical_hash,
        warmup_repetitions=warmup_repetitions,
        measured_repetitions=measured_repetitions,
        repetition_hashes=tuple(repetition_hashes),
        baseline=baseline,
        latency=LatencyMetrics(
            sample_count=len(durations_ns),
            min_ns=min(durations_ns),
            mean_ns=total_duration_ns // len(durations_ns),
            p50_ns=_nearest_rank(durations_ns, 50),
            p95_ns=_nearest_rank(durations_ns, 95),
            max_ns=max(durations_ns),
        ),
        throughput=ThroughputMetrics(
            measured_cases=measured_cases,
            measured_code_points=measured_code_points,
            total_duration_ns=total_duration_ns,
            cases_per_second=_per_second(measured_cases, total_duration_ns),
            code_points_per_second=_per_second(measured_code_points, total_duration_ns),
        ),
        resources=ResourceMetrics(peak_rss_bytes=rss_probe()),
    )


def _nearest_rank(values: Sequence[int], percentile: int) -> int:
    ordered = sorted(values)
    rank = (percentile * len(ordered) + 99) // 100
    return ordered[rank - 1]


def _per_second(item_count: int, duration_ns: int) -> float:
    if duration_ns == 0:
        return 0.0
    return item_count * 1_000_000_000 / duration_ns


def _findings_snapshot_sha256(
    dataset: EvaluationDataset,
    findings_by_case: tuple[tuple[Finding, ...], ...],
) -> str:
    snapshot = [
        {"case_id": case.id, "finding_ids": [finding.id for finding in findings]}
        for case, findings in zip(dataset.cases, findings_by_case, strict=True)
    ]
    canonical = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(canonical).hexdigest()
