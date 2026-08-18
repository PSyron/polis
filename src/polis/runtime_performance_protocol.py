"""Isolated runtime performance protocol v2 (repository measurement support)."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import platform
import re
import resource
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, TextIO, cast

_REQUEST_SCHEMA: Final = "polis.runtime-performance.request"
_RESPONSE_SCHEMA: Final = "polis.runtime-performance.response"
_SCHEMA_VERSION: Final = 2
_PROFILE_IDS: Final = frozenset({"default", "morphology"})
_ENVIRONMENT_FIELDS: Final = frozenset(
    {
        "package_version",
        "platform_machine",
        "platform_release",
        "platform_system",
        "python_version",
    }
)
_FINDING_FIELDS: Final = frozenset(
    {
        "id",
        "category",
        "severity",
        "message",
        "explanation",
        "original",
        "suggestion",
        "start",
        "end",
        "confidence",
        "source",
    }
)
_FINDING_ID: Final = re.compile(r"finding_[0-9a-f]{32}\Z")
_SOURCE: Final = re.compile(r"(?:rule|llm):[a-z0-9][a-z0-9._-]*\Z")
_NOTICE_SHA256: Final = (
    "84a51ba8ad5f8b3e4571762bbd59aa48efb78d5dc551bd93cec9f9f708049393"
)
_DICTIONARY_ID: Final = "pl.sgjp.sgjp-2026.06.01"


class RuntimePerformanceProtocolError(ValueError):
    """Malformed request, response, worker identity, or process state."""


@dataclass(frozen=True, slots=True)
class RuntimeWorkerMeasurement:
    profile: str
    environment: dict[str, str]
    morphology_provider: dict[str, str] | None
    startup_rss_bytes: int
    measurement_start_rss_bytes: int
    peak_rss_bytes: int
    durations_ns: tuple[int, ...]
    findings_by_case: tuple[tuple[dict[str, object], ...], ...]
    findings_sha256: str


def _canonical_line(value: Mapping[str, object]) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_object(line: str, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(line)
    except json.JSONDecodeError as error:
        raise RuntimePerformanceProtocolError(f"{label} is not valid JSON") from error
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise RuntimePerformanceProtocolError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _exact(value: Mapping[str, object], fields: set[str], label: str) -> None:
    if set(value) != fields:
        raise RuntimePerformanceProtocolError(f"{label} fields mismatch")


def _validate_finding_payload(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise RuntimePerformanceProtocolError("finding must be an object")
    finding = cast(dict[str, object], value)
    _exact(finding, set(_FINDING_FIELDS), "finding")
    finding_id = finding["id"]
    category = finding["category"]
    severity = finding["severity"]
    message = finding["message"]
    explanation = finding["explanation"]
    original = finding["original"]
    suggestion = finding["suggestion"]
    start = finding["start"]
    end = finding["end"]
    confidence = finding["confidence"]
    source = finding["source"]
    if not isinstance(finding_id, str) or _FINDING_ID.fullmatch(finding_id) is None:
        raise RuntimePerformanceProtocolError("finding id malformed")
    if category not in {
        "inflection",
        "agreement",
        "syntax",
        "spelling",
        "punctuation",
        "style",
    }:
        raise RuntimePerformanceProtocolError("finding category malformed")
    if severity not in {"error", "warning", "suggestion"}:
        raise RuntimePerformanceProtocolError("finding severity malformed")
    if not isinstance(message, str) or not message.strip():
        raise RuntimePerformanceProtocolError("finding message malformed")
    if not isinstance(explanation, str) or not explanation.strip():
        raise RuntimePerformanceProtocolError("finding explanation malformed")
    if not isinstance(original, str):
        raise RuntimePerformanceProtocolError("finding original malformed")
    if suggestion is not None and not isinstance(suggestion, str):
        raise RuntimePerformanceProtocolError("finding suggestion malformed")
    if suggestion is not None and suggestion == original:
        raise RuntimePerformanceProtocolError("finding suggestion is unchanged")
    if (
        isinstance(start, bool)
        or not isinstance(start, int)
        or start < 0
        or isinstance(end, bool)
        or not isinstance(end, int)
        or end < start
        or end - start != len(original)
    ):
        raise RuntimePerformanceProtocolError("finding range malformed")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(confidence)
        or not 0.0 <= confidence <= 1.0
    ):
        raise RuntimePerformanceProtocolError("finding confidence malformed")
    if not isinstance(source, str) or _SOURCE.fullmatch(source) is None:
        raise RuntimePerformanceProtocolError("finding source malformed")
    return finding


def _require_protocol(value: Mapping[str, object], *, schema: str, label: str) -> str:
    if (
        value.get("schema_id") != schema
        or value.get("schema_version") != _SCHEMA_VERSION
    ):
        raise RuntimePerformanceProtocolError(f"{label} schema mismatch")
    operation = value.get("operation")
    if not isinstance(operation, str):
        raise RuntimePerformanceProtocolError(f"{label} operation must be a string")
    return operation


def _rss_bytes() -> int:
    raw = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return raw if platform.system() == "Darwin" else raw * 1024


def _environment() -> dict[str, str]:
    return {
        "package_version": importlib.metadata.version("polis-nlp"),
        "platform_machine": platform.machine(),
        "platform_release": platform.release(),
        "platform_system": platform.system(),
        "python_version": platform.python_version(),
    }


def _validate_profile(profile: str) -> dict[str, object] | None:
    if profile not in _PROFILE_IDS:
        raise RuntimePerformanceProtocolError("unsupported runtime profile")
    if profile == "default":
        try:
            importlib.import_module("morfeusz2")
        except ImportError:
            return None
        raise RuntimePerformanceProtocolError(
            "default worker requires morfeusz2 absent"
        )

    from polis.rules._morfeusz import _load_qualified_morfeusz

    provider = _load_qualified_morfeusz()
    if provider is None:
        raise RuntimePerformanceProtocolError(
            "morphology worker requires qualified provider"
        )
    identity = provider.identity
    if (
        identity.package_version != "1.99.15"
        or identity.dictionary_id != _DICTIONARY_ID
        or identity.dictionary_notice_sha256 != _NOTICE_SHA256
    ):
        raise RuntimePerformanceProtocolError("morphology provider identity mismatch")
    return {
        "provider": "morfeusz2",
        "package_version": identity.package_version,
        "dictionary_id": identity.dictionary_id,
        "dictionary_notice_sha256": identity.dictionary_notice_sha256,
    }


def _finding_payload(finding: object) -> dict[str, object]:
    from polis.core import Finding

    if not isinstance(finding, Finding):
        raise RuntimePerformanceProtocolError("analyzer returned a non-Finding")
    return {
        "id": finding.id,
        "category": finding.category.value,
        "severity": finding.severity.value,
        "message": finding.message,
        "explanation": finding.explanation,
        "original": finding.original,
        "suggestion": finding.suggestion,
        "start": finding.start,
        "end": finding.end,
        "confidence": finding.confidence.value,
        "source": str(finding.source),
    }


def run_worker(stdin: TextIO, stdout: TextIO) -> int:
    """Run one strict line-oriented worker. Dataset/scoring never enter this process."""

    started = _read_object(stdin.readline(), label="start request")
    _exact(
        started,
        {"schema_id", "schema_version", "operation", "profile"},
        "start request",
    )
    if (
        _require_protocol(started, schema=_REQUEST_SCHEMA, label="start request")
        != "start"
    ):
        raise RuntimePerformanceProtocolError("first operation must be start")
    profile = started.get("profile")
    if not isinstance(profile, str):
        raise RuntimePerformanceProtocolError("profile must be a string")
    provider = _validate_profile(profile)

    from polis import Analyzer, AnalyzerConfig

    analyzer = Analyzer(AnalyzerConfig())
    startup_rss = _rss_bytes()
    stdout.write(
        _canonical_line(
            {
                "schema_id": _RESPONSE_SCHEMA,
                "schema_version": _SCHEMA_VERSION,
                "operation": "started",
                "profile": profile,
                "environment": _environment(),
                "morphology_provider": provider,
                "startup_rss_bytes": startup_rss,
            }
        )
        + "\n"
    )
    stdout.flush()

    measurement_checkpoint_seen = False
    expected_sequence = 0
    while True:
        line = stdin.readline()
        if not line:
            raise RuntimePerformanceProtocolError("worker input ended before finish")
        request = _read_object(line, label="worker request")
        operation = _require_protocol(
            request, schema=_REQUEST_SCHEMA, label="worker request"
        )
        if operation == "analyze":
            _exact(
                request,
                {"schema_id", "schema_version", "operation", "sequence", "text"},
                "analyze request",
            )
            sequence = request.get("sequence")
            text = request.get("text")
            if (
                isinstance(sequence, bool)
                or not isinstance(sequence, int)
                or sequence < 0
            ):
                raise RuntimePerformanceProtocolError(
                    "sequence must be a non-negative integer"
                )
            if not isinstance(text, str):
                raise RuntimePerformanceProtocolError("text must be a string")
            if sequence != expected_sequence:
                raise RuntimePerformanceProtocolError("worker sequence mismatch")
            before = time.perf_counter_ns()
            findings = analyzer.analyze(text).issues
            after = time.perf_counter_ns()
            stdout.write(
                _canonical_line(
                    {
                        "schema_id": _RESPONSE_SCHEMA,
                        "schema_version": _SCHEMA_VERSION,
                        "operation": "analyzed",
                        "sequence": sequence,
                        "duration_ns": after - before,
                        "findings": [_finding_payload(finding) for finding in findings],
                    }
                )
                + "\n"
            )
            stdout.flush()
            expected_sequence += 1
            continue
        if operation == "measurement_start":
            _exact(
                request,
                {"schema_id", "schema_version", "operation"},
                "measurement start request",
            )
            if measurement_checkpoint_seen:
                raise RuntimePerformanceProtocolError(
                    "measurement start checkpoint already recorded"
                )
            stdout.write(
                _canonical_line(
                    {
                        "schema_id": _RESPONSE_SCHEMA,
                        "schema_version": _SCHEMA_VERSION,
                        "operation": "measurement_started",
                        "measurement_start_rss_bytes": _rss_bytes(),
                    }
                )
                + "\n"
            )
            stdout.flush()
            measurement_checkpoint_seen = True
            continue
        if operation == "finish":
            _exact(
                request, {"schema_id", "schema_version", "operation"}, "finish request"
            )
            if not measurement_checkpoint_seen:
                raise RuntimePerformanceProtocolError(
                    "finish requires measurement start checkpoint"
                )
            stdout.write(
                _canonical_line(
                    {
                        "schema_id": _RESPONSE_SCHEMA,
                        "schema_version": _SCHEMA_VERSION,
                        "operation": "finished",
                        "peak_rss_bytes": _rss_bytes(),
                    }
                )
                + "\n"
            )
            stdout.flush()
            return 0
        raise RuntimePerformanceProtocolError("unsupported worker operation")


def run_isolated_measurement(
    *,
    python: str,
    profile: str,
    texts: Sequence[str],
    warmup_repetitions: int,
    measured_repetitions: int,
) -> RuntimeWorkerMeasurement:
    """Measure an installed-wheel runtime worker while the parent owns the dataset."""

    if warmup_repetitions < 0 or measured_repetitions < 2:
        raise RuntimePerformanceProtocolError("invalid repetition counts")
    process = subprocess.Popen(
        [python, "-m", "polis.runtime_performance_worker"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None

    process.stdin.write(
        _canonical_line(
            {
                "schema_id": _REQUEST_SCHEMA,
                "schema_version": _SCHEMA_VERSION,
                "operation": "start",
                "profile": profile,
            }
        )
        + "\n"
    )
    process.stdin.flush()
    started = _read_object(process.stdout.readline(), label="started response")
    _exact(
        started,
        {
            "schema_id",
            "schema_version",
            "operation",
            "profile",
            "environment",
            "morphology_provider",
            "startup_rss_bytes",
        },
        "started response",
    )
    if (
        _require_protocol(started, schema=_RESPONSE_SCHEMA, label="started response")
        != "started"
    ):
        raise RuntimePerformanceProtocolError("worker did not start")
    if started.get("profile") != profile:
        raise RuntimePerformanceProtocolError("worker profile mismatch")

    sequence = 0
    durations: list[int] = []
    measured_findings: list[tuple[dict[str, object], ...]] = []
    first_hash: str | None = None
    measurement_start_rss: int | None = None
    for repetition in range(warmup_repetitions + measured_repetitions):
        if repetition == warmup_repetitions:
            process.stdin.write(
                _canonical_line(
                    {
                        "schema_id": _REQUEST_SCHEMA,
                        "schema_version": _SCHEMA_VERSION,
                        "operation": "measurement_start",
                    }
                )
                + "\n"
            )
            process.stdin.flush()
            checkpoint = _read_object(
                process.stdout.readline(), label="measurement started response"
            )
            _exact(
                checkpoint,
                {
                    "schema_id",
                    "schema_version",
                    "operation",
                    "measurement_start_rss_bytes",
                },
                "measurement started response",
            )
            if (
                _require_protocol(
                    checkpoint,
                    schema=_RESPONSE_SCHEMA,
                    label="measurement started response",
                )
                != "measurement_started"
            ):
                raise RuntimePerformanceProtocolError(
                    "worker did not report measurement start"
                )
            raw_measurement_start = checkpoint.get("measurement_start_rss_bytes")
            if (
                isinstance(raw_measurement_start, bool)
                or not isinstance(raw_measurement_start, int)
                or raw_measurement_start < 0
            ):
                raise RuntimePerformanceProtocolError(
                    "measurement_start_rss_bytes must be a non-negative integer"
                )
            measurement_start_rss = raw_measurement_start

        repetition_findings: list[tuple[dict[str, object], ...]] = []
        for text in texts:
            process.stdin.write(
                _canonical_line(
                    {
                        "schema_id": _REQUEST_SCHEMA,
                        "schema_version": _SCHEMA_VERSION,
                        "operation": "analyze",
                        "sequence": sequence,
                        "text": text,
                    }
                )
                + "\n"
            )
            process.stdin.flush()
            response = _read_object(
                process.stdout.readline(), label="analyzed response"
            )
            _exact(
                response,
                {
                    "schema_id",
                    "schema_version",
                    "operation",
                    "sequence",
                    "duration_ns",
                    "findings",
                },
                "analyzed response",
            )
            if (
                _require_protocol(
                    response, schema=_RESPONSE_SCHEMA, label="analyzed response"
                )
                != "analyzed"
                or response.get("sequence") != sequence
            ):
                raise RuntimePerformanceProtocolError("worker sequence mismatch")
            duration = response.get("duration_ns")
            findings = response.get("findings")
            if (
                isinstance(duration, bool)
                or not isinstance(duration, int)
                or duration < 0
            ):
                raise RuntimePerformanceProtocolError(
                    "duration_ns must be non-negative"
                )
            if not isinstance(findings, list):
                raise RuntimePerformanceProtocolError("findings must be an object list")
            parsed_findings = tuple(
                _validate_finding_payload(item) for item in findings
            )
            if repetition >= warmup_repetitions:
                durations.append(duration)
                repetition_findings.append(parsed_findings)
            sequence += 1
        if repetition >= warmup_repetitions:
            encoded = _canonical_line({"findings": repetition_findings}).encode("utf-8")
            digest = hashlib.sha256(encoded).hexdigest()
            if first_hash is None:
                first_hash = digest
                measured_findings = repetition_findings
            elif digest != first_hash:
                raise RuntimePerformanceProtocolError(
                    "worker findings changed between repetitions"
                )

    process.stdin.write(
        _canonical_line(
            {
                "schema_id": _REQUEST_SCHEMA,
                "schema_version": _SCHEMA_VERSION,
                "operation": "finish",
            }
        )
        + "\n"
    )
    process.stdin.flush()
    finished = _read_object(process.stdout.readline(), label="finished response")
    _exact(
        finished,
        {"schema_id", "schema_version", "operation", "peak_rss_bytes"},
        "finished response",
    )
    if (
        _require_protocol(finished, schema=_RESPONSE_SCHEMA, label="finished response")
        != "finished"
    ):
        raise RuntimePerformanceProtocolError("worker did not finish")
    process.stdin.close()
    return_code = process.wait(timeout=30)
    stderr = process.stderr.read()
    if return_code != 0:
        raise RuntimePerformanceProtocolError(f"worker failed: {stderr.strip()}")
    environment = started.get("environment")
    morphology_provider = started.get("morphology_provider")
    startup_rss = started.get("startup_rss_bytes")
    peak_rss = finished.get("peak_rss_bytes")
    if (
        not isinstance(environment, dict)
        or set(environment) != _ENVIRONMENT_FIELDS
        or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in environment.items()
        )
        or any(not value for value in environment.values())
    ):
        raise RuntimePerformanceProtocolError("worker environment malformed")
    expected_provider = (
        None
        if profile == "default"
        else {
            "provider": "morfeusz2",
            "package_version": "1.99.15",
            "dictionary_id": _DICTIONARY_ID,
            "dictionary_notice_sha256": _NOTICE_SHA256,
        }
    )
    if morphology_provider != expected_provider:
        raise RuntimePerformanceProtocolError("worker morphology provider malformed")
    if (
        isinstance(startup_rss, bool)
        or not isinstance(startup_rss, int)
        or isinstance(measurement_start_rss, bool)
        or not isinstance(measurement_start_rss, int)
        or isinstance(peak_rss, bool)
        or not isinstance(peak_rss, int)
    ):
        raise RuntimePerformanceProtocolError("worker RSS malformed")
    if (
        startup_rss < 0
        or measurement_start_rss < 0
        or peak_rss < 0
        or measurement_start_rss < startup_rss
        or peak_rss < measurement_start_rss
    ):
        raise RuntimePerformanceProtocolError("worker RSS ordering malformed")
    assert first_hash is not None
    return RuntimeWorkerMeasurement(
        profile=profile,
        environment=cast(dict[str, str], environment),
        morphology_provider=cast(dict[str, str] | None, morphology_provider),
        startup_rss_bytes=startup_rss,
        measurement_start_rss_bytes=measurement_start_rss,
        peak_rss_bytes=peak_rss,
        durations_ns=tuple(durations),
        findings_by_case=tuple(measured_findings),
        findings_sha256=first_hash,
    )


__all__ = [
    "RuntimePerformanceProtocolError",
    "RuntimeWorkerMeasurement",
    "run_isolated_measurement",
    "run_worker",
]
