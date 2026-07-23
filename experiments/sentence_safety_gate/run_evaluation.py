"""Run the installed-package sentence correction release gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import venv
import zipfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import IO, Any, cast

from .gate import (
    EditCounts,
    FreezeInputs,
    GateConfig,
    RunnerObservation,
    SentenceCase,
    freeze_gate,
    frozen_input_hashes,
    gate_qualifies,
    load_development_sentences,
    load_gate_config,
    load_reserved_holdout_sentences,
    reserve_holdout_once,
    score_exact_edits,
    sha256_path,
    validate_privacy_safe_report,
    validate_runner_response,
    verify_frozen_gate,
)

_ROOT = Path(__file__).resolve().parents[2]
_RUNNER = _ROOT / "scripts" / "run_sentence_safety_case.py"
_GATE_MODULE = Path(__file__).with_name("gate.py")
_ANALYZER = _ROOT / "src" / "polis" / "analyzer.py"
_LT_ROOT = _ROOT / "third_party" / "languagetool-pl"
_LT_RUNNER = _LT_ROOT / "scripts" / "run_stdio.sh"
_LT_BRIDGE = (
    _LT_ROOT
    / "src"
    / "main"
    / "java"
    / "org"
    / "polis"
    / "languagetool"
    / "PolisStdioServer.java"
)
_LT_MANIFEST = _LT_ROOT / "manifest.json"
_LT_ARTIFACT = _LT_ROOT / "target" / "languagetool-pl-stdio-0.1.0-SNAPSHOT.jar"
_LT_DEPENDENCIES = _LT_ROOT / "target" / "dependency"
_PROXY_VARIABLES = (
    "ALL_PROXY",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "all_proxy",
    "http_proxy",
    "https_proxy",
    "no_proxy",
)
_FORBIDDEN_ARTIFACT_SUFFIXES = (
    ".bin",
    ".gguf",
    ".jar",
    ".mlx",
    ".onnx",
    ".pt",
    ".safetensors",
)
_REPORT_KEYS = frozenset(
    {
        "schema_version",
        "experiment_id",
        "configuration_sha256",
        "environment",
        "artifact_audit",
        "fallback",
        "development",
        "holdout",
        "decision",
    }
)
_ENVIRONMENT_KEYS = frozenset(
    {
        "python_version",
        "implementation",
        "machine",
        "operating_system",
        "platform_profile",
        "source_policy_version",
        "language_tool_version",
        "language_tool_upstream_commit",
        "language_tool_manifest_sha256",
        "language_tool_bridge_sha256",
        "language_tool_runner_sha256",
        "language_tool_artifact_sha256",
        "language_tool_dependencies_sha256",
        "model_calls_per_sentence",
    }
)
_ARTIFACT_AUDIT_KEYS = frozenset(
    {"wheel_sha256", "sdist_sha256", "wheel_members", "sdist_members", "qualified"}
)
_FALLBACK_KEYS = frozenset(
    {
        "qualified",
        "status",
        "automatic_sources",
        "reviewable_sources",
        "model_calls",
        "output_hash",
    }
)
_SPLIT_KEYS = frozenset(
    {
        "total_cases",
        "automatic",
        "reviewable",
        "structured_outcome_validity",
        "protected_automatic_changes",
        "protected_reviewable_findings",
        "categories",
        "sources",
        "performance",
        "case_evidence",
        "decision",
    }
)
_CHANNEL_KEYS = frozenset(
    {
        "proposed_edits",
        "true_positive_edits",
        "false_positive_edits",
        "false_negative_edits",
        "precision",
        "recall",
        "correction_accuracy",
    }
)
_CATEGORY_CHANNEL_KEYS = _CHANNEL_KEYS - {"correction_accuracy"}
_PERFORMANCE_KEYS = frozenset(
    {
        "cold_e2e_ms",
        "warm_in_process_p50_ms",
        "warm_in_process_p95_ms",
        "warm_e2e_p50_ms",
        "warm_e2e_p95_ms",
        "cases_per_second",
        "characters_per_second",
        "python_loaded_rss_bytes",
        "child_loaded_rss_bytes",
        "combined_loaded_rss_bytes",
        "python_peak_rss_bytes",
        "child_peak_rss_bytes",
        "combined_peak_rss_bytes",
        "swap_delta_bytes",
        "socket_count",
        "model_calls",
        "process_start_count",
        "stable_repetitions",
    }
)
_CASE_EVIDENCE_KEYS = frozenset(
    {
        "case_id",
        "stratum",
        "input_character_count",
        "automatic_edit_count",
        "reviewable_edit_count",
        "elapsed_ms",
        "e2e_elapsed_ms",
        "output_hash",
    }
)
_SOURCE_METRIC_KEYS = frozenset(
    {
        "proposed_edits",
        "true_positive_edits",
        "false_positive_edits",
        "false_negative_edits",
        "precision",
        "recall",
        "recall_denominator",
    }
)


@dataclass(frozen=True, slots=True)
class ArtifactAudit:
    wheel_sha256: str
    sdist_sha256: str
    wheel_members: int
    sdist_members: int
    qualified: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "wheel_sha256": self.wheel_sha256,
            "sdist_sha256": self.sdist_sha256,
            "wheel_members": self.wheel_members,
            "sdist_members": self.sdist_members,
            "qualified": self.qualified,
        }


@dataclass(frozen=True, slots=True)
class CaseRun:
    case: SentenceCase
    observation: RunnerObservation
    e2e_elapsed_ms: float
    output_hash: str


@dataclass(frozen=True, slots=True)
class PerformanceEvidence:
    cold_e2e_ms: float
    warm_in_process_p50_ms: float
    warm_in_process_p95_ms: float
    warm_e2e_p50_ms: float
    warm_e2e_p95_ms: float
    cases_per_second: float
    characters_per_second: float
    python_loaded_rss_bytes: int
    child_loaded_rss_bytes: int
    combined_loaded_rss_bytes: int
    python_peak_rss_bytes: int
    child_peak_rss_bytes: int
    combined_peak_rss_bytes: int
    swap_delta_bytes: int
    socket_count: int
    model_calls: int
    process_start_count: int
    stable_repetitions: int

    def as_dict(self) -> dict[str, int | float]:
        return {
            "cold_e2e_ms": self.cold_e2e_ms,
            "warm_in_process_p50_ms": self.warm_in_process_p50_ms,
            "warm_in_process_p95_ms": self.warm_in_process_p95_ms,
            "warm_e2e_p50_ms": self.warm_e2e_p50_ms,
            "warm_e2e_p95_ms": self.warm_e2e_p95_ms,
            "cases_per_second": self.cases_per_second,
            "characters_per_second": self.characters_per_second,
            "python_loaded_rss_bytes": self.python_loaded_rss_bytes,
            "child_loaded_rss_bytes": self.child_loaded_rss_bytes,
            "combined_loaded_rss_bytes": self.combined_loaded_rss_bytes,
            "python_peak_rss_bytes": self.python_peak_rss_bytes,
            "child_peak_rss_bytes": self.child_peak_rss_bytes,
            "combined_peak_rss_bytes": self.combined_peak_rss_bytes,
            "swap_delta_bytes": self.swap_delta_bytes,
            "socket_count": self.socket_count,
            "model_calls": self.model_calls,
            "process_start_count": self.process_start_count,
            "stable_repetitions": self.stable_repetitions,
        }


class InstalledRunnerSession:
    """One persistent runner using only the clean environment's Polis install."""

    def __init__(
        self,
        *,
        python: Path,
        runner: Path,
        vendored_stdio: Path,
        working_directory: Path,
        timeout_seconds: float,
    ) -> None:
        if not python.is_absolute() or not python.is_file():
            raise ValueError("installed Python executable is unavailable")
        if not runner.is_absolute() or not runner.is_file():
            raise ValueError("installed runner script is unavailable")
        if not vendored_stdio.is_absolute() or not vendored_stdio.is_file():
            raise ValueError("vendored stdio executable is unavailable")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("runner timeout must be positive and finite")
        working_directory.mkdir(parents=True, exist_ok=True)
        install_root = _installed_package_root(python, working_directory)
        environment = _offline_environment()
        command = (
            *_network_denial_prefix(),
            os.fspath(python),
            os.fspath(runner),
            "--vendored-stdio",
            os.fspath(vendored_stdio),
            "--expected-install-root",
            os.fspath(install_root),
            "--timeout-seconds",
            str(timeout_seconds),
        )
        self._process = subprocess.Popen(
            command,
            cwd=working_directory,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._timeout_seconds = timeout_seconds
        self._resource_stop = threading.Event()
        self._resource_lock = threading.Lock()
        self._python_peak_rss = 0
        self._child_peak_rss = 0
        self._resource_thread = threading.Thread(
            target=self._sample_resources,
            daemon=True,
        )
        self._resource_thread.start()

    @property
    def process_id(self) -> int:
        return self._process.pid

    def exchange(self, request_id: int, text: str) -> tuple[dict[str, Any], float]:
        stdin = self._process.stdin
        stdout = self._process.stdout
        if stdin is None or stdout is None:
            raise RuntimeError("installed runner pipes are unavailable")
        request = json.dumps(
            {
                "schema_version": 1,
                "request_id": request_id,
                "operation": "analyze_sentence",
                "text": text,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        started = time.perf_counter()
        stdin.write(request + "\n")
        stdin.flush()
        ready = _wait_readable(stdout, self._timeout_seconds)
        if not ready:
            raise TimeoutError("installed runner response timed out")
        raw = stdout.readline()
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if not raw:
            raise RuntimeError("installed runner ended without a response")
        try:
            payload: Any = json.loads(raw)
        except json.JSONDecodeError as error:
            raise ValueError("installed runner response is invalid JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("installed runner response must be an object")
        python_rss, child_rss = _resource_tree_snapshot(self.process_id)
        with self._resource_lock:
            self._python_peak_rss = max(self._python_peak_rss, python_rss)
            self._child_peak_rss = max(self._child_peak_rss, child_rss)
            payload.update(
                {
                    "python_rss_bytes": python_rss,
                    "child_rss_bytes": child_rss,
                    "combined_rss_bytes": python_rss + child_rss,
                    "python_peak_rss_bytes": self._python_peak_rss,
                    "child_peak_rss_bytes": self._child_peak_rss,
                    "combined_peak_rss_bytes": (
                        self._python_peak_rss + self._child_peak_rss
                    ),
                }
            )
        return cast(dict[str, Any], payload), elapsed_ms

    def close(self) -> None:
        self._resource_stop.set()
        self._resource_thread.join(timeout=1.0)
        stdin = self._process.stdin
        if stdin is not None and not stdin.closed:
            stdin.close()
        try:
            self._process.wait(timeout=self._timeout_seconds)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            try:
                self._process.wait(timeout=self._timeout_seconds)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=self._timeout_seconds)
        if self._process.returncode != 0:
            stderr = self._process.stderr
            if stderr is not None:
                stderr.read()
            raise RuntimeError("installed runner exited unsuccessfully")

    def _sample_resources(self) -> None:
        while not self._resource_stop.wait(0.01):
            try:
                python_rss, child_rss = _resource_tree_snapshot(self.process_id)
            except (OSError, subprocess.SubprocessError, ValueError):
                continue
            with self._resource_lock:
                self._python_peak_rss = max(self._python_peak_rss, python_rss)
                self._child_peak_rss = max(self._child_peak_rss, child_rss)

    def __enter__(self) -> InstalledRunnerSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def audit_release_artifacts(wheel: Path, sdist: Path) -> ArtifactAudit:
    """Reject release archives containing evaluation or optional runtime data."""

    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
        _audit_names(wheel_names)
        _audit_wheel_names(wheel_names)
        for name in wheel_names:
            with archive.open(name) as stream:
                _audit_private_stream(stream)
    with tarfile.open(sdist) as archive:
        sdist_names = archive.getnames()
        _audit_names(sdist_names)
        _audit_sdist_names(sdist_names)
        for member in archive.getmembers():
            if not member.isfile():
                continue
            tar_stream = archive.extractfile(member)
            if tar_stream is not None:
                _audit_private_stream(tar_stream)
    return ArtifactAudit(
        wheel_sha256=sha256_path(wheel),
        sdist_sha256=sha256_path(sdist),
        wheel_members=len(wheel_names),
        sdist_members=len(sdist_names),
        qualified=True,
    )


def install_artifact_offline(
    artifact: Path,
    destination: Path,
    *,
    build_backend_path: Path | None = None,
) -> Path:
    """Install an artifact without indexes or dependency resolution."""

    venv.EnvBuilder(with_pip=True, clear=False, symlinks=True).create(destination)
    python = _venv_python(destination)
    command = [
        os.fspath(python),
        "-m",
        "pip",
        "install",
        "--no-index",
        "--no-deps",
        "--disable-pip-version-check",
    ]
    environment = _offline_environment()
    if artifact.name.endswith(".tar.gz"):
        if build_backend_path is None:
            raise ValueError(
                "sdist installation requires an offline build backend path"
            )
        command.append("--no-build-isolation")
        environment["PYTHONPATH"] = os.fspath(build_backend_path)
    command.append(os.fspath(artifact))
    completed = subprocess.run(
        command,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != 0:
        raise RuntimeError("offline artifact installation failed")
    return python


def summarize_split(
    runs: tuple[CaseRun, ...], performance: PerformanceEvidence
) -> dict[str, object]:
    """Score validated runs without exposing source or exact edit material."""

    if not runs:
        raise ValueError("release split must contain at least one run")
    automatic_counts = EditCounts(0, 0, 0)
    reviewable_counts = EditCounts(0, 0, 0)
    automatic_changed = automatic_exact = 0
    reviewable_changed = reviewable_exact = 0
    protected_automatic = protected_reviewable = 0
    sources: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "proposed_edits": 0,
            "true_positive_edits": 0,
            "false_positive_edits": 0,
        }
    )
    categories: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "gold_edits": 0,
            "automatic_true_positive_edits": 0,
            "automatic_false_positive_edits": 0,
            "reviewable_true_positive_edits": 0,
            "reviewable_false_positive_edits": 0,
        }
    )
    case_evidence: list[dict[str, object]] = []
    for run in runs:
        gold = run.case.gold_edits
        automatic = score_exact_edits(gold, run.observation.automatic_edits)
        reviewable = score_exact_edits(gold, run.observation.reviewable_edits)
        automatic_counts = _plus_counts(automatic_counts, automatic)
        reviewable_counts = _plus_counts(reviewable_counts, reviewable)
        if run.observation.automatic_edits:
            automatic_changed += 1
            automatic_exact += (
                run.observation.corrected_text == run.case.expected_output
            )
        if run.observation.reviewable_edits:
            reviewable_changed += 1
            reviewable_exact += (
                run.observation.selected_text == run.case.expected_output
            )
        if run.case.protected_negative:
            protected_automatic += bool(run.observation.automatic_edits)
            protected_reviewable += len(run.observation.reviewable_edits)

        gold_keys = {edit.exact_key for edit in gold}
        for edit in gold:
            categories[edit.category]["gold_edits"] += 1
        for channel, edits in (
            ("automatic", run.observation.automatic_edits),
            ("reviewable", run.observation.reviewable_edits),
        ):
            for observed in edits:
                source_bucket = sources[observed.source]
                source_bucket["proposed_edits"] += 1
                if observed.exact_key in gold_keys:
                    source_bucket["true_positive_edits"] += 1
                    gold_category = next(
                        item.category
                        for item in gold
                        if item.exact_key == observed.exact_key
                    )
                    categories[gold_category][f"{channel}_true_positive_edits"] += 1
                else:
                    source_bucket["false_positive_edits"] += 1
                    categories[observed.category][
                        f"{channel}_false_positive_edits"
                    ] += 1
        case_evidence.append(
            {
                "case_id": run.case.case_id,
                "stratum": run.case.stratum,
                "input_character_count": len(run.case.source),
                "automatic_edit_count": len(run.observation.automatic_edits),
                "reviewable_edit_count": len(run.observation.reviewable_edits),
                "output_hash": run.output_hash,
                "elapsed_ms": run.observation.elapsed_ms,
                "e2e_elapsed_ms": run.e2e_elapsed_ms,
            }
        )

    automatic_metrics = _channel_metrics(
        automatic_counts,
        correction_accuracy=(
            automatic_exact / automatic_changed if automatic_changed else None
        ),
    )
    reviewable_metrics = _channel_metrics(
        reviewable_counts,
        correction_accuracy=(
            reviewable_exact / reviewable_changed if reviewable_changed else None
        ),
    )
    total_gold = sum(len(run.case.gold_edits) for run in runs)
    category_metrics: dict[str, object] = {}
    for category, values in sorted(categories.items()):
        gold_count = values["gold_edits"]
        channel_values: dict[str, object] = {"gold_edits": gold_count}
        for channel in ("automatic", "reviewable"):
            true_positive = values[f"{channel}_true_positive_edits"]
            false_positive = values[f"{channel}_false_positive_edits"]
            channel_values[channel] = _edit_metrics(
                EditCounts(
                    true_positive=true_positive,
                    false_positive=false_positive,
                    false_negative=max(0, gold_count - true_positive),
                )
            )
        category_metrics[category] = channel_values
    source_metrics: dict[str, object] = {}
    for source_name, source_values in sorted(sources.items()):
        counts = EditCounts(
            true_positive=source_values["true_positive_edits"],
            false_positive=source_values["false_positive_edits"],
            false_negative=max(
                0, total_gold - source_values["true_positive_edits"]
            ),
        )
        source_metrics[source_name] = {
            **_edit_metrics(counts),
            "recall_denominator": "all_gold_edits",
        }
    return {
        "total_cases": len(runs),
        "automatic": automatic_metrics,
        "reviewable": reviewable_metrics,
        "structured_outcome_validity": 1.0,
        "protected_automatic_changes": protected_automatic,
        "protected_reviewable_findings": protected_reviewable,
        "categories": category_metrics,
        "sources": source_metrics,
        "performance": performance.as_dict(),
        "case_evidence": case_evidence,
    }


