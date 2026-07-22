"""Benchmark one persistent vendored LanguageTool process on Polish sentences."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from statistics import median
from typing import Any, cast

from polis import Analyzer, AnalyzerConfig
from polis.evaluation.correction_corpus import (
    CorrectionCorpusCase,
    load_correction_corpus_json,
    select_cases_for_purpose,
)
from polis.rules.languagetool_stdio import LocalLanguageToolStdioSession

_FORBIDDEN_REPORT_KEYS = frozenset(
    {
        "source",
        "source_text",
        "input",
        "expected_output",
        "original",
        "suggestion",
        "raw_response",
        "path",
    }
)
_RUNTIME_OVERRIDE_VARIABLES = (
    "POLIS_LT_MAIN_CLASS",
    "POLIS_LT_ARTIFACT",
    "POLIS_LT_DEPENDENCIES",
    "JAVA_BIN",
)


def load_development_sentence_cases(path: Path) -> tuple[CorrectionCorpusCase, ...]:
    """Load only reviewed development cases whose unit is one sentence."""

    corpus = load_correction_corpus_json(path)
    return tuple(
        case
        for case in select_cases_for_purpose(corpus, purpose="benchmark")
        if case.split == "development" and case.unit == "sentence"
    )


def benchmark_qualifies(summary: Mapping[str, int | float], config: Mapping[str, Any]) -> bool:
    """Apply the closed performance, reuse, and privacy gates."""

    gates = config["gates"]
    if not isinstance(gates, dict):
        return False
    return bool(
        summary.get("measured_samples", 0) > 0
        and summary.get("warm_p95_ms", math.inf)
        <= gates["maximum_warm_p95_ms"]
        and summary.get("combined_rss_bytes", math.inf)
        <= gates["maximum_combined_rss_bytes"]
        and summary.get("swap_delta_bytes", math.inf)
        <= gates["maximum_swap_delta_bytes"]
        and summary.get("socket_count", math.inf)
        <= gates["maximum_socket_count"]
        and summary.get("process_start_count")
        == gates["required_process_start_count"]
        and summary.get("repeatable_case_count")
        == gates["required_repeatable_cases"]
    )


def validate_privacy_safe_report(raw: object) -> dict[str, object]:
    """Reject visible analyzed text, edits, responses, and private paths."""

    if not isinstance(raw, dict):
        raise TypeError("report must be an object")
    if _contains_forbidden_key(raw):
        raise ValueError("report contains raw analyzed material or a private path")
    return cast(dict[str, object], raw)


def _contains_forbidden_key(raw: object) -> bool:
    if isinstance(raw, dict):
        return any(
            key in _FORBIDDEN_REPORT_KEYS or _contains_forbidden_key(value)
            for key, value in raw.items()
        )
    if isinstance(raw, list | tuple):
        return any(_contains_forbidden_key(item) for item in raw)
    return False


def _finding_hash(findings: Sequence[object]) -> str:
    records = []
    for value in findings:
        finding = cast(Any, value)
        records.append(
            (
                finding.start,
                finding.end,
                finding.original,
                finding.suggestion,
                finding.category.value,
                str(finding.source),
            )
        )
    encoded = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(1, math.ceil(len(ordered) * quantile)) - 1]


def _rss_bytes(process_id: int) -> int:
    result = subprocess.run(
        ("ps", "-o", "rss=", "-p", str(process_id)),
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError("RSS measurement is unavailable")
    return int(result.stdout.strip()) * 1_024


def _swap_used_bytes() -> int:
    result = subprocess.run(
        ("sysctl", "-n", "vm.swapusage"),
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )
    if result.returncode != 0:
        raise RuntimeError("swap measurement is unavailable")
    match = re.search(r"used = ([0-9.]+)([KMG])", result.stdout)
    if match is None:
        raise RuntimeError("swap measurement has an unsupported shape")
    multiplier = {"K": 1_024, "M": 1_048_576, "G": 1_073_741_824}[match[2]]
    return round(float(match[1]) * multiplier)


def _socket_count(process_id: int) -> int:
    lsof = shutil.which("lsof")
    if lsof is None:
        raise RuntimeError("socket audit requires lsof")
    result = subprocess.run(
        (lsof, "-nP", "-a", "-p", str(process_id), "-i"),
        capture_output=True,
        check=False,
        text=True,
        timeout=5,
    )
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return max(0, len(lines) - 1) if lines else 0


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _directory_sha256(path: Path) -> str:
    if not path.is_dir():
        raise ValueError("runtime dependency directory is unavailable")
    records = [
        (item.relative_to(path).as_posix(), _sha256(item))
        for item in sorted(path.rglob("*"))
        if item.is_file()
    ]
    if not records:
        raise ValueError("runtime dependency directory is empty")
    encoded = json.dumps(records, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_runtime_artifacts(
    config: Mapping[str, Any], *, root: Path
) -> tuple[Path, dict[str, str]]:
    if any(os.environ.get(name) for name in _RUNTIME_OVERRIDE_VARIABLES):
        raise ValueError("LanguageTool runtime environment override is not allowed")
    language_tool = config["language_tool"]
    runner = root / language_tool["runner_path"]
    artifact = root / language_tool["artifact_path"]
    dependencies = root / language_tool["dependencies_path"]
    if not runner.is_file() or not os.access(runner, os.X_OK):
        raise ValueError("pinned LanguageTool runner is unavailable")
    observed = {
        "runner_sha256": _sha256(runner),
        "artifact_sha256": _sha256(artifact),
        "dependencies_sha256": _directory_sha256(dependencies),
    }
    for name, value in observed.items():
        if value != language_tool[name]:
            raise ValueError(f"LanguageTool runtime {name} mismatch")
    return runner, observed


def _validate_config(config: object, *, root: Path) -> dict[str, Any]:
    if not isinstance(config, dict) or set(config) != {
        "schema_version",
        "experiment_id",
        "sentence_only",
        "corpus",
        "language_tool",
        "repetitions",
        "gates",
    }:
        raise ValueError("benchmark configuration fields are invalid")
    if config["schema_version"] != 1 or config["sentence_only"] is not True:
        raise ValueError("benchmark must be schema 1 and sentence-only")
    corpus = config["corpus"]
    language_tool = config["language_tool"]
    if not isinstance(corpus, dict) or set(corpus) != {"path", "sha256"}:
        raise ValueError("corpus configuration is invalid")
    if not isinstance(language_tool, dict) or set(language_tool) != {
        "version",
        "upstream_commit",
        "manifest_sha256",
        "bridge_sha256",
        "runner_path",
        "runner_sha256",
        "artifact_path",
        "artifact_sha256",
        "dependencies_path",
        "dependencies_sha256",
    }:
        raise ValueError("LanguageTool configuration is invalid")
    corpus_path = root / corpus["path"]
    if _sha256(corpus_path) != corpus["sha256"]:
        raise ValueError("corpus hash mismatch")
    return cast(dict[str, Any], config)


def run_benchmark(
    config: dict[str, Any],
    *,
    root: Path,
) -> dict[str, object]:
    """Run warmup and measured passes through one shared real session."""

    corpus_path = root / config["corpus"]["path"]
    cases = load_development_sentence_cases(corpus_path)
    if len(cases) != 69:
        raise ValueError("benchmark requires exactly 69 development sentences")
    manifest = root / "third_party" / "languagetool-pl" / "manifest.json"
    bridge = (
        root
        / "third_party"
        / "languagetool-pl"
        / "src"
        / "main"
        / "java"
        / "org"
        / "polis"
        / "languagetool"
        / "PolisStdioServer.java"
    )
    if _sha256(manifest) != config["language_tool"]["manifest_sha256"]:
        raise ValueError("LanguageTool manifest hash mismatch")
    if _sha256(bridge) != config["language_tool"]["bridge_sha256"]:
        raise ValueError("LanguageTool bridge hash mismatch")
    runner, runtime_hashes = _validate_runtime_artifacts(config, root=root)

    swap_before = _swap_used_bytes()
    warmup_hashes: dict[str, str] = {}
    measured: dict[str, list[tuple[float, str, int]]] = {
        case.id: [] for case in cases
    }
    cold_ms = 0.0
    python_rss = _rss_bytes(os.getpid())
    java_rss = 0
    socket_count = -1
    process_start_count = 0
    with LocalLanguageToolStdioSession.from_executable(
        runner.resolve(), timeout_seconds=30.0
    ) as session:
        analyzer = Analyzer(
            AnalyzerConfig(),
            language_tool_transport=session,
            contextual_inflection_transport=session,
        )
        for index, case in enumerate(cases):
            started = time.perf_counter()
            findings = analyzer.analyze(case.input).issues
            elapsed_ms = (time.perf_counter() - started) * 1_000
            if index == 0:
                cold_ms = elapsed_ms
            warmup_hashes[case.id] = _finding_hash(findings)

        for _ in range(config["repetitions"]["measured"]):
            for case in cases:
                started = time.perf_counter()
                findings = analyzer.analyze(case.input).issues
                elapsed_ms = (time.perf_counter() - started) * 1_000
                measured[case.id].append(
                    (elapsed_ms, _finding_hash(findings), len(findings))
                )
            python_rss = max(python_rss, _rss_bytes(os.getpid()))
            if session.process_id is None:
                raise RuntimeError("LanguageTool process ended during benchmark")
            java_rss = max(java_rss, _rss_bytes(session.process_id))

        if session.process_id is None:
            raise RuntimeError("LanguageTool process is unavailable for audit")
        socket_count = _socket_count(session.process_id)
        process_start_count = session.process_start_count
        swap_after = _swap_used_bytes()

    latencies = [item[0] for values in measured.values() for item in values]
    repeatable = sum(
        all(item[1] == warmup_hashes[case_id] for item in values)
        for case_id, values in measured.items()
    )
    character_samples = sum(
        len(case.input) * len(measured[case.id]) for case in cases
    )
    elapsed_seconds = sum(latencies) / 1_000
    summary: dict[str, int | float] = {
        "total_cases": len(cases),
        "measured_samples": len(latencies),
        "cold_first_request_ms": cold_ms,
        "warm_median_ms": median(latencies),
        "warm_p50_ms": _percentile(latencies, 0.50),
        "warm_p95_ms": _percentile(latencies, 0.95),
        "cases_per_second": len(latencies) / elapsed_seconds,
        "characters_per_second": character_samples / elapsed_seconds,
        "python_rss_bytes": python_rss,
        "java_rss_bytes": java_rss,
        "combined_rss_bytes": python_rss + java_rss,
        "swap_delta_bytes": max(0, swap_after - swap_before),
        "socket_count": socket_count,
        "process_start_count": process_start_count,
        "repeatable_case_count": repeatable,
    }
    evidence = [
        {
            "case_id": case.id,
            "input_character_count": len(case.input),
            "finding_count": measured[case.id][0][2],
            "finding_hash": measured[case.id][0][1],
            "repeatable": all(
                item[1] == warmup_hashes[case.id] for item in measured[case.id]
            ),
            "median_ms": median(item[0] for item in measured[case.id]),
            "p95_ms": _percentile(
                [item[0] for item in measured[case.id]], 0.95
            ),
        }
        for case in cases
    ]
    report: dict[str, object] = {
        "schema_version": 1,
        "experiment_id": config["experiment_id"],
        "configuration_sha256": "",
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "machine": platform.machine(),
            "language_tool_version": config["language_tool"]["version"],
            "language_tool_upstream_commit": config["language_tool"][
                "upstream_commit"
            ],
            **runtime_hashes,
        },
        "summary": summary,
        "case_evidence": evidence,
        "decision": {"qualified": benchmark_qualifies(summary, config)},
    }
    validate_privacy_safe_report(report)
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).with_name("config.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    root = Path.cwd()
    raw: object = json.loads(arguments.config.read_text(encoding="utf-8"))
    config = _validate_config(raw, root=root)
    report = run_benchmark(config, root=root)
    report["configuration_sha256"] = _sha256(arguments.config)
    validate_privacy_safe_report(report)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "benchmark_qualifies",
    "load_development_sentence_cases",
    "run_benchmark",
    "validate_privacy_safe_report",
]
