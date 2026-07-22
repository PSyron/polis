#!/usr/bin/env python3
"""Run installed Polis sentence analysis through a bounded JSONL protocol."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO, cast

_MAX_REQUEST_BYTES = 65_536
_SCHEMA_VERSION = 1
_OPERATION = "analyze_sentence"
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
_ABBREVIATIONS = frozenset(
    {
        "al",
        "doc",
        "dr",
        "itd",
        "itp",
        "m.in",
        "nr",
        "np",
        "prof",
        "r",
        "tj",
        "tzn",
        "ul",
    }
)
_TRAILING_MARKS = frozenset("'\"”’»)]}")


@dataclass(frozen=True, slots=True)
class Request:
    request_id: int
    text: str


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_sentence_release_case.py",
        description=__doc__,
    )
    parser.add_argument("--vendored-stdio", type=Path, required=True)
    parser.add_argument("--expected-install-root", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser


def _validate_startup(arguments: argparse.Namespace) -> None:
    if not arguments.expected_install_root.is_absolute():
        raise SystemExit("expected installation root must be absolute")
    if not arguments.vendored_stdio.is_absolute():
        raise SystemExit("vendored stdio executable must be absolute")
    if not arguments.vendored_stdio.is_file() or not os.access(
        arguments.vendored_stdio, os.X_OK
    ):
        raise SystemExit("vendored stdio executable is unavailable")
    if (
        isinstance(arguments.timeout_seconds, bool)
        or not math.isfinite(arguments.timeout_seconds)
        or arguments.timeout_seconds <= 0
    ):
        raise SystemExit("timeout must be positive and finite")
    if any(os.environ.get(name) for name in _PROXY_VARIABLES):
        raise SystemExit("proxy environment variables are forbidden")


def _validate_import_origin(module_file: str, expected_root: Path) -> None:
    origin = Path(module_file).resolve()
    try:
        origin.relative_to(expected_root.resolve())
    except ValueError as error:
        raise SystemExit(
            "installed Polis import origin is outside the expected installation"
        ) from error


def _request(raw: bytes, previous_request_id: int) -> Request:
    if len(raw) > _MAX_REQUEST_BYTES:
        raise ValueError("runner.request_too_large")
    try:
        payload: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("runner.invalid_json") from error
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "request_id",
        "operation",
        "text",
    }:
        raise ValueError("runner.invalid_request")
    if payload["schema_version"] != _SCHEMA_VERSION:
        raise ValueError("runner.unsupported_schema")
    if payload["operation"] != _OPERATION:
        raise ValueError("runner.unsupported_operation")
    request_id = payload["request_id"]
    if (
        isinstance(request_id, bool)
        or not isinstance(request_id, int)
        or request_id <= previous_request_id
    ):
        raise ValueError("runner.invalid_request_id")
    text = payload["text"]
    if not isinstance(text, str):
        raise ValueError("runner.invalid_request")
    if _sentence_count(text) != 1:
        raise ValueError("runner.single_sentence_required")
    return Request(request_id=request_id, text=text)


def _sentence_count(text: str) -> int:
    if not text or not text.strip() or "\n\n" in text or "\r\n\r\n" in text:
        return 0
    boundaries = 0
    index = 0
    while index < len(text):
        character = text[index]
        if character not in ".!?":
            index += 1
            continue
        if character == "." and (
            _is_decimal(text, index) or _is_abbreviation(text, index)
        ):
            index += 1
            continue
        end = index + 1
        while end < len(text) and text[end] in ".!?":
            end += 1
        while end < len(text) and text[end] in _TRAILING_MARKS:
            end += 1
        if end == len(text) or text[end].isspace():
            boundaries += 1
        index = end
    trailing = text.rstrip()
    if not trailing:
        return 0
    if trailing[-1] not in ".!?" and trailing[-1] not in _TRAILING_MARKS:
        boundaries += 1
    return boundaries


def _is_decimal(text: str, index: int) -> bool:
    return (
        index > 0
        and index + 1 < len(text)
        and text[index - 1].isdigit()
        and text[index + 1].isdigit()
    )


def _is_abbreviation(text: str, index: int) -> bool:
    start = index - 1
    end = index + 1
    while start >= 0 and (text[start].isalnum() or text[start] == "."):
        start -= 1
    while end < len(text) and (text[end].isalnum() or text[end] == "."):
        end += 1
    return text[start + 1 : end].rstrip(".").lower() in _ABBREVIATIONS


def _finding_payload(finding: object) -> dict[str, object]:
    item = cast(Any, finding)
    return {
        "id": item.id,
        "category": item.category.value,
        "severity": item.severity.value,
        "original": item.original,
        "suggestion": item.suggestion,
        "start": item.start,
        "end": item.end,
        "confidence": item.confidence.value,
        "source": str(item.source),
    }


def _outcome_payload(outcome: object) -> dict[str, object]:
    item = cast(Any, outcome)
    return {
        "status": item.status,
        "backend": item.backend,
        "operation": item.operation,
        "suggestions": item.suggestions,
        "model_calls": item.model_calls,
        "protocol_versions": list(item.protocol_versions),
        "operation_version": item.operation_version,
        "source_policy_version": item.source_policy_version,
    }


def _self_peak_rss_bytes() -> int:
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak if sys.platform == "darwin" else peak * 1024


def _write(stream: TextIO, payload: object) -> None:
    stream.write(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )
    stream.flush()


def _error_payload(request_id: int | None, code: str) -> dict[str, object]:
    return {
        "schema_version": _SCHEMA_VERSION,
        "request_id": request_id,
        "status": "invalid_request",
        "error_code": code,
    }


def _language_tool_process_start_count(analyzer: object) -> int:
    """Read measured process evidence from the public Analyzer diagnostic."""

    value = getattr(analyzer, "language_tool_process_start_count", None)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("runner.invalid_process_start_evidence")
    return value


def main() -> int:
    arguments = _parser().parse_args()
    _validate_startup(arguments)

    import polis
    from polis import Analyzer, AnalyzerConfig

    if polis.__file__ is None:
        raise SystemExit("installed Polis import origin is unavailable")
    _validate_import_origin(polis.__file__, arguments.expected_install_root)

    previous_request_id = 0
    with Analyzer(
        AnalyzerConfig(
            vendored_language_tool_stdio_path=os.fspath(arguments.vendored_stdio),
            vendored_language_tool_timeout_seconds=arguments.timeout_seconds,
        )
    ) as analyzer:
        for raw in sys.stdin.buffer:
            request_id: int | None = None
            try:
                request = _request(raw, previous_request_id)
                request_id = request.request_id
                previous_request_id = request.request_id
            except ValueError as error:
                _write(sys.stdout, _error_payload(request_id, str(error)))
                continue

            started = time.perf_counter()
            try:
                analysis = analyzer.analyze(request.text)
                correction = analyzer.correct(request.text)
                selected_ids = tuple(
                    finding.id
                    for finding in correction.skipped_findings
                    if finding.suggestion is not None
                )
                selected_text = correction.apply_suggestions(selected_ids)
            except Exception as error:
                del error
                _write(
                    sys.stdout,
                    {
                        "schema_version": _SCHEMA_VERSION,
                        "request_id": request.request_id,
                        "status": "invalid_output",
                        "error_code": "runner.analysis_failed",
                    },
                )
                continue
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            python_rss = _self_peak_rss_bytes()
            outcomes = tuple(
                _outcome_payload(outcome) for outcome in correction.suggestion_outcomes
            )
            _write(
                sys.stdout,
                {
                    "schema_version": _SCHEMA_VERSION,
                    "request_id": request.request_id,
                    "status": "complete",
                    "analysis_findings": [
                        _finding_payload(finding) for finding in analysis.issues
                    ],
                    "automatic_findings": [
                        _finding_payload(finding)
                        for finding in correction.applied_findings
                    ],
                    "reviewable_findings": [
                        _finding_payload(finding)
                        for finding in correction.skipped_findings
                        if finding.suggestion is not None
                    ],
                    "corrected_text": correction.corrected_text,
                    "selected_text": selected_text,
                    "selected_finding_ids": list(selected_ids),
                    "suggestion_outcomes": list(outcomes),
                    "elapsed_ms": elapsed_ms,
                    "python_rss_bytes": python_rss,
                    "child_rss_bytes": 0,
                    "combined_rss_bytes": python_rss,
                    "python_peak_rss_bytes": python_rss,
                    "child_peak_rss_bytes": 0,
                    "combined_peak_rss_bytes": python_rss,
                    "model_calls": sum(
                        cast(int, outcome["model_calls"]) for outcome in outcomes
                    ),
                    "process_start_count": _language_tool_process_start_count(analyzer),
                },
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