def run_installed_cases(
    cases: tuple[SentenceCase, ...],
    session: Any,
    config: GateConfig,
    *,
    repetitions: int,
) -> tuple[tuple[CaseRun, ...], PerformanceEvidence]:
    """Run and validate repeated cases through one installed runner session."""

    if not cases:
        raise ValueError("installed evaluation requires sentence cases")
    if repetitions < config.gates.required_stable_repetitions:
        raise ValueError("installed evaluation has too few stability repetitions")
    swap_before = _swap_used_bytes()
    first_runs: list[CaseRun] = []
    hashes_by_case: dict[str, list[str]] = defaultdict(list)
    in_process_latencies: list[float] = []
    e2e_latencies: list[float] = []
    python_rss = child_rss = combined_rss = 0
    python_peak_rss = child_peak_rss = combined_peak_rss = 0
    model_calls = process_starts = sockets = 0
    request_id = 0
    for repetition in range(repetitions):
        for case in cases:
            request_id += 1
            raw, e2e_elapsed_ms = session.exchange(request_id, case.source)
            observation = validate_runner_response(case.source, raw, config=config)
            output_hash = _observation_hash(observation)
            hashes_by_case[case.case_id].append(output_hash)
            if repetition == 0:
                first_runs.append(
                    CaseRun(case, observation, e2e_elapsed_ms, output_hash)
                )
            in_process_latencies.append(observation.elapsed_ms)
            e2e_latencies.append(e2e_elapsed_ms)
            python_rss = max(python_rss, observation.python_rss_bytes)
            child_rss = max(child_rss, observation.child_rss_bytes)
            combined_rss = max(combined_rss, observation.combined_rss_bytes)
            python_peak_rss = max(python_peak_rss, observation.python_peak_rss_bytes)
            child_peak_rss = max(child_peak_rss, observation.child_peak_rss_bytes)
            combined_peak_rss = max(
                combined_peak_rss, observation.combined_peak_rss_bytes
            )
            model_calls += observation.model_calls
            process_starts = max(process_starts, observation.process_start_count)
            sockets = max(sockets, _socket_count_tree(session.process_id))
    unstable = [
        case_id
        for case_id, hashes in hashes_by_case.items()
        if len(hashes) != repetitions or len(set(hashes)) != 1
    ]
    if unstable:
        raise ValueError("installed sentence output is not stable across repetitions")
    warm_in_process = in_process_latencies[1:] or in_process_latencies
    warm_e2e = e2e_latencies[1:] or e2e_latencies
    total_seconds = sum(e2e_latencies) / 1000.0
    samples = len(e2e_latencies)
    characters = sum(len(case.source) for case in cases) * repetitions
    performance = PerformanceEvidence(
        cold_e2e_ms=e2e_latencies[0],
        warm_in_process_p50_ms=median(warm_in_process),
        warm_in_process_p95_ms=_percentile(warm_in_process, 0.95),
        warm_e2e_p50_ms=median(warm_e2e),
        warm_e2e_p95_ms=_percentile(warm_e2e, 0.95),
        cases_per_second=samples / total_seconds if total_seconds else 0.0,
        characters_per_second=characters / total_seconds if total_seconds else 0.0,
        python_loaded_rss_bytes=python_rss,
        child_loaded_rss_bytes=child_rss,
        combined_loaded_rss_bytes=combined_rss,
        python_peak_rss_bytes=python_peak_rss,
        child_peak_rss_bytes=child_peak_rss,
        combined_peak_rss_bytes=combined_peak_rss,
        swap_delta_bytes=max(0, _swap_used_bytes() - swap_before),
        socket_count=sockets,
        model_calls=model_calls,
        process_start_count=process_starts,
        stable_repetitions=repetitions,
    )
    return tuple(first_runs), performance


