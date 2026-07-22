"""Benchmark the real vendored Polish LanguageTool stdio engine."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import select
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any, Protocol

_ALLOWED_RULE_IDS = frozenset(
    {
        "BRAK_PRZECINKA_KTORY",
        "BRAK_PRZECINKA_SPOJNIK_PROSTY",
        "BRAK_PRZECINKA_ZE",
        "BRAK_PRZECINKA_ZEBY",
        "WOLACZ_BEZ_PRZECINKA",
    }
)
_TOOL = "LanguageTool"
_VERSION = "6.8"


class Session(Protocol):
    rss_kib: int

    def check(self, text: str) -> tuple[dict[str, Any], float]: ...

    def close(self) -> None: ...


class StdioSession:
    """One persistent stdio process so startup and warm checks stay distinct."""

    def __init__(self, command: list[str], timeout: float) -> None:
        self._timeout = timeout
        self._process = subprocess.Popen(  # noqa: S603
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.rss_kib = 0

    def check(self, text: str) -> tuple[dict[str, Any], float]:
        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("stdio process does not expose pipes")
        request = json.dumps({"text": text, "language": "pl-PL"}, ensure_ascii=False)
        started = time.perf_counter()
        self._process.stdin.write(request + "\n")
        self._process.stdin.flush()
        readable, _, _ = select.select(
            [self._process.stdout.fileno()], [], [], self._timeout
        )
        if not readable:
            raise TimeoutError("vendored LanguageTool response timed out")
        raw = self._process.stdout.readline()
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        if not raw:
            raise RuntimeError(self._failure_message("stdio process exited"))
        payload: Any = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("stdio response must be a JSON object")
        self.rss_kib = max(self.rss_kib, _rss_kib(self._process.pid))
        return payload, elapsed_ms

    def close(self) -> None:
        if self._process.stdin is not None and not self._process.stdin.closed:
            self._process.stdin.close()
        try:
            return_code = self._process.wait(timeout=self._timeout)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            self._process.wait(timeout=self._timeout)
            raise RuntimeError(
                "stdio process did not exit after stdin closed"
            ) from None
        if return_code != 0:
            raise RuntimeError(self._failure_message("stdio process failed"))

    def _failure_message(self, prefix: str) -> str:
        stderr = ""
        if self._process.stderr is not None:
            stderr = self._process.stderr.read().strip()
        return f"{prefix}: {stderr}" if stderr else prefix


def _rss_kib(pid: int) -> int:
    result = subprocess.run(  # noqa: S603
        ["ps", "-o", "rss=", "-p", str(pid)],
        capture_output=True,
        check=False,
        text=True,
        timeout=2,
    )
    if result.returncode != 0:
        return 0
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def _load_corpus(path: Path) -> list[dict[str, Any]]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("corpus must contain a cases array")
    cases: list[dict[str, Any]] = []
    for raw_case in payload["cases"]:
        if not isinstance(raw_case, dict):
            raise ValueError("corpus case must be an object")
        case_id = raw_case.get("id")
        text = raw_case.get("input")
        findings = raw_case.get("expected_findings")
        verification = raw_case.get("verification")
        if (
            not isinstance(case_id, str)
            or not isinstance(text, str)
            or not isinstance(findings, list)
            or not isinstance(verification, str)
        ):
            raise ValueError("corpus case is missing benchmark fields")
        cases.append(raw_case)
    return cases


def _gold_edits(
    case: dict[str, Any], *, category: str | None = None
) -> set[tuple[int, int, str]]:
    result: set[tuple[int, int, str]] = set()
    for finding in case["expected_findings"]:
        if not isinstance(finding, dict):
            raise ValueError("expected finding must be an object")
        if category is not None and finding.get("category") != category:
            continue
        start = finding.get("start")
        end = finding.get("end")
        suggestion = finding.get("suggestion")
        if (
            isinstance(start, bool)
            or not isinstance(start, int)
            or isinstance(end, bool)
            or not isinstance(end, int)
            or not isinstance(suggestion, str)
        ):
            raise ValueError("expected finding has an invalid edit")
        result.add((start, end, suggestion))
    return result


def _normalize_prediction(
    text: str, payload: dict[str, Any]
) -> set[tuple[int, int, str, str]]:
    raw_matches = payload.get("matches")
    if not isinstance(raw_matches, list):
        raise ValueError("stdio response must contain a matches list")
    normalized: set[tuple[int, int, str, str]] = set()
    for raw_match in raw_matches:
        if not isinstance(raw_match, dict):
            raise ValueError("LanguageTool match must be an object")
        rule = raw_match.get("rule")
        if not isinstance(rule, dict) or rule.get("id") not in _ALLOWED_RULE_IDS:
            raise ValueError("stdio bridge emitted a non-qualified rule")
        rule_id = rule["id"]
        offset = _non_negative_int(raw_match.get("offset"), "offset")
        length = _non_negative_int(raw_match.get("length"), "length")
        start = _utf16_offset_to_codepoint(text, offset)
        end = _utf16_offset_to_codepoint(text, offset + length)
        replacements = raw_match.get("replacements")
        if not isinstance(replacements, list):
            raise ValueError("LanguageTool replacements must be a list")
        candidate_edits: set[tuple[int, int, str]] = set()
        for replacement in replacements:
            if not isinstance(replacement, dict) or not isinstance(
                replacement.get("value"), str
            ):
                raise ValueError("LanguageTool replacement must contain text")
            edit = _minimal_edit(start, text[start:end], replacement["value"])
            if edit is not None:
                candidate_edits.add(edit)
        if len(candidate_edits) == 1:
            edit_start, edit_end, suggestion = candidate_edits.pop()
            normalized.add((edit_start, edit_end, suggestion, rule_id))
    return normalized


def _minimal_edit(
    start: int, original: str, replacement: str
) -> tuple[int, int, str] | None:
    prefix = 0
    while (
        prefix < len(original)
        and prefix < len(replacement)
        and original[prefix] == replacement[prefix]
    ):
        prefix += 1
    original_tail = len(original)
    replacement_tail = len(replacement)
    while (
        original_tail > prefix
        and replacement_tail > prefix
        and original[original_tail - 1] == replacement[replacement_tail - 1]
    ):
        original_tail -= 1
        replacement_tail -= 1
    suggestion = replacement[prefix:replacement_tail]
    if original[prefix:original_tail] == suggestion:
        return None
    return start + prefix, start + original_tail, suggestion


def _utf16_offset_to_codepoint(text: str, offset: int) -> int:
    units = 0
    for index, character in enumerate(text):
        if units == offset:
            return index
        width = 2 if ord(character) > 0xFFFF else 1
        if units < offset < units + width:
            raise ValueError("LanguageTool offset splits a surrogate pair")
        units += width
    if units == offset:
        return len(text)
    raise ValueError("LanguageTool offset is outside the input")


def _non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"LanguageTool {label} must be a non-negative integer")
    return value


def _verify_software(payload: dict[str, Any]) -> None:
    software = payload.get("software")
    if not isinstance(software, dict):
        raise ValueError("stdio response is missing software metadata")
    if software.get("name") != _TOOL or software.get("version") != _VERSION:
        raise ValueError("stdio response identity mismatch")


def _metric(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0
    return precision, recall, f1


def _latency(durations: list[float]) -> dict[str, float]:
    if not durations:
        return {"p50": 0.0, "p95": 0.0, "average": 0.0}
    ordered = sorted(durations)
    p95_index = max(int(len(ordered) * 0.95) - 1, 0)
    return {
        "p50": statistics.median(ordered),
        "p95": ordered[p95_index],
        "average": sum(ordered) / len(ordered),
    }


def run_benchmark(
    *,
    corpus: Path,
    session: Session,
    runtime_disk_bytes: int,
) -> dict[str, Any]:
    cases = _load_corpus(corpus)
    durations: list[float] = []
    case_reports: list[dict[str, Any]] = []
    qualified_tp = qualified_fp = qualified_fn = 0
    all_tp = all_fp = all_fn = 0
    negative_count = negative_changed = 0
    try:
        for case in cases:
            text = case["input"]
            payload, elapsed_ms = session.check(text)
            _verify_software(payload)
            durations.append(elapsed_ms)
            raw_prediction = _normalize_prediction(text, payload)
            prediction = {
                (start, end, suggestion) for start, end, suggestion, _ in raw_prediction
            }
            qualified_gold = _gold_edits(case, category="punctuation")
            all_gold = _gold_edits(case)
            qualified_tp += len(prediction & qualified_gold)
            qualified_fp += len(prediction - qualified_gold)
            qualified_fn += len(qualified_gold - prediction)
            all_tp += len(prediction & all_gold)
            all_fp += len(prediction - all_gold)
            all_fn += len(all_gold - prediction)
            is_negative = case["verification"] == "negative"
            if is_negative:
                negative_count += 1
                negative_changed += bool(prediction)
            case_reports.append(
                {
                    "id": case["id"],
                    "verification": case["verification"],
                    "predicted": sorted(prediction),
                    "qualified_false_positives": sorted(prediction - qualified_gold),
                    "qualified_false_negatives": sorted(qualified_gold - prediction),
                    "all_gold_false_negatives": sorted(all_gold - prediction),
                    "rule_ids": sorted({item[3] for item in raw_prediction}),
                    "latency_ms": elapsed_ms,
                }
            )
    finally:
        session.close()

    qualified_precision, qualified_recall, qualified_f1 = _metric(
        qualified_tp, qualified_fp, qualified_fn
    )
    all_precision, all_recall, all_f1 = _metric(all_tp, all_fp, all_fn)
    return {
        "tool": _TOOL,
        "version": _VERSION,
        "corpus_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
        "totals": {
            "case_count": len(cases),
            "qualified_true_positives": qualified_tp,
            "qualified_false_positives": qualified_fp,
            "qualified_false_negatives": qualified_fn,
            "all_gold_true_positives": all_tp,
            "all_gold_false_positives": all_fp,
            "all_gold_false_negatives": all_fn,
            "hard_negative_cases": negative_count,
            "hard_negative_cases_with_findings": negative_changed,
        },
        "quality": {
            "qualified_precision": qualified_precision,
            "qualified_recall": qualified_recall,
            "qualified_f1": qualified_f1,
            "all_gold_precision": all_precision,
            "all_gold_recall": all_recall,
            "all_gold_f1": all_f1,
            "hard_negative_unchanged_rate": (
                (negative_count - negative_changed) / negative_count
                if negative_count
                else 0.0
            ),
        },
        "performance": {
            "startup_ms": durations[0] if durations else 0.0,
            "warm_latency_ms": _latency(durations[1:]),
            "rss_peak_kib": session.rss_kib,
            "runtime_disk_bytes": runtime_disk_bytes,
        },
        "cases": case_reports,
    }


def _runtime_disk_bytes(jar: Path, dependencies: Path) -> int:
    return jar.stat().st_size + sum(
        path.stat().st_size for path in dependencies.rglob("*") if path.is_file()
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    arguments = _parse_args()
    if not arguments.jar.is_file():
        raise SystemExit(f"jar not found: {arguments.jar}")
    if not arguments.dependencies.is_dir():
        raise SystemExit(f"dependencies not found: {arguments.dependencies}")
    if not arguments.corpus.is_file():
        raise SystemExit(f"corpus not found: {arguments.corpus}")
    java_bin = os.environ.get("JAVA_BIN", "java")
    classpath = f"{arguments.jar}{os.pathsep}{arguments.dependencies / '*'}"
    report = run_benchmark(
        corpus=arguments.corpus,
        session=StdioSession(
            [
                java_bin,
                "-cp",
                classpath,
                "org.polis.languagetool.PolisStdioServer",
            ],
            arguments.timeout,
        ),
        runtime_disk_bytes=_runtime_disk_bytes(arguments.jar, arguments.dependencies),
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if arguments.json is not None:
        arguments.json.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
