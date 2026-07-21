"""Run the real local LanguageTool inflection candidate benchmark (#58)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import select
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import TracebackType
from typing import Self

from experiments.inflection_candidates.benchmark import (
    BenchmarkCase,
    CandidateBenchmarkReport,
    TimedCandidateResponse,
    authored_benchmark_cases,
    build_request_payload,
    load_corpus_cases,
    run_cases,
    summarize_observations,
    validate_response,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODULE_ROOT = ROOT / "third_party" / "languagetool-pl"
DEFAULT_CORPUS_PATH = (
    ROOT / "tests" / "fixtures" / "evaluation" / "polish_correction_corpus_v3.json"
)
DEFAULT_AUTHORED_PATH = Path(__file__).with_name("cases.json")


@dataclass(frozen=True)
class RuntimeEvidence:
    """Reproducible local resource and provenance evidence."""

    engine: str
    version: str
    upstream_revision: str
    license: str
    hardware: str
    operating_system: str
    cold_start_ms: float
    peak_rss_bytes: int
    runtime_disk_bytes: int
    polish_resource_bytes: int


class LocalStdioClient:
    """One warm, local newline-delimited JSON LanguageTool process."""

    def __init__(
        self,
        *,
        command: tuple[str, ...],
        cwd: Path,
        timeout_seconds: float,
    ) -> None:
        if not command:
            raise ValueError("stdio command must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._command = command
        self._cwd = cwd
        self._timeout_seconds = timeout_seconds
        self._process: subprocess.Popen[str] | None = None
        self._started_at = 0.0
        self.cold_start_ms = 0.0
        self.peak_rss_bytes = 0

    def __enter__(self) -> Self:
        if self._process is not None:
            raise RuntimeError("stdio client is already running")
        self._started_at = time.perf_counter()
        self._process = subprocess.Popen(
            self._command,
            cwd=self._cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Close the child process without leaving a local runtime behind."""

        process = self._process
        if process is None:
            return
        if process.stdin is not None and not process.stdin.closed:
            process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        self._process = None

    def generate(self, case: BenchmarkCase) -> TimedCandidateResponse:
        """Request and validate one independent candidate set."""

        process = self._process
        if process is None or process.stdin is None or process.stdout is None:
            raise RuntimeError("stdio client must be entered before use")
        if process.poll() is not None:
            raise RuntimeError("LanguageTool stdio process exited unexpectedly")
        request = json.dumps(
            build_request_payload(case), ensure_ascii=False, separators=(",", ":")
        )
        started = time.perf_counter()
        process.stdin.write(request + "\n")
        process.stdin.flush()
        ready, _, _ = select.select(
            [process.stdout], [], [], self._timeout_seconds
        )
        if not ready:
            raise TimeoutError("LanguageTool synthesis response timed out")
        raw_response = process.stdout.readline()
        if not raw_response:
            raise RuntimeError("LanguageTool stdio process returned no response")
        elapsed_ms = (time.perf_counter() - started) * 1_000
        result = validate_response(
            raw_response,
            source_text=case.source,
            requested_spans=((case.start, case.end),),
        )[0]
        if self.cold_start_ms == 0.0:
            self.cold_start_ms = (time.perf_counter() - self._started_at) * 1_000
        self.peak_rss_bytes = max(self.peak_rss_bytes, _resident_bytes(process.pid))
        return TimedCandidateResponse(result=result, elapsed_ms=elapsed_ms)


def _resident_bytes(process_id: int) -> int:
    result = subprocess.run(
        ("ps", "-o", "rss=", "-p", str(process_id)),
        check=False,
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode != 0 or not result.stdout.strip().isdigit():
        return 0
    return int(result.stdout.strip()) * 1_024


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def collect_runtime_evidence(
    module_root: Path, client: LocalStdioClient
) -> RuntimeEvidence:
    """Read pinned provenance and measured resource use after inference."""

    manifest_payload = json.loads(
        (module_root / "manifest.json").read_text(encoding="utf-8")
    )
    if not isinstance(manifest_payload, dict):
        raise TypeError("LanguageTool manifest must be an object")
    upstream = manifest_payload.get("upstream")
    if not isinstance(upstream, dict):
        raise TypeError("LanguageTool manifest upstream must be an object")
    version = upstream.get("version")
    revision = upstream.get("commit")
    license_name = manifest_payload.get("license")
    if not isinstance(version, str) or not version:
        raise ValueError("LanguageTool manifest version is incomplete")
    if not isinstance(revision, str) or not revision:
        raise ValueError("LanguageTool manifest revision is incomplete")
    if not isinstance(license_name, str) or not license_name:
        raise ValueError("LanguageTool manifest provenance is incomplete")
    resource_root = (
        module_root
        / "sources"
        / "languagetool-language-modules"
        / "pl"
        / "src"
        / "main"
        / "resources"
        / "org"
        / "languagetool"
        / "resource"
        / "pl"
    )
    return RuntimeEvidence(
        engine="LanguageTool PolishSynthesizer",
        version=version,
        upstream_revision=revision,
        license=license_name,
        hardware=platform.machine(),
        operating_system=platform.platform(),
        cold_start_ms=client.cold_start_ms,
        peak_rss_bytes=client.peak_rss_bytes,
        runtime_disk_bytes=_directory_size(module_root / "target"),
        polish_resource_bytes=_directory_size(resource_root),
    )


def _report_payload(report: CandidateBenchmarkReport) -> dict[str, object]:
    return asdict(report)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark finite Polish inflection candidates through local stdio."
    )
    parser.add_argument("--module-root", type=Path, default=DEFAULT_MODULE_ROOT)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--authored", type=Path, default=DEFAULT_AUTHORED_PATH)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    arguments = parser.parse_args(argv)

    runner = arguments.module_root / "scripts" / "run_stdio.sh"
    command = (os.fspath(runner),)
    authored_cases = authored_benchmark_cases(arguments.authored)
    development_cases = load_corpus_cases(arguments.corpus, split="development")
    holdout_cases = load_corpus_cases(arguments.corpus, split="holdout")

    with LocalStdioClient(
        command=command,
        cwd=arguments.module_root,
        timeout_seconds=arguments.timeout_seconds,
    ) as client:
        authored_report = summarize_observations(
            run_cases(client, authored_cases), exclude_first_latency=True
        )
        development_report = summarize_observations(
            run_cases(client, development_cases)
        )
        holdout_report = summarize_observations(run_cases(client, holdout_cases))
        runtime = collect_runtime_evidence(arguments.module_root, client)

    payload = {
        "schema_version": 1,
        "generator": "languagetool-polish-synthesizer",
        "corpus_sha256": _sha256(arguments.corpus),
        "authored_cases_sha256": _sha256(arguments.authored),
        "runtime": asdict(runtime),
        "authored": _report_payload(authored_report),
        "development": _report_payload(development_report),
        "holdout": _report_payload(holdout_report),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["LocalStdioClient", "RuntimeEvidence", "collect_runtime_evidence", "main"]