def _observation_hash(observation: RunnerObservation) -> str:
    payload = {
        "analysis_finding_ids": observation.analysis_finding_ids,
        "automatic": [
            (*item.exact_key, item.category, item.source, item.finding_id)
            for item in observation.automatic_edits
        ],
        "reviewable": [
            (*item.exact_key, item.category, item.source, item.finding_id)
            for item in observation.reviewable_edits
        ],
        "corrected_text": observation.corrected_text,
        "selected_text": observation.selected_text,
        "suggestion_outcomes": observation.suggestion_outcomes,
        "model_calls": observation.model_calls,
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(1, math.ceil(len(ordered) * quantile)) - 1]


def _swap_used_bytes() -> int:
    completed = subprocess.run(
        ("sysctl", "-n", "vm.swapusage"),
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    if completed.returncode != 0:
        raise RuntimeError("swap measurement is unavailable")
    match = re.search(r"used = ([0-9.]+)([KMG])", completed.stdout)
    if match is None:
        raise RuntimeError("swap measurement has an unsupported shape")
    multiplier = {"K": 1_024, "M": 1_048_576, "G": 1_073_741_824}[match.group(2)]
    return round(float(match.group(1)) * multiplier)


def _socket_count_tree(parent_pid: int) -> int:
    lsof = shutil.which("lsof")
    if lsof is None:
        raise RuntimeError("socket audit requires lsof")
    pids = {parent_pid}
    completed = subprocess.run(
        ("ps", "-axo", "pid=,ppid="),
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    relationships: list[tuple[int, int]] = []
    for line in completed.stdout.splitlines():
        columns = line.split()
        if len(columns) == 2:
            relationships.append((int(columns[0]), int(columns[1])))
    changed = True
    while changed:
        changed = False
        for pid, ppid in relationships:
            if ppid in pids and pid not in pids:
                pids.add(pid)
                changed = True
    count = 0
    for pid in pids:
        result = subprocess.run(
            (lsof, "-nP", "-a", "-p", str(pid), "-i"),
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.stderr.strip() or result.returncode not in {0, 1}:
            raise RuntimeError("socket audit failed")
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        if result.returncode == 0 and len(lines) < 2:
            raise RuntimeError("socket audit returned incomplete evidence")
        if result.returncode == 1 and lines:
            raise RuntimeError("socket audit returned inconsistent evidence")
        count += max(0, len(lines) - 1) if lines else 0
    return count


def _resource_tree_snapshot(parent_pid: int) -> tuple[int, int]:
    completed = subprocess.run(
        ("/bin/ps", "-axo", "pid=,ppid=,rss="),
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
    )
    records: dict[int, tuple[int, int]] = {}
    for line in completed.stdout.splitlines():
        columns = line.split()
        if len(columns) == 3:
            pid, ppid, rss_kib = (int(value) for value in columns)
            records[pid] = (ppid, rss_kib * 1024)
    descendants = {parent_pid}
    changed = True
    while changed:
        changed = False
        for pid, (ppid, _) in records.items():
            if ppid in descendants and pid not in descendants:
                descendants.add(pid)
                changed = True
    python_rss = records.get(parent_pid, (0, 0))[1]
    child_rss = sum(
        records[pid][1] for pid in descendants - {parent_pid} if pid in records
    )
    return python_rss, child_rss


def _channel_metrics(
    counts: EditCounts,
    *,
    correction_accuracy: float | None,
) -> dict[str, int | float | None]:
    return {
        **_edit_metrics(counts),
        "correction_accuracy": correction_accuracy,
    }


def _edit_metrics(counts: EditCounts) -> dict[str, int | float | None]:
    return {
        "proposed_edits": counts.proposed,
        "true_positive_edits": counts.true_positive,
        "false_positive_edits": counts.false_positive,
        "false_negative_edits": counts.false_negative,
        "precision": counts.precision,
        "recall": counts.recall,
    }


def _plus_counts(left: EditCounts, right: EditCounts) -> EditCounts:
    return EditCounts(
        left.true_positive + right.true_positive,
        left.false_positive + right.false_positive,
        left.false_negative + right.false_negative,
    )


def _audit_names(names: Sequence[str]) -> None:
    lowered = tuple(name.lower() for name in names)
    forbidden_fragments = (
        "polish_correction_corpus_v3.json",
        "polish_correction_corpus_v3.xml",
        "polish_correction_safety_corpus_v1.json",
        "polish_correction_safety_corpus_v1.xml",
        "experiments/sentence_safety_gate/frozen_gate.json",
        "experiments/sentence_safety_gate/holdout.started",
        "experiments/sentence_safety_gate/report.json",
        "target/dependency",
        "/.cache/",
        "__pycache__",
    )
    if any(fragment in name for name in lowered for fragment in forbidden_fragments):
        raise ValueError("distribution contains evaluation or cache data")
    if any(name.endswith(_FORBIDDEN_ARTIFACT_SUFFIXES) for name in lowered):
        raise ValueError("distribution contains model or Java runtime products")


def _audit_wheel_names(names: Sequence[str]) -> None:
    for name in names:
        first = name.split("/", 1)[0]
        if first != "polis" and not first.endswith(".dist-info"):
            raise ValueError(f"unexpected wheel member: {name}")


def _audit_sdist_names(names: Sequence[str]) -> None:
    allowed = {
        ".gitattributes",
        ".github",
        ".gitignore",
        "AGENTS.md",
        "CHANGELOG.md",
        "LICENSE",
        "PKG-INFO",
        "PROMPT.md",
        "README.md",
        "data",
        "docs",
        "examples",
        "experiments",
        "pyproject.toml",
        "scripts",
        "src",
        "tests",
        "uv.lock",
    }
    roots = {name.split("/", 1)[0] for name in names if name}
    if len(roots) != 1:
        raise ValueError("sdist must have exactly one archive root")
    root = next(iter(roots))
    for name in names:
        relative = name.removeprefix(root + "/")
        if not relative:
            continue
        first = relative.split("/", 1)[0]
        if first not in allowed:
            raise ValueError(f"unexpected sdist member: {name}")


def _audit_private_stream(stream: IO[bytes]) -> None:
    home = os.fspath(Path.home()).encode("utf-8")
    carry = b""
    while chunk := stream.read(65_536):
        payload = carry + chunk
        if home in payload:
            raise ValueError("distribution contains a private home path")
        carry = payload[-max(0, len(home) - 1) :]


def _network_denial_prefix() -> tuple[str, ...]:
    release_platform_profile()
    sandbox = Path("/usr/bin/sandbox-exec")
    if not sandbox.is_file():
        raise RuntimeError("release evaluation requires macOS network sandboxing")
    return (
        os.fspath(sandbox),
        "-p",
        "(version 1)(allow default)(deny network*)",
        "--",
    )


def _validate_vendored_stdio(path: Path, config: GateConfig) -> Path:
    resolved = path.resolve()
    if resolved != _LT_RUNNER.resolve():
        raise ValueError("vendored stdio must be the pinned runner")
    if sha256_path(resolved) != config.language_tool["runner_sha256"]:
        raise ValueError("pinned runner hash mismatch")
    return resolved


def _installed_package_root(python: Path, cwd: Path) -> Path:
    completed = subprocess.run(
        (
            os.fspath(python),
            "-c",
            "import pathlib, polis; "
            "print(pathlib.Path(polis.__file__).resolve().parents[1])",
        ),
        cwd=cwd,
        env=_offline_environment(),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError("installed Polis package is unavailable")
    return Path(completed.stdout.strip())


def _offline_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PIP_NO_INDEX"] = "1"
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    for name in _PROXY_VARIABLES:
        environment.pop(name, None)
    return environment


def _venv_python(destination: Path) -> Path:
    directory = destination / ("Scripts" if os.name == "nt" else "bin")
    for name in ("python", "python3", "python.exe"):
        candidate = directory / name
        if candidate.is_file():
            return candidate.absolute()
    raise RuntimeError("virtual environment Python executable is unavailable")


def _wait_readable(stream: IO[Any], timeout_seconds: float) -> bool:
    import select

    ready, _, _ = select.select((stream,), (), (), timeout_seconds)
    return bool(ready)


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--development", action="store_true")
    mode.add_argument("--holdout", action="store_true")
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--verify-development", action="store_true")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("config.json"),
    )
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--vendored-stdio", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--frozen", type=Path)
    parser.add_argument("--holdout-marker", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    arguments = parser.parse_args(argv)
    if arguments.development and (
        arguments.output is None or arguments.freeze is None
    ):
        parser.error("--development requires --output and --freeze")
    if arguments.holdout and (
        arguments.output is None
        or arguments.frozen is None
        or arguments.holdout_marker is None
    ):
        parser.error(
            "--holdout requires --output, --frozen, and --holdout-marker"
        )
    if arguments.verify_development and (
        arguments.output is None or arguments.freeze is None
    ):
        parser.error("--verify-development requires --output and --freeze")
    return arguments


def release_platform_profile(
    system: str | None = None, machine: str | None = None
) -> str:
    """Return the only platform profile whose evidence #76 can qualify."""

    resolved_system = platform.system() if system is None else system
    resolved_machine = platform.machine() if machine is None else machine
    if (resolved_system, resolved_machine.lower()) != ("Darwin", "arm64"):
        raise RuntimeError(
            "this platform does not qualify the macos-arm64-v1 release profile"
        )
    return "macos-arm64-v1"


def preflight_release_capabilities() -> None:
    """Prove every platform-native evidence primitive before holdout reservation."""

    release_platform_profile()
    _sandbox_capability_probe()
    _swap_used_bytes()
    with socket.socket() as probe_socket:
        probe_socket.bind(("127.0.0.1", 0))
        probe_socket.listen(1)
        if _socket_count_tree(os.getpid()) < 1:
            raise RuntimeError("socket visibility preflight failed")
    python_rss, child_rss = _resource_tree_snapshot(os.getpid())
    if python_rss <= 0 or child_rss < 0:
        raise RuntimeError("release RSS measurement preflight failed")
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, b"x")
        with os.fdopen(read_fd, "rb") as stream:
            read_fd = -1
            if not _wait_readable(stream, 1.0) or stream.read(1) != b"x":
                raise RuntimeError("release pipe readiness preflight failed")
    finally:
        if read_fd >= 0:
            os.close(read_fd)
        os.close(write_fd)


def _sandbox_capability_probe() -> None:
    code = (
        "import socket,subprocess,sys\n"
        "subprocess.run((sys.executable, '-c', 'pass'), check=True)\n"
        "candidate = socket.socket()\n"
        "try:\n"
        " candidate.bind(('127.0.0.1', 0))\n"
        "except PermissionError:\n"
        " sys.exit(0)\n"
        "finally:\n"
        " candidate.close()\n"
        "sys.exit(2)\n"
    )
    completed = subprocess.run(
        (*_network_denial_prefix(), sys.executable, "-c", code),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        raise RuntimeError("sandbox capability probe failed")


def authorize_holdout(
    *,
    prior_report: Mapping[str, object],
    config: GateConfig,
    frozen_path: Path,
    marker_path: Path,
    inputs: FreezeInputs,
) -> None:
    """Validate frozen development evidence before atomically reserving holdout."""

    validate_privacy_safe_report(prior_report)
    _validate_development_report(prior_report, config, inputs)
    verify_frozen_gate(
        frozen_path,
        inputs,
        development_report=prior_report,
    )
    reserve_holdout_once(
        frozen_path,
        marker_path,
        inputs,
        development_report=prior_report,
    )


def authorize_and_load_holdout(
    *,
    prior_report: Mapping[str, object],
    config: GateConfig,
    frozen_path: Path,
    marker_path: Path,
    inputs: FreezeInputs,
    corpus_path: Path,
) -> tuple[SentenceCase, ...]:
    """Preflight, reserve, and only then materialize the one-shot holdout."""

    preflight_release_capabilities()
    authorize_holdout(
        prior_report=prior_report,
        config=config,
        frozen_path=frozen_path,
        marker_path=marker_path,
        inputs=inputs,
    )
    return load_reserved_holdout_sentences(
        corpus_path,
        marker_path,
        frozen_path,
        inputs,
    )


def _validate_development_report(
    report: Mapping[str, object], config: GateConfig, inputs: FreezeInputs
) -> None:
    _closed_keys(report, _REPORT_KEYS, "development report schema")
    if report["schema_version"] != 1 or report["experiment_id"] != config.experiment_id:
        raise ValueError("development report schema identity mismatch")
    hashes = frozen_input_hashes(inputs)
    if report["configuration_sha256"] != hashes.get("configuration_sha256"):
        raise ValueError("development report configuration identity mismatch")
    if report["holdout"] is not None or report["decision"] != {
        "qualified": False,
        "scope": "sentence_only",
    }:
        raise ValueError("development report schema decision mismatch")

    environment = _closed_mapping(
        report["environment"], _ENVIRONMENT_KEYS, "development environment schema"
    )
    expected_environment = {
        "source_policy_version": config.source_policy_version,
        "language_tool_version": config.language_tool["version"],
        "language_tool_upstream_commit": config.language_tool["upstream_commit"],
        "language_tool_manifest_sha256": config.language_tool["manifest_sha256"],
        "language_tool_bridge_sha256": config.language_tool["bridge_sha256"],
        "language_tool_runner_sha256": config.language_tool["runner_sha256"],
        "language_tool_artifact_sha256": config.language_tool["artifact_sha256"],
        "language_tool_dependencies_sha256": config.language_tool[
            "dependencies_sha256"
        ],
    }
    if any(environment[key] != value for key, value in expected_environment.items()):
        raise ValueError("development report runtime identity mismatch")
    if environment["platform_profile"] != "macos-arm64-v1":
        raise ValueError("development report platform identity mismatch")

    audit = _closed_mapping(
        report["artifact_audit"], _ARTIFACT_AUDIT_KEYS, "artifact audit schema"
    )
    if (
        audit["qualified"] is not True
        or audit["wheel_sha256"] != hashes.get("wheel_sha256")
        or audit["sdist_sha256"] != hashes.get("sdist_sha256")
    ):
        raise ValueError("development report artifact identity mismatch")
    fallback = _closed_mapping(
        report["fallback"], _FALLBACK_KEYS, "fallback evidence schema"
    )
    if (
        fallback["qualified"] is not True
        or fallback["status"] != "complete"
        or fallback["model_calls"] != config.gates.required_model_calls
    ):
        raise ValueError("development fallback did not qualify")

    development = _closed_mapping(
        report["development"], _SPLIT_KEYS, "development split schema"
    )
    _closed_mapping(development["automatic"], _CHANNEL_KEYS, "automatic schema")
    _closed_mapping(development["reviewable"], _CHANNEL_KEYS, "reviewable schema")
    _closed_mapping(development["performance"], _PERFORMANCE_KEYS, "performance schema")
    _validate_variable_metrics(development)
    if development["decision"] != {"qualified": True} or not gate_qualifies(
        development, config
    ):
        raise ValueError("development sentence gate did not qualify")


def _validate_variable_metrics(development: Mapping[str, object]) -> None:
    categories = _mapping_object(development["categories"], "category schema")
    for category in categories.values():
        item = _closed_mapping(
            category,
            frozenset({"gold_edits", "automatic", "reviewable"}),
            "category schema",
        )
        _closed_mapping(item["automatic"], _CATEGORY_CHANNEL_KEYS, "category schema")
        _closed_mapping(item["reviewable"], _CATEGORY_CHANNEL_KEYS, "category schema")
    sources = _mapping_object(development["sources"], "source schema")
    for source in sources.values():
        _closed_mapping(source, _SOURCE_METRIC_KEYS, "source schema")
    evidence = development["case_evidence"]
    if not isinstance(evidence, list):
        raise ValueError("case evidence schema must be a list")
    for item in evidence:
        _closed_mapping(item, _CASE_EVIDENCE_KEYS, "case evidence schema")


def _mapping_object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _closed_mapping(
    value: object, expected: frozenset[str], label: str
) -> dict[str, Any]:
    mapping = _mapping_object(value, label)
    _closed_keys(mapping, expected, label)
    return mapping


def _closed_keys(
    value: Mapping[str, object], expected: frozenset[str], label: str
) -> None:
    if set(value) != expected:
        raise ValueError(f"{label} must contain exactly the frozen keys")


def run_prepared_split(
    *,
    cases: tuple[SentenceCase, ...] | None,
    prior_report: Mapping[str, object] | None,
    config: GateConfig,
    freeze_inputs: FreezeInputs,
    frozen_path: Path | None,
    marker_path: Path | None,
    corpus_path: Path,
    wheel: Path,
    sdist: Path,
    vendored_stdio: Path,
    timeout_seconds: float,
) -> tuple[
    tuple[SentenceCase, ...],
    tuple[CaseRun, ...],
    PerformanceEvidence,
    dict[str, object],
]:
    """Complete reversible setup before a possible holdout reservation."""

    with tempfile.TemporaryDirectory(prefix="polis-sentence-safety-") as raw_temp:
        temporary = Path(raw_temp)
        wheel_python = install_artifact_offline(wheel, temporary / "wheel-install")
        backend_path = _build_backend_path()
        sdist_python = install_artifact_offline(
            sdist,
            temporary / "sdist-install",
            build_backend_path=backend_path,
        )
        _installed_smoke(sdist_python, temporary / "sdist-smoke")
        fallback = _fallback_evidence(
            wheel_python,
            temporary,
            config,
            timeout_seconds=timeout_seconds,
        )
        with InstalledRunnerSession(
            python=wheel_python,
            runner=_RUNNER,
            vendored_stdio=vendored_stdio,
            working_directory=temporary / "evaluation",
            timeout_seconds=timeout_seconds,
        ) as session:
            selected_cases = cases
            if selected_cases is None:
                if (
                    prior_report is None
                    or frozen_path is None
                    or marker_path is None
                ):
                    raise ValueError("holdout authorization inputs are unavailable")
                selected_cases = authorize_and_load_holdout(
                    prior_report=prior_report,
                    config=config,
                    frozen_path=frozen_path,
                    marker_path=marker_path,
                    inputs=freeze_inputs,
                    corpus_path=corpus_path,
                )
            runs, performance = run_installed_cases(
                selected_cases,
                session,
                config,
                repetitions=config.gates.required_stable_repetitions,
            )
    return selected_cases, runs, performance, fallback


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    release_platform_profile()
    config = load_gate_config(arguments.config)
    wheel, sdist = _distribution_paths(arguments.dist)
    audit = audit_release_artifacts(wheel, sdist)
    _validate_frozen_runtime(config)
    vendored_stdio = _validate_vendored_stdio(arguments.vendored_stdio, config)
    freeze_inputs = _freeze_inputs(arguments.config, wheel, sdist)

    if arguments.preflight:
        preflight_release_capabilities()
        print("sentence safety preflight qualified")
        return 0

    if arguments.verify_development:
        assert arguments.output is not None
        assert arguments.freeze is not None
        verified_report = cast(
            dict[str, Any],
            validate_privacy_safe_report(
                json.loads(arguments.output.read_text(encoding="utf-8"))
            ),
        )
        _validate_development_report(verified_report, config, freeze_inputs)
        verify_frozen_gate(
            arguments.freeze,
            freeze_inputs,
            development_report=verified_report,
        )
        print(arguments.output)
        return 0

    prior_report: dict[str, Any] | None = None
    if arguments.holdout:
        assert arguments.output is not None
        if not arguments.output.is_file():
            raise ValueError("development report is unavailable")
        prior_report = cast(
            dict[str, Any],
            validate_privacy_safe_report(
                json.loads(arguments.output.read_text(encoding="utf-8"))
            ),
        )
        cases: tuple[SentenceCase, ...] | None = None
    else:
        cases = load_development_sentences(_ROOT / config.corpus_xml_path)

    cases, runs, performance, fallback = run_prepared_split(
        cases=cases,
        prior_report=prior_report,
        config=config,
        freeze_inputs=freeze_inputs,
        frozen_path=arguments.frozen,
        marker_path=arguments.holdout_marker,
        corpus_path=_ROOT / config.corpus_json_path,
        wheel=wheel,
        sdist=sdist,
        vendored_stdio=vendored_stdio,
        timeout_seconds=arguments.timeout_seconds,
    )

    summary = summarize_split(runs, performance)
    qualified = bool(fallback["qualified"] and gate_qualifies(summary, config))
    split_payload = {**summary, "decision": {"qualified": qualified}}
    if arguments.development:
        report: dict[str, object] = {
            "schema_version": 1,
            "experiment_id": config.experiment_id,
            "configuration_sha256": sha256_path(arguments.config),
            "environment": _environment_payload(config, performance, len(cases)),
            "artifact_audit": audit.as_dict(),
            "fallback": fallback,
            "development": split_payload,
            "holdout": None,
            "decision": {"qualified": False, "scope": "sentence_only"},
        }
    else:
        if prior_report is None:
            raise AssertionError("prior development report is unavailable")
        report = prior_report
        report["holdout"] = split_payload
        report["decision"] = {
            "qualified": qualified,
            "scope": "sentence_only",
        }
    validate_privacy_safe_report(report)
    if arguments.development and qualified:
        assert arguments.freeze is not None
        freeze_gate(
            freeze_inputs,
            arguments.freeze,
            development_report=report,
        )
    assert arguments.output is not None
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(arguments.output)
    return 0 if qualified else 1


def _distribution_paths(dist: Path) -> tuple[Path, Path]:
    wheels = sorted(dist.glob("*.whl"))
    sdists = sorted(dist.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("distribution directory must contain one wheel and one sdist")
    return wheels[0], sdists[0]


def _validate_frozen_runtime(config: GateConfig) -> None:
    expected = config.language_tool
    files = {
        "manifest_sha256": _LT_MANIFEST,
        "bridge_sha256": _LT_BRIDGE,
        "runner_sha256": _LT_RUNNER,
        "artifact_sha256": _LT_ARTIFACT,
    }
    for name, path in files.items():
        if not path.is_file() or sha256_path(path) != expected[name]:
            raise ValueError(f"LanguageTool {name} mismatch")
    if _directory_sha256(_LT_DEPENDENCIES) != expected["dependencies_sha256"]:
        raise ValueError("LanguageTool dependencies_sha256 mismatch")
    if sha256_path(_ROOT / config.corpus_json_path) != config.corpus_sha256:
        raise ValueError("corpus JSON hash mismatch")
    if sha256_path(_ROOT / config.corpus_xml_path) != config.corpus_xml_sha256:
        raise ValueError("corpus XML hash mismatch")


def _directory_sha256(path: Path) -> str:
    if not path.is_dir():
        raise ValueError("runtime dependency directory is unavailable")
    records = [
        (item.relative_to(path).as_posix(), sha256_path(item))
        for item in sorted(path.rglob("*"))
        if item.is_file()
    ]
    if not records:
        raise ValueError("runtime dependency directory is empty")
    return hashlib.sha256(
        json.dumps(records, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _freeze_inputs(config: Path, wheel: Path, sdist: Path) -> FreezeInputs:
    return FreezeInputs(
        files={
            "configuration": config,
            "evaluator": Path(__file__),
            "gate": _GATE_MODULE,
            "installed_runner": _RUNNER,
            "source_policy": _ANALYZER,
            "corpus_json": _ROOT
            / (
                "tests/fixtures/evaluation/"
                "polish_correction_safety_corpus_v1.json"
            ),
            "corpus_xml": _ROOT
            / (
                "tests/fixtures/evaluation/"
                "polish_correction_safety_corpus_v1.xml"
            ),
            "language_tool_bridge": _LT_BRIDGE,
            "language_tool_runner": _LT_RUNNER,
            "language_tool_manifest": _LT_MANIFEST,
            "language_tool_artifact": _LT_ARTIFACT,
            "wheel": wheel,
            "sdist": sdist,
        },
        directories={"language_tool_dependencies": _LT_DEPENDENCIES},
    )


def _build_backend_path() -> Path:
    import hatchling

    if hatchling.__file__ is None:
        raise RuntimeError("offline Hatchling backend is unavailable")
    return Path(hatchling.__file__).resolve().parents[1]


def _installed_smoke(python: Path, working_directory: Path) -> None:
    working_directory.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        (
            os.fspath(python),
            "-c",
            "from polis import Analyzer, AnalyzerConfig; "
            "a=Analyzer(AnalyzerConfig()); "
            "r=a.analyze('Zeby wrócić.'); "
            "c=a.correct('Zeby wrócić.'); "
            "assert r.issues and c.corrected_text == 'Żeby wrócić.'",
        ),
        cwd=working_directory,
        env=_offline_environment(),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError("installed sdist public API smoke failed")


def _fallback_evidence(
    python: Path,
    temporary: Path,
    config: GateConfig,
    *,
    timeout_seconds: float,
) -> dict[str, object]:
    unavailable = temporary / "unavailable-languagetool"
    unavailable.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    unavailable.chmod(0o700)
    with InstalledRunnerSession(
        python=python,
        runner=_RUNNER,
        vendored_stdio=unavailable,
        working_directory=temporary / "fallback",
        timeout_seconds=timeout_seconds,
    ) as session:
        raw, _ = session.exchange(1, "Zeby wrócić.")
    observation = validate_runner_response("Zeby wrócić.", raw, config=config)
    automatic_sources = sorted({item.source for item in observation.automatic_edits})
    reviewable_sources = sorted({item.source for item in observation.reviewable_edits})
    qualified = (
        automatic_sources == ["rule:spelling.zeby"]
        and not reviewable_sources
        and observation.corrected_text == "Żeby wrócić."
        and observation.model_calls == 0
    )
    return {
        "qualified": qualified,
        "status": "complete",
        "automatic_sources": automatic_sources,
        "reviewable_sources": reviewable_sources,
        "model_calls": observation.model_calls,
        "output_hash": _observation_hash(observation),
    }


def _environment_payload(
    config: GateConfig, performance: PerformanceEvidence, cases: int
) -> dict[str, object]:
    return {
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "machine": platform.machine(),
        "operating_system": platform.platform(),
        "platform_profile": release_platform_profile(),
        "source_policy_version": config.source_policy_version,
        "language_tool_version": config.language_tool["version"],
        "language_tool_upstream_commit": config.language_tool["upstream_commit"],
        "language_tool_manifest_sha256": config.language_tool["manifest_sha256"],
        "language_tool_bridge_sha256": config.language_tool["bridge_sha256"],
        "language_tool_runner_sha256": config.language_tool["runner_sha256"],
        "language_tool_artifact_sha256": config.language_tool["artifact_sha256"],
        "language_tool_dependencies_sha256": config.language_tool[
            "dependencies_sha256"
        ],
        "model_calls_per_sentence": (performance.model_calls / cases if cases else 0.0),
    }


__all__ = [
    "ArtifactAudit",
    "CaseRun",
    "InstalledRunnerSession",
    "PerformanceEvidence",
    "audit_release_artifacts",
    "install_artifact_offline",
    "parse_arguments",
    "run_installed_cases",
    "summarize_split",
]


if __name__ == "__main__":
    raise SystemExit(main())
