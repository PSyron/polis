"""Evaluate deterministic residual syntax rules on sentence-only corpus splits."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import median
from typing import Any, Literal, Sequence, cast

from polis.core import AnalysisOptions, Category
from polis.evaluation.correction_corpus import (
    load_correction_corpus_json,
    select_cases_for_purpose,
)
from polis.rules import (
    DeterministicRuleRegistry,
    RuleRegistration,
    SyntaxMissingCorrelativeRule,
    SyntaxMissingReflexiveRule,
)

Split = Literal["development", "holdout"]


@dataclass(frozen=True, slots=True)
class ExactEdit:
    start: int
    end: int
    original: str
    suggestion: str


@dataclass(frozen=True, slots=True)
class CaseObservation:
    case_id: str
    protected_negative: bool
    gold_edits: tuple[ExactEdit, ...]
    actual_edits: tuple[ExactEdit, ...]
    elapsed_ms: float


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    case_id: str
    protected_negative: bool
    source: str
    gold_edits: tuple[ExactEdit, ...]


def load_sentence_cases(path: Path, *, split: Split) -> tuple[EvaluationCase, ...]:
    """Load only independently reviewed cases whose unit is one sentence."""

    corpus = load_correction_corpus_json(path)
    purpose = "benchmark" if split == "development" else "quality_gate"
    selected = select_cases_for_purpose(corpus, purpose=purpose)
    return tuple(
        EvaluationCase(
            case.id,
            case.stratum == "hard_negative",
            case.input,
            tuple(
                ExactEdit(edit.start, edit.end, edit.original, edit.suggestion)
                for edit in case.edits
            ),
        )
        for case in selected
        if case.split == split and case.unit == "sentence"
    )


def run_cases(cases: tuple[EvaluationCase, ...]) -> tuple[CaseObservation, ...]:
    """Run the frozen rules without consulting gold edits during detection."""

    registry = DeterministicRuleRegistry(
        (
            RuleRegistration(
                rule=SyntaxMissingReflexiveRule(),
                categories={Category.SYNTAX},
            ),
            RuleRegistration(
                rule=SyntaxMissingCorrelativeRule(),
                categories={Category.SYNTAX},
            ),
        )
    )
    options = AnalysisOptions(categories={Category.SYNTAX})
    observations: list[CaseObservation] = []
    for case in cases:
        started = time.perf_counter()
        findings = registry.find(case.source, options=options)
        elapsed_ms = (time.perf_counter() - started) * 1_000
        actual = tuple(
            ExactEdit(
                finding.start,
                finding.end,
                finding.original,
                finding.suggestion,
            )
            for finding in findings
        )
        observations.append(
            CaseObservation(
                case.case_id,
                case.protected_negative,
                case.gold_edits,
                actual,
                elapsed_ms,
            )
        )
    return tuple(observations)


def score_observations(
    observations: tuple[CaseObservation, ...],
) -> dict[str, int | float]:
    true_positive = false_positive = false_negative = 0
    protected_changes = exact_matches = 0
    for observation in observations:
        gold = set(observation.gold_edits)
        actual = set(observation.actual_edits)
        true_positive += len(gold & actual)
        false_positive += len(actual - gold)
        false_negative += len(gold - actual)
        protected_changes += int(observation.protected_negative and bool(actual))
        exact_matches += int(actual == gold)
    proposed = true_positive + false_positive
    gold_total = true_positive + false_negative
    warm_latencies = [item.elapsed_ms for item in observations][1:]
    return {
        "total_cases": len(observations),
        "proposed_edits": proposed,
        "true_positive_edits": true_positive,
        "false_positive_edits": false_positive,
        "false_negative_edits": false_negative,
        "precision": true_positive / proposed if proposed else 0.0,
        "recall": true_positive / gold_total if gold_total else 0.0,
        "protected_negative_changes": protected_changes,
        "exact_output_matches": exact_matches,
        "warm_median_ms": median(warm_latencies) if warm_latencies else 0.0,
        "warm_p95_ms": _percentile(warm_latencies, 0.95),
    }


def validate_privacy_safe_report(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise TypeError("report must be an object")
    forbidden = {
        "source",
        "source_text",
        "input",
        "expected_output",
        "original",
        "suggestion",
        "raw_response",
    }
    if _contains_key(raw, forbidden):
        raise ValueError("report cannot contain raw analyzed text or edit material")
    return cast(dict[str, object], raw)


def development_qualifies(
    summary: dict[str, int | float], config: dict[str, Any]
) -> bool:
    gates = config["gates"]
    return bool(
        summary["proposed_edits"] > 0
        and summary["precision"] >= gates["minimum_edit_precision"]
        and summary["protected_negative_changes"]
        <= gates["maximum_protected_negative_changes"]
        and summary["warm_p95_ms"] <= gates["maximum_warm_p95_ms"]
    )


def freeze_rules(
    config_path: Path,
    syntax_path: Path,
    evaluator_path: Path,
    destination: Path,
) -> dict[str, str]:
    payload = {
        "configuration_sha256": _sha256(config_path),
        "evaluator_sha256": _sha256(evaluator_path),
        "rules_sha256": _sha256(syntax_path),
    }
    destination.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def reserve_holdout_once(
    frozen_path: Path,
    marker_path: Path,
    *,
    expected: dict[str, str] | None = None,
) -> None:
    payload = json.loads(frozen_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload:
        raise ValueError("frozen rule hashes are invalid")
    if expected is not None and payload != expected:
        raise ValueError("frozen rule hashes do not match current files")
    try:
        with marker_path.open("x", encoding="utf-8") as marker:
            json.dump(payload, marker, sort_keys=True)
            marker.write("\n")
    except FileExistsError as error:
        raise FileExistsError("holdout run is already reserved") from error


def _contains_key(raw: object, forbidden: set[str]) -> bool:
    if isinstance(raw, dict):
        return any(
            key in forbidden or _contains_key(value, forbidden)
            for key, value in raw.items()
        )
    if isinstance(raw, list | tuple):
        return any(_contains_key(item, forbidden) for item in raw)
    return False


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(1, math.ceil(len(ordered) * quantile)) - 1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _case_evidence(
    observations: tuple[CaseObservation, ...],
) -> list[dict[str, object]]:
    evidence: list[dict[str, object]] = []
    for item in observations:
        visible = [
            [edit.start, edit.end, edit.original, edit.suggestion]
            for edit in item.actual_edits
        ]
        evidence.append(
            {
                "case_id": item.case_id,
                "proposed_edits": len(item.actual_edits),
                "exact_edit_match": set(item.actual_edits) == set(item.gold_edits),
                "edit_hash": hashlib.sha256(
                    json.dumps(
                        visible, ensure_ascii=False, separators=(",", ":")
                    ).encode("utf-8")
                ).hexdigest(),
                "elapsed_ms": item.elapsed_ms,
            }
        )
    return evidence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config", type=Path, default=Path(__file__).with_name("config.json")
    )
    parser.add_argument("--split", choices=("development", "holdout"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frozen", type=Path)
    parser.add_argument("--holdout-marker", type=Path)
    parser.add_argument("--development-report", type=Path)
    arguments = parser.parse_args(argv)

    config: dict[str, Any] = json.loads(arguments.config.read_text(encoding="utf-8"))
    corpus_path = Path(config["corpus"]["path"])
    if _sha256(corpus_path) != config["corpus"]["sha256"]:
        raise ValueError("corpus hash mismatch")
    syntax_path = Path("src/polis/rules/syntax.py")
    evaluator_path = Path(__file__)
    split = cast(Split, arguments.split)

    development_report: dict[str, object] | None = None
    if split == "holdout":
        if (
            arguments.frozen is None
            or arguments.holdout_marker is None
            or arguments.development_report is None
        ):
            parser.error(
                "holdout requires --frozen, --holdout-marker, and "
                "--development-report"
            )
        development_report = validate_privacy_safe_report(
            json.loads(arguments.development_report.read_text(encoding="utf-8"))
        )
        decision = development_report.get("decision")
        if not isinstance(decision, dict) or decision.get("qualified") is not True:
            raise ValueError("development rules did not qualify")
        expected = {
            "configuration_sha256": _sha256(arguments.config),
            "evaluator_sha256": _sha256(evaluator_path),
            "rules_sha256": _sha256(syntax_path),
        }
        reserve_holdout_once(
            arguments.frozen, arguments.holdout_marker, expected=expected
        )

    cases = load_sentence_cases(corpus_path, split=split)
    observations = run_cases(cases)
    summary = score_observations(observations)
    qualified = development_qualifies(summary, config)
    split_report = {
        "summary": summary,
        "case_evidence": _case_evidence(observations),
    }

    if split == "development":
        report: dict[str, object] = {
            "schema_version": 1,
            "experiment_id": config["experiment_id"],
            "configuration_sha256": _sha256(arguments.config),
            "rules_sha256": _sha256(syntax_path),
            "evaluator_sha256": _sha256(evaluator_path),
            "decision": {"qualified": qualified, "automatic_policy": False},
            "development": split_report,
            "holdout": None,
        }
        if qualified and arguments.frozen is not None:
            freeze_rules(
                arguments.config,
                syntax_path,
                evaluator_path,
                arguments.frozen,
            )
    else:
        if development_report is None:
            raise AssertionError("development report is unavailable")
        report = development_report
        report["holdout"] = split_report
        development = report["development"]
        if not isinstance(development, dict):
            raise ValueError("development report is invalid")
        development_summary = development["summary"]
        if not isinstance(development_summary, dict):
            raise ValueError("development summary is invalid")
        both_qualified = development_qualifies(
            cast(dict[str, int | float], development_summary), config
        ) and qualified
        report["decision"] = {
            "qualified": both_qualified,
            "automatic_policy": both_qualified,
        }

    validate_privacy_safe_report(report)
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
