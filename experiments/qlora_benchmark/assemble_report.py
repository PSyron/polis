"""Assemble privacy-safe QLoRA summary evidence from local raw arm reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from dataclasses import asdict
from pathlib import Path
from typing import cast

from experiments.qlora_benchmark.experiment import (
    ArmMetrics,
    load_experiment_config,
    select_adapter,
    validate_report,
)
from experiments.role_prompt_benchmark.run_benchmark import _infer_focus
from polis.evaluation.correction_corpus import load_correction_corpus_json
from polis.evaluation.finetuning_dataset import load_finetuning_bundle

ROOT = Path(__file__).parents[2]
DEFAULT_CONFIG = ROOT / "experiments" / "qlora_benchmark" / "config.json"
DEFAULT_DATASET = ROOT / "data" / "finetuning" / "bielik_1_5b_v1"
DEFAULT_CORPUS = (
    ROOT / "tests" / "fixtures" / "evaluation" / "polish_correction_corpus_v3.json"
)
FOCUSES = ("inflection", "syntax", "punctuation")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--training-metadata", type=Path, required=True)
    parser.add_argument("--arm-report", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    config = load_experiment_config(args.config)
    training = _object(_load(args.training_metadata), "training metadata")
    if training.get("experiment_id") != config.experiment_id:
        raise ValueError("training metadata experiment mismatch")
    raw_arms = [_object(_load(path), "arm report") for path in args.arm_report]
    arms = [_arm_metrics(raw) for raw in raw_arms]
    by_pair = {(arm.arm, arm.split): arm for arm in arms}
    raw_by_pair = {
        (arm.arm, arm.split): raw for arm, raw in zip(arms, raw_arms, strict=True)
    }
    case_metadata = _case_metadata()
    required = {
        ("prompt_only", "validation"),
        ("adapter", "validation"),
        ("adapter_prompt_ablation", "validation"),
        ("prompt_only", "holdout"),
        ("adapter", "holdout"),
    }
    if set(by_pair) != required:
        raise ValueError("exactly five required arm reports must be supplied")
    decision = select_adapter(
        config.selection,
        validation_base=by_pair[("prompt_only", "validation")],
        validation_adapter=by_pair[("adapter", "validation")],
        holdout_base=by_pair[("prompt_only", "holdout")],
        holdout_adapter=by_pair[("adapter", "holdout")],
        training_swap_delta_bytes=_integer(
            training.get("swap_delta_bytes"), "training swap delta"
        ),
    )
    adapter_hash = training.get("adapter_sha256")
    report = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "configuration_sha256": _sha256(args.config),
        "environment": {
            "hardware": "Apple M4, 16 GB unified memory",
            "operating_system": platform.platform(),
            "runtime": asdict(config.runtime),
        },
        "artifacts": {
            "base_model": asdict(config.base_model),
            "dataset": asdict(config.dataset),
            "adapter_sha256": adapter_hash,
            "adapter_size_bytes": training.get("adapter_size_bytes"),
            "weights_committed": False,
        },
        "training": {
            "configuration": asdict(config.training),
            "duration_seconds": training.get("duration_seconds"),
            "peak_process_rss_bytes": training.get("peak_process_rss_bytes"),
            "peak_mlx_memory_gb": _peak_mlx_memory(training),
            "swap_delta_bytes": training.get("swap_delta_bytes"),
            "initial_validation_loss": _validation_loss(training, first=True),
            "final_validation_loss": _validation_loss(training, first=False),
            "learning_curve": training.get("learning_curve"),
            "generated_config_sha256": training.get("generated_config_sha256"),
        },
        "arms": [
            _metrics_payload(
                arm,
                _focus_metrics(raw_by_pair[(arm.arm, arm.split)], case_metadata),
            )
            for arm in sorted(arms, key=lambda item: (item.split, item.arm))
        ],
        "selection": asdict(decision),
    }
    validate_report(report, config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(args.output)
    return 0


def _arm_metrics(raw: object) -> ArmMetrics:
    root = _object(raw, "arm report")
    metrics = _object(root.get("metrics"), "arm metrics")
    return ArmMetrics(
        arm=_string(metrics.get("arm"), "arm"),
        split=_string(metrics.get("split"), "split"),
        total_cases=_integer(metrics.get("total_cases"), "total_cases"),
        valid_responses=_integer(metrics.get("valid_responses"), "valid_responses"),
        negative_cases=_integer(metrics.get("negative_cases"), "negative_cases"),
        negative_changes=_integer(metrics.get("negative_changes"), "negative_changes"),
        true_positive_edits=_integer(
            metrics.get("true_positive_edits"), "true_positive_edits"
        ),
        false_positive_edits=_integer(
            metrics.get("false_positive_edits"), "false_positive_edits"
        ),
        false_negative_edits=_integer(
            metrics.get("false_negative_edits"), "false_negative_edits"
        ),
        exact_output_matches=_integer(
            metrics.get("exact_output_matches"), "exact_output_matches"
        ),
        median_latency_ms=_number(
            metrics.get("median_latency_ms"), "median_latency_ms"
        ),
        p95_latency_ms=_number(metrics.get("p95_latency_ms"), "p95_latency_ms"),
        throughput_chars_per_second=_number(
            metrics.get("throughput_chars_per_second"), "throughput"
        ),
        loaded_memory_bytes=_optional_integer(
            metrics.get("loaded_memory_bytes"), "loaded_memory_bytes"
        ),
    )


def _metrics_payload(
    metrics: ArmMetrics, focus_metrics: dict[str, dict[str, object]]
) -> dict[str, object]:
    payload = asdict(metrics)
    payload.update(
        {
            "valid_response_rate": metrics.valid_response_rate,
            "edit_precision": metrics.edit_precision,
            "edit_recall": metrics.edit_recall,
            "edit_f1": metrics.edit_f1,
            "complete_output_accuracy": metrics.complete_output_accuracy,
            "focus_metrics": focus_metrics,
        }
    )
    return payload


def _case_metadata() -> dict[str, tuple[str, bool]]:
    bundle = load_finetuning_bundle(
        DEFAULT_DATASET, evaluation_corpus_path=DEFAULT_CORPUS
    )
    metadata = {
        record.id: (record.focus, record.category == "no_change")
        for record in bundle.validation
    }
    corpus = load_correction_corpus_json(DEFAULT_CORPUS)
    metadata.update(
        {
            case.id: (
                _infer_focus(case.tags, case.stratum),
                case.stratum == "hard_negative",
            )
            for case in corpus.cases
            if case.split == "holdout"
        }
    )
    return metadata


def _focus_metrics(
    raw: dict[str, object], case_metadata: dict[str, tuple[str, bool]]
) -> dict[str, dict[str, object]]:
    evidence = raw.get("case_evidence")
    if not isinstance(evidence, list):
        raise ValueError("arm report case_evidence must be a list")
    grouped: dict[str, list[tuple[dict[str, object], bool]]] = {
        focus: [] for focus in FOCUSES
    }
    for item_raw in evidence:
        item = _object(item_raw, "case evidence")
        case_id = _string(item.get("case_id"), "case evidence id")
        if case_id not in case_metadata:
            raise ValueError(f"unknown case evidence id: {case_id}")
        focus, is_negative = case_metadata[case_id]
        if focus not in grouped:
            raise ValueError(f"unsupported case focus: {focus}")
        grouped[focus].append((item, is_negative))

    result: dict[str, dict[str, object]] = {}
    for focus, items in grouped.items():
        total = len(items)
        valid = sum(item.get("valid_response") is True for item, _ in items)
        negatives = sum(is_negative for _, is_negative in items)
        negative_changes = sum(
            item.get("negative_changed") is True for item, _ in items
        )
        true_positive = sum(
            _integer(item.get("true_positive_edits"), "true_positive_edits")
            for item, _ in items
        )
        false_positive = sum(
            _integer(item.get("false_positive_edits"), "false_positive_edits")
            for item, _ in items
        )
        false_negative = sum(
            _integer(item.get("false_negative_edits"), "false_negative_edits")
            for item, _ in items
        )
        exact = sum(item.get("exact_output_match") is True for item, _ in items)
        precision = _ratio(true_positive, true_positive + false_positive)
        recall = _ratio(true_positive, true_positive + false_negative)
        result[focus] = {
            "total_cases": total,
            "valid_responses": valid,
            "valid_response_rate": _ratio(valid, total),
            "negative_cases": negatives,
            "negative_changes": negative_changes,
            "true_positive_edits": true_positive,
            "false_positive_edits": false_positive,
            "false_negative_edits": false_negative,
            "edit_precision": precision,
            "edit_recall": recall,
            "edit_f1": _ratio(2 * precision * recall, precision + recall),
            "exact_output_matches": exact,
            "complete_output_accuracy": _ratio(exact, total),
        }
    return result


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return numerator / denominator if denominator else 0.0


def _peak_mlx_memory(training: dict[str, object]) -> float:
    curve = training.get("learning_curve")
    if not isinstance(curve, list):
        raise ValueError("training learning_curve must be a list")
    values = [
        float(point["peak_memory_gb"])
        for point in curve
        if isinstance(point, dict)
        and isinstance(point.get("peak_memory_gb"), (int, float))
    ]
    if not values:
        raise ValueError("training curve has no peak memory evidence")
    return max(values)


def _validation_loss(training: dict[str, object], *, first: bool) -> float:
    curve = training.get("learning_curve")
    if not isinstance(curve, list):
        raise ValueError("training learning_curve must be a list")
    values = [
        float(point["loss"])
        for point in curve
        if isinstance(point, dict)
        and point.get("kind") == "validation"
        and isinstance(point.get("loss"), (int, float))
    ]
    if not values:
        raise ValueError("training curve has no validation loss")
    return values[0] if first else values[-1]


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a string")
    return value


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def _optional_integer(value: object, label: str) -> int | None:
    if value is None:
        return None
    return _integer(value, label)


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    return float(value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
