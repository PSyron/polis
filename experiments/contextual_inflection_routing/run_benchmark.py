"""Run the deterministic sentence-only contextual inflection benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import select
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Literal, Sequence

from polis.evaluation.correction_corpus import (
    load_correction_corpus_json,
    select_cases_for_purpose,
)
from polis.llm import TextEdit

from .experiment import (
    ContextualProposal,
    ContextSpanResult,
    RoutingInput,
    TargetClass,
    detect_evidence,
    rank_evidence,
    validate_context_response,
)

Split = Literal["development", "holdout"]


@dataclass(frozen=True, slots=True)
class GoldEdit:
    edit: TextEdit
    target_class: TargetClass
    is_inflection: bool


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    protected_negative: bool
    routing_input: RoutingInput
    expected_output: str
    gold_edits: tuple[GoldEdit, ...]


@dataclass(frozen=True, slots=True)
class CaseObservation:
    case_id: str
    protected_negative: bool
    expected_output: str
    source: str
    gold_edits: tuple[GoldEdit, ...]
    proposals: tuple[ContextualProposal, ...]
    evidence_count: int
    supported_spans: tuple[tuple[int, int], ...]
    elapsed_ms: float


class SynthesisSession:
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

    def synthesize(
        self, source: str, spans: tuple[tuple[int, int], ...]
    ) -> tuple[tuple[ContextSpanResult, ...], float]:
        if self._process.stdin is None or self._process.stdout is None:
            raise OSError("synthesis stdio pipes are unavailable")
        request = json.dumps(
            {
                "operation": "synthesize_context",
                "language": "pl-PL",
                "text": source,
                "spans": [
                    {"start": start, "end": end} for start, end in spans
                ],
            },
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
            raise TimeoutError("LanguageTool synthesis timed out")
        raw = self._process.stdout.readline()
        elapsed_ms = (time.perf_counter() - started) * 1_000
        if not raw:
            raise OSError("LanguageTool synthesis process ended")
        self.peak_rss_bytes = max(
            self.peak_rss_bytes, _rss_bytes(self._process.pid)
        )
        return (
            validate_context_response(
                raw, source_text=source, requested_spans=spans
            ),
            elapsed_ms,
        )

    def close(self) -> None:
        if self._process.stdin is not None:
            self._process.stdin.close()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            self._process.wait(timeout=5)

    def __enter__(self) -> SynthesisSession:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def load_sentence_cases(path: Path, *, split: Split) -> tuple[EvaluationCase, ...]:
    corpus = load_correction_corpus_json(path)
    purpose = "benchmark" if split == "development" else "quality_gate"
    selected = select_cases_for_purpose(corpus, purpose=purpose)
    cases: list[EvaluationCase] = []
    for case in selected:
        if case.split != split or case.unit != "sentence":
            continue
        target_class: TargetClass
        if "surname" in case.tags:
            target_class = "surname"
        elif "name" in case.tags:
            target_class = "first_name"
        else:
            target_class = "ordinary"
        gold = tuple(
            GoldEdit(
                TextEdit(edit.start, edit.end, edit.original, edit.suggestion),
                target_class,
                case.stratum == "inflection",
            )
            for edit in case.edits
        )
        cases.append(
            EvaluationCase(
                case.id,
                case.stratum == "hard_negative",
                RoutingInput(case.input),
                case.expected_output,
                gold,
            )
        )
    return tuple(cases)


def run_cases(
    cases: tuple[EvaluationCase, ...], session: SynthesisSession
) -> tuple[CaseObservation, ...]:
    observations: list[CaseObservation] = []
    for case in cases:
        source = case.routing_input.source
        evidence = detect_evidence(case.routing_input)
        supported_spans = tuple(
            sorted({span for item in evidence for span in item.spans})
        )
        proposals: tuple[ContextualProposal, ...] = ()
        elapsed_ms = 0.0
        if evidence:
            spans = tuple(
                sorted({span for item in evidence for span in item.spans})
            )
            results, elapsed_ms = session.synthesize(source, spans)
            by_span = {(item.start, item.end): item for item in results}
            raw_proposals = tuple(
                proposal
                for item in evidence
                for proposal in rank_evidence(
                    source,
                    item,
                    tuple(by_span[span] for span in item.spans),
                )
            )
            proposals = _normalize_proposals(raw_proposals)
        observations.append(
            CaseObservation(
                case.case_id,
                case.protected_negative,
                case.expected_output,
                source,
                case.gold_edits,
                proposals,
                len(evidence),
                supported_spans,
                elapsed_ms,
            )
        )
    return tuple(observations)


def score_observations(
    observations: tuple[CaseObservation, ...], *, peak_rss_bytes: int
) -> dict[str, object]:
    tp = fp = fn = protected_changes = invalid = exact = 0
    all_inflection_gold = detected_inflection_gold = 0
    class_counts: dict[str, dict[str, int]] = {
        name: {"true_positive_edits": 0, "false_positive_edits": 0, "false_negative_edits": 0}
        for name in ("ordinary", "first_name", "surname")
    }
    latencies = [item.elapsed_ms for item in observations if item.evidence_count]
    for observation in observations:
        actual_by_edit = {
            TextEdit(item.start, item.end, item.original, item.suggestion): item
            for item in observation.proposals
        }
        all_inflection_gold += sum(item.is_inflection for item in observation.gold_edits)
        detected_inflection_gold += sum(
            item.is_inflection
            and (item.edit.start, item.edit.end) in observation.supported_spans
            for item in observation.gold_edits
        )
        gold_by_edit = {
            item.edit: item
            for item in observation.gold_edits
            if (item.edit.start, item.edit.end) in observation.supported_spans
            and item.edit.original
            and item.edit.suggestion
        }
        actual = set(actual_by_edit)
        gold = set(gold_by_edit)
        tp_set = actual & gold
        fp_set = actual - gold
        fn_set = gold - actual
        tp += len(tp_set)
        fp += len(fp_set)
        fn += len(fn_set)
        protected_changes += observation.protected_negative and bool(actual)
        for edit in tp_set:
            class_counts[gold_by_edit[edit].target_class]["true_positive_edits"] += 1
        for edit in fn_set:
            class_counts[gold_by_edit[edit].target_class]["false_negative_edits"] += 1
        for edit in fp_set:
            class_counts[actual_by_edit[edit].target_class]["false_positive_edits"] += 1
        corrected = _apply_edits(
            observation.source,
            tuple(
                sorted(
                    actual,
                    key=lambda edit: (edit.start, edit.end, edit.suggestion),
                )
            ),
        )
        invalid += corrected is None
        exact += corrected is not None and corrected == observation.expected_output
    classes: dict[str, dict[str, int | float]] = {}
    for name, counts in class_counts.items():
        class_tp = counts["true_positive_edits"]
        class_fp = counts["false_positive_edits"]
        class_fn = counts["false_negative_edits"]
        classes[name] = {
            **counts,
            "precision": class_tp / (class_tp + class_fp)
            if class_tp + class_fp
            else 0.0,
            "recall": class_tp / (class_tp + class_fn)
            if class_tp + class_fn
            else 0.0,
        }
    return {
        "total_cases": len(observations),
        "cases_with_evidence": sum(item.evidence_count > 0 for item in observations),
        "evidence_count": sum(item.evidence_count for item in observations),
        "proposed_edits": tp + fp,
        "true_positive_edits": tp,
        "false_positive_edits": fp,
        "false_negative_edits": fn,
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "recall": tp / (tp + fn) if tp + fn else 0.0,
        "all_inflection_gold_edits": all_inflection_gold,
        "detected_inflection_gold_edits": detected_inflection_gold,
        "target_detection_recall": (
            detected_inflection_gold / all_inflection_gold
            if all_inflection_gold
            else 0.0
        ),
        "protected_negative_suggestions": protected_changes,
        "invalid_output_cases": invalid,
        "exact_output_matches": exact,
        "warm_median_ms": median(latencies[1:] or latencies) if latencies else 0.0,
        "warm_p95_ms": _percentile(latencies[1:] or latencies, 0.95),
        "peak_rss_bytes": peak_rss_bytes,
        "classes": classes,
    }


def development_qualifies(summary: dict[str, object], config: dict[str, Any]) -> bool:
    gates = config["gates"]
    return bool(
        summary["precision"] >= gates["minimum_edit_precision"]
        and summary["recall"] >= gates["minimum_supported_recall"]
        and summary["protected_negative_suggestions"]
        <= gates["maximum_protected_negative_suggestions"]
        and summary["invalid_output_cases"] == 0
        and summary["warm_p95_ms"] <= gates["maximum_warm_p95_ms"]
    )


def validate_privacy_safe_report(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TypeError("report must be an object")
    report = raw
    forbidden = {
        "source",
        "source_text",
        "input",
        "expected_output",
        "original",
        "suggestion",
        "form",
        "raw_response",
    }
    if _contains_key(report, forbidden):
        raise ValueError("report cannot contain raw analyzed text or forms")
    return report


def freeze_router(
    config_path: Path, experiment_path: Path, bridge_path: Path, destination: Path
) -> None:
    payload = {
        "configuration_sha256": _sha256(config_path),
        "experiment_sha256": _sha256(experiment_path),
        "bridge_sha256": _sha256(bridge_path),
        "runner_sha256": _sha256(Path(__file__)),
    }
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def reserve_holdout_once(
    frozen_path: Path,
    config_path: Path,
    experiment_path: Path,
    bridge_path: Path,
    marker_path: Path,
) -> None:
    payload: Any = json.loads(frozen_path.read_text(encoding="utf-8"))
    expected = {
        "configuration_sha256": _sha256(config_path),
        "experiment_sha256": _sha256(experiment_path),
        "bridge_sha256": _sha256(bridge_path),
        "runner_sha256": _sha256(Path(__file__)),
    }
    if payload != expected:
        raise ValueError("frozen router hashes do not match")
    try:
        with marker_path.open("x", encoding="utf-8") as marker:
            json.dump(payload, marker, sort_keys=True)
            marker.write("\n")
    except FileExistsError as error:
        raise FileExistsError("holdout run is already reserved") from error


def _normalize_proposals(
    proposals: tuple[ContextualProposal, ...],
) -> tuple[ContextualProposal, ...]:
    unique = tuple(
        sorted(
            set(proposals),
            key=lambda item: (item.start, item.end, item.suggestion, item.candidate_id),
        )
    )
    conflicting: set[int] = set()
    for index, left in enumerate(unique):
        for other_index, right in enumerate(unique[index + 1 :], start=index + 1):
            if left.start < right.end and right.start < left.end:
                conflicting.update((index, other_index))
            elif left.start == left.end == right.start == right.end and left != right:
                conflicting.update((index, other_index))
    return tuple(item for index, item in enumerate(unique) if index not in conflicting)


def _apply_edits(source: str, edits: tuple[TextEdit, ...]) -> str | None:
    cursor = 0
    pieces: list[str] = []
    for edit in edits:
        if edit.start < cursor or source[edit.start : edit.end] != edit.original:
            return None
        pieces.extend((source[cursor : edit.start], edit.suggestion))
        cursor = edit.end
    pieces.append(source[cursor:])
    return "".join(pieces)


def _case_evidence(observations: tuple[CaseObservation, ...]) -> list[dict[str, object]]:
    return [
        {
            "case_id": item.case_id,
            "evidence_count": item.evidence_count,
            "proposal_count": len(item.proposals),
            "candidate_ids": [proposal.candidate_id for proposal in item.proposals],
            "evidence_kinds": sorted({proposal.evidence_kind for proposal in item.proposals}),
            "outcome_hash": hashlib.sha256(
                json.dumps(
                    [
                        [
                            proposal.start,
                            proposal.end,
                            proposal.candidate_id,
                            proposal.evidence_kind,
                        ]
                        for proposal in item.proposals
                    ],
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            "elapsed_ms": item.elapsed_ms,
        }
        for item in observations
    ]


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(1, math.ceil(len(ordered) * quantile)) - 1]


def _rss_bytes(process_id: int) -> int:
    result = subprocess.run(
        ("ps", "-o", "rss=", "-p", str(process_id)),
        capture_output=True,
        text=True,
        check=True,
    )
    return int(result.stdout.strip()) * 1_024


def _directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _contains_key(raw: object, forbidden: set[str]) -> bool:
    if isinstance(raw, dict):
        return any(
            key in forbidden or _contains_key(value, forbidden)
            for key, value in raw.items()
        )
    if isinstance(raw, list | tuple):
        return any(_contains_key(item, forbidden) for item in raw)
    return False


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--module-root", type=Path, default=Path("third_party/languagetool-pl"))
    parser.add_argument("--freeze", type=Path)
    parser.add_argument("--holdout", action="store_true")
    parser.add_argument("--frozen", type=Path)
    parser.add_argument("--holdout-marker", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    arguments = parser.parse_args(argv)

    config: dict[str, Any] = json.loads(arguments.config.read_text(encoding="utf-8"))
    corpus_path = Path(config["corpus"]["path"])
    if _sha256(corpus_path) != config["corpus"]["sha256"]:
        raise ValueError("corpus hash mismatch")
    module_root = arguments.module_root.resolve()
    experiment_path = Path(__file__).with_name("experiment.py")
    bridge_path = module_root / "src/main/java/org/polis/languagetool/PolisStdioServer.java"
    split: Split = "holdout" if arguments.holdout else "development"
    development_report: dict[str, Any] | None = None
    if arguments.holdout:
        if arguments.frozen is None or arguments.holdout_marker is None:
            parser.error("--holdout requires --frozen and --holdout-marker")
        development_report = json.loads(arguments.output.read_text(encoding="utf-8"))
        validate_privacy_safe_report(development_report)
        if not development_report["decision"]["qualified"]:
            raise ValueError("development router did not qualify")
        reserve_holdout_once(
            arguments.frozen,
            arguments.config,
            experiment_path,
            bridge_path,
            arguments.holdout_marker,
        )
    cases = load_sentence_cases(corpus_path, split=split)
    with SynthesisSession(
        module_root / "scripts/run_stdio.sh", arguments.timeout_seconds
    ) as session:
        observations = run_cases(cases, session)
        summary = score_observations(
            observations, peak_rss_bytes=session.peak_rss_bytes
        )
    if arguments.holdout:
        if development_report is None:
            raise AssertionError("development report is unavailable")
        report = development_report
        report["holdout"] = {
            "summary": summary,
            "case_evidence": _case_evidence(observations),
        }
    else:
        qualified = development_qualifies(summary, config)
        report = {
            "schema_version": 1,
            "experiment_id": config["experiment_id"],
            "configuration_sha256": _sha256(arguments.config),
            "router_sha256": _sha256(experiment_path),
            "decision": {"qualified": qualified},
            "environment": {
                "language_tool_version": config["language_tool"]["version"],
                "upstream_commit": config["language_tool"]["upstream_commit"],
                "bridge_sha256": _sha256(bridge_path),
                "runtime_disk_bytes": _directory_bytes(module_root / "target"),
            },
            "summary": summary,
            "case_evidence": _case_evidence(observations),
            "holdout": None,
        }
        if qualified and arguments.freeze is not None:
            freeze_router(arguments.config, experiment_path, bridge_path, arguments.freeze)
    validate_privacy_safe_report(report)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CaseObservation",
    "EvaluationCase",
    "GoldEdit",
    "SynthesisSession",
    "development_qualifies",
    "freeze_router",
    "load_sentence_cases",
    "reserve_holdout_once",
    "run_cases",
    "score_observations",
    "validate_privacy_safe_report",
]
