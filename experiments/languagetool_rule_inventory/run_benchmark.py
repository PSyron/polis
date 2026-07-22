"""Run the unfiltered local Polish LanguageTool rule inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import select
import subprocess
import time
from pathlib import Path
from statistics import median
from typing import Any, Sequence

from polis.llm import TextEdit

from .experiment import (
    InventoryCase,
    RuleObservation,
    disqualify_conflicting_rules,
    load_sentence_cases,
    normalize_inspection_response,
    score_rules,
    select_rule_allowlist,
    validate_privacy_safe_report,
)


class InspectionSession:
    def __init__(self, runner: Path, timeout_seconds: float) -> None:
        self._timeout = timeout_seconds
        self._process = subprocess.Popen(
            (os.fspath(runner),),
            cwd=runner.parents[1],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.peak_rss_bytes = 0

    def inspect(self, source: str) -> tuple[dict[str, Any], float]:
        if self._process.stdin is None or self._process.stdout is None:
            raise OSError("inspection stdio pipes are unavailable")
        request = json.dumps(
            {"language": "pl-PL", "operation": "inspect", "text": source},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        started = time.perf_counter()
        self._process.stdin.write(request + "\n")
        self._process.stdin.flush()
        ready, _, _ = select.select(
            [self._process.stdout], [], [], self._timeout
        )
        if not ready:
            raise TimeoutError("LanguageTool inspection timed out")
        line = self._process.stdout.readline()
        elapsed_ms = (time.perf_counter() - started) * 1_000
        if not line:
            raise OSError("LanguageTool inspection process ended")
        payload: Any = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError("inspection response must be an object")
        self.peak_rss_bytes = max(
            self.peak_rss_bytes, _rss_bytes(self._process.pid)
        )
        return payload, elapsed_ms

    def close(self) -> None:
        if self._process.stdin is not None:
            self._process.stdin.close()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            self._process.wait(timeout=5)

    def __enter__(self) -> InspectionSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def freeze_allowlist(
    rule_ids: tuple[str, ...],
    config_path: Path,
    bridge_path: Path,
    destination: Path,
) -> None:
    if not rule_ids:
        raise ValueError("cannot freeze an empty rule allowlist")
    payload = {
        "configuration_sha256": hashlib.sha256(config_path.read_bytes()).hexdigest(),
        "bridge_sha256": hashlib.sha256(bridge_path.read_bytes()).hexdigest(),
        "rule_ids": list(rule_ids),
    }
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def reserve_holdout_once(
    frozen_path: Path,
    config_path: Path,
    bridge_path: Path,
    marker_path: Path,
) -> None:
    payload = _load_frozen_allowlist(frozen_path, config_path, bridge_path)
    try:
        with marker_path.open("x", encoding="utf-8") as marker:
            json.dump(payload, marker, sort_keys=True)
            marker.write("\n")
    except FileExistsError as error:
        raise FileExistsError("holdout run is already reserved") from error


def _load_frozen_allowlist(
    frozen_path: Path, config_path: Path, bridge_path: Path
) -> dict[str, Any]:
    payload: Any = json.loads(frozen_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {
        "bridge_sha256",
        "configuration_sha256",
        "rule_ids",
    }:
        raise ValueError("frozen allowlist shape is invalid")
    expected = hashlib.sha256(config_path.read_bytes()).hexdigest()
    if payload["configuration_sha256"] != expected:
        raise ValueError("frozen allowlist configuration mismatch")
    if payload["bridge_sha256"] != hashlib.sha256(bridge_path.read_bytes()).hexdigest():
        raise ValueError("frozen allowlist bridge mismatch")
    rule_ids = payload["rule_ids"]
    if (
        not isinstance(rule_ids, list)
        or not rule_ids
        or not all(isinstance(rule_id, str) and rule_id for rule_id in rule_ids)
    ):
        raise ValueError("frozen rule identifiers are invalid")
    return payload


def run_development(
    cases: tuple[InventoryCase, ...],
    session: InspectionSession,
    *,
    selected_override: tuple[str, ...] | None = None,
) -> tuple[dict[str, object], tuple[str, ...]]:
    observations: dict[
        str, tuple[bool, tuple[TextEdit, ...], tuple[RuleObservation, ...]]
    ] = {}
    latencies: list[float] = []
    case_evidence: list[dict[str, object]] = []
    for case in cases:
        payload, elapsed_ms = session.inspect(case.inspection_input.source)
        predictions = normalize_inspection_response(
            case.inspection_input.source, payload
        )
        observations[case.case_id] = (
            case.protected_negative,
            case.gold_edits,
            predictions,
        )
        latencies.append(elapsed_ms)
        case_evidence.append(
            {
                "case_id": case.case_id,
                "protected_negative": case.protected_negative,
                "rule_ids": sorted({item.rule_id for item in predictions}),
                "proposed_edit_count": len(predictions),
                "elapsed_ms": elapsed_ms,
                "outcome_hash": hashlib.sha256(
                    json.dumps(
                        [
                            [
                                item.rule_id,
                                item.edit.start,
                                item.edit.end,
                                item.edit.suggestion,
                            ]
                            for item in predictions
                        ],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest(),
            }
        )
    metrics = score_rules(observations)
    if selected_override is None:
        candidates = select_rule_allowlist(metrics)
        selected, conflicting_rules = disqualify_conflicting_rules(
            observations, candidates
        )
    else:
        selected = selected_override
        _, conflicting_rules = disqualify_conflicting_rules(
            observations, selected
        )
        if conflicting_rules:
            raise ValueError("frozen allowlist produced conflicting edits")
    combined_tp, combined_fp, combined_fn, negative_changes = _combined_score(
        observations, selected
    )
    selected_set = set(selected)
    exact_output_matches = 0
    invalid_output_cases = 0
    for case, evidence in zip(cases, case_evidence, strict=True):
        selected_edits = tuple(
            sorted(
                {
                    item.edit
                    for item in observations[case.case_id][2]
                    if item.rule_id in selected_set
                },
                key=lambda edit: (edit.start, edit.end, edit.suggestion),
            )
        )
        corrected = _apply_valid_edits(case.inspection_input.source, selected_edits)
        valid = corrected is not None
        exact = valid and corrected == case.expected_output
        exact_output_matches += exact
        invalid_output_cases += not valid
        evidence["selected_edit_count"] = len(selected_edits)
        evidence["application_valid"] = valid
        evidence["exact_output_match"] = exact
    warm = latencies[1:] if len(latencies) > 1 else latencies
    summary = {
        "total_cases": len(cases),
        "inspected_rule_count": len(metrics),
        "selected_rule_count": len(selected),
        "conflicting_candidate_rule_count": len(conflicting_rules),
        "true_positive_edits": combined_tp,
        "false_positive_edits": combined_fp,
        "false_negative_edits": combined_fn,
        "protected_negative_changes": negative_changes,
        "exact_output_matches": exact_output_matches,
        "exact_output_coverage": exact_output_matches / len(cases) if cases else 0.0,
        "invalid_output_cases": invalid_output_cases,
        "precision": combined_tp / (combined_tp + combined_fp)
        if combined_tp + combined_fp
        else 0.0,
        "recall": combined_tp / (combined_tp + combined_fn)
        if combined_tp + combined_fn
        else 0.0,
        "cold_latency_ms": latencies[0],
        "warm_median_latency_ms": median(warm),
        "warm_p95_latency_ms": _percentile(warm, 0.95),
        "peak_rss_bytes": session.peak_rss_bytes,
    }
    result: dict[str, object] = {
        "summary": summary,
        "rules": [
            {
                "rule_id": item.rule_id,
                "upstream_categories": list(item.upstream_categories),
                "true_positive_edits": item.true_positive_edits,
                "false_positive_edits": item.false_positive_edits,
                "false_negative_edits": item.false_negative_edits,
                "protected_negative_changes": item.protected_negative_changes,
                "cases_with_edits": item.cases_with_edits,
                "precision": item.precision,
                "recall": item.recall,
            }
            for item in sorted(metrics.values(), key=lambda value: value.rule_id)
        ],
        "case_evidence": case_evidence,
    }
    return result, selected


def _apply_valid_edits(source: str, edits: tuple[TextEdit, ...]) -> str | None:
    cursor = 0
    pieces: list[str] = []
    for edit in edits:
        if edit.start < cursor or edit.end < edit.start or edit.end > len(source):
            return None
        if source[edit.start : edit.end] != edit.original:
            return None
        pieces.extend((source[cursor : edit.start], edit.suggestion))
        cursor = edit.end
    pieces.append(source[cursor:])
    return "".join(pieces)


def _combined_score(
    observations: dict[
        str, tuple[bool, tuple[TextEdit, ...], tuple[RuleObservation, ...]]
    ],
    selected: tuple[str, ...],
) -> tuple[int, int, int, int]:
    tp = fp = fn = negative_changes = 0
    selected_set = set(selected)
    for protected, expected, predictions in observations.values():
        actual = {
            item.edit for item in predictions if item.rule_id in selected_set
        }
        gold = set(expected)
        tp += len(actual & gold)
        fp += len(actual - gold)
        fn += len(gold - actual)
        negative_changes += protected and bool(actual)
    return tp, fp, fn, negative_changes


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(len(ordered) * quantile))
    return ordered[rank - 1]


def _rss_bytes(process_id: int) -> int:
    result = subprocess.run(
        ("ps", "-o", "rss=", "-p", str(process_id)),
        capture_output=True,
        text=True,
        check=True,
    )
    return int(result.stdout.strip()) * 1_024


def _runtime_disk_bytes(module_root: Path) -> int:
    return sum(
        path.stat().st_size
        for path in (module_root / "target").rglob("*")
        if path.is_file()
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).with_name("config.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--frozen", type=Path)
    parser.add_argument("--holdout-marker", type=Path)
    parser.add_argument(
        "--module-root", type=Path, default=Path("third_party/languagetool-pl")
    )
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    arguments = parser.parse_args(argv)

    config: Any = json.loads(arguments.config.read_text(encoding="utf-8"))
    corpus_path = Path(config["corpus"]["path"])
    if hashlib.sha256(corpus_path.read_bytes()).hexdigest() != config["corpus"][
        "sha256"
    ]:
        raise ValueError("corpus hash mismatch")
    cases = load_sentence_cases(corpus_path, split="development")
    module_root = arguments.module_root.resolve()
    bridge_path = (
        module_root / "src/main/java/org/polis/languagetool/PolisStdioServer.java"
    )
    selected_override: tuple[str, ...] | None = None
    development_report: dict[str, Any] | None = None
    if arguments.holdout:
        if arguments.frozen is None or arguments.holdout_marker is None:
            parser.error("--holdout requires --frozen and --holdout-marker")
        frozen_raw = _load_frozen_allowlist(
            arguments.frozen, arguments.config, bridge_path
        )
        rule_ids = frozen_raw["rule_ids"]
        selected_override = tuple(rule_ids)
        development_report = json.loads(
            arguments.output.read_text(encoding="utf-8")
        )
        validate_privacy_safe_report(development_report)
        if development_report["decision"]["selected_rule_ids"] != list(
            selected_override
        ):
            raise ValueError("frozen allowlist differs from development decision")
        reserve_holdout_once(
            arguments.frozen,
            arguments.config,
            bridge_path,
            arguments.holdout_marker,
        )
        cases = load_sentence_cases(corpus_path, split="holdout")
    with InspectionSession(
        module_root / "scripts" / "run_stdio.sh", arguments.timeout_seconds
    ) as session:
        result, selected = run_development(
            cases, session, selected_override=selected_override
        )
    if not arguments.holdout and arguments.freeze is not None:
        freeze_allowlist(
            selected, arguments.config, bridge_path, arguments.freeze
        )
    environment = {
        "language_tool_version": config["language_tool"]["version"],
        "upstream_commit": config["language_tool"]["upstream_commit"],
        "bridge_sha256": hashlib.sha256(
            bridge_path.read_bytes()
        ).hexdigest(),
        "runtime_disk_bytes": _runtime_disk_bytes(module_root),
    }
    if arguments.holdout:
        if development_report is None:
            raise AssertionError("development report was not loaded")
        report = development_report
        report["holdout"] = {
            "summary": result["summary"],
            "rules": result["rules"],
            "case_evidence": result["case_evidence"],
        }
    else:
        report = {
            "schema_version": 1,
            "experiment_id": config["experiment_id"],
            "configuration_sha256": hashlib.sha256(
                arguments.config.read_bytes()
            ).hexdigest(),
            "decision": {"selected_rule_ids": list(selected)},
            "environment": environment,
            "summary": result["summary"],
            "rules": result["rules"],
            "case_evidence": result["case_evidence"],
            "holdout": None,
        }
    validate_privacy_safe_report(report)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "InspectionSession",
    "freeze_allowlist",
    "reserve_holdout_once",
    "run_development",
]
