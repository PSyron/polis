"""Assemble the frozen issue #69 development matrix without raw text."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence, cast

from .experiment import (
    Channel,
    EditMetrics,
    ExperimentConfig,
    Focus,
    ModelMetrics,
    load_experiment_config,
    select_development_winner,
    validate_privacy_safe_report,
)


def assemble_development_report(
    config_path: Path, runs: tuple[dict[str, object], ...]
) -> dict[str, object]:
    """Validate and combine exactly one development run per frozen model."""

    config = load_experiment_config(config_path)
    configuration_sha256 = hashlib.sha256(config_path.read_bytes()).hexdigest()
    if len(runs) != len(config.models):
        raise ValueError("development matrix must contain every frozen model")
    by_name: dict[str, tuple[dict[str, object], ModelMetrics]] = {}
    for run in runs:
        if set(run) != {
            "schema_version",
            "experiment_id",
            "configuration_sha256",
            "environment",
            "metrics",
        }:
            raise ValueError("run fields are not closed")
        if run["schema_version"] != 1 or run["experiment_id"] != config.experiment_id:
            raise ValueError("run identity mismatch")
        if run["configuration_sha256"] != configuration_sha256:
            raise ValueError("run configuration hash mismatch")
        raw_metrics = _mapping(run["metrics"], "metrics")
        metrics = _parse_metrics(raw_metrics)
        if metrics.model in by_name:
            raise ValueError("development matrix contains a duplicate model")
        by_name[metrics.model] = (run, metrics)
    expected_names = tuple(model.name for model in config.models)
    if set(by_name) != set(expected_names):
        raise ValueError("development matrix does not match frozen model names")

    ordered_metrics = tuple(by_name[name][1] for name in expected_names)
    selection = select_development_winner(config.selection, ordered_metrics)
    report: dict[str, object] = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "configuration_sha256": configuration_sha256,
        "decision": asdict(selection),
        "environment": {
            "runs": [by_name[name][0]["environment"] for name in expected_names]
        },
        "models": [by_name[name][0]["metrics"] for name in expected_names],
        "holdout": None,
    }
    return validate_privacy_safe_report(report, config)


def _parse_metrics(raw: dict[str, object]) -> ModelMetrics:
    focus_raw = _mapping(raw.get("focus_metrics"), "focus metrics")
    channel_raw = _mapping(raw.get("channel_metrics"), "channel metrics")
    focuses = {
        cast(Focus, name): _parse_edit_metrics(_mapping(value, f"{name} metrics"))
        for name, value in focus_raw.items()
    }
    channels = {
        cast(Channel, name): _parse_edit_metrics(_mapping(value, f"{name} metrics"))
        for name, value in channel_raw.items()
    }
    if set(focuses) != {"inflection", "syntax", "punctuation"}:
        raise ValueError("focus metrics are incomplete")
    if set(channels) != {
        "deterministic_punctuation",
        "deterministic_inflection",
        "model_syntax",
    }:
        raise ValueError("channel metrics are incomplete")
    return ModelMetrics(
        model=_string(raw.get("model"), "model"),
        split=_string(raw.get("split"), "split"),
        total_cases=_int(raw.get("total_cases"), "total cases"),
        valid_responses=_int(raw.get("valid_responses"), "valid responses"),
        negative_cases=_int(raw.get("negative_cases"), "negative cases"),
        negative_changes=_int(raw.get("negative_changes"), "negative changes"),
        true_positive_edits=_int(raw.get("true_positive_edits"), "true positives"),
        false_positive_edits=_int(raw.get("false_positive_edits"), "false positives"),
        false_negative_edits=_int(raw.get("false_negative_edits"), "false negatives"),
        exact_output_matches=_int(raw.get("exact_output_matches"), "exact matches"),
        median_latency_ms=_number(raw.get("median_latency_ms"), "median latency"),
        warm_p95_latency_ms=_number(raw.get("warm_p95_latency_ms"), "warm p95"),
        mean_call_count=_number(raw.get("mean_call_count"), "mean calls"),
        maximum_call_count=_int(raw.get("maximum_call_count"), "maximum calls"),
        loaded_memory_bytes=_int(raw.get("loaded_memory_bytes"), "loaded memory"),
        swap_delta_bytes=_int(raw.get("swap_delta_bytes"), "swap delta"),
        process_rss_bytes=_int(raw.get("process_rss_bytes"), "process RSS"),
        focus_metrics=focuses,
        channel_metrics=channels,
        case_evidence=(),
    )


def _parse_edit_metrics(raw: dict[str, object]) -> EditMetrics:
    return EditMetrics(
        _int(raw.get("true_positive_edits"), "true positives"),
        _int(raw.get("false_positive_edits"), "false positives"),
        _int(raw.get("false_negative_edits"), "false negatives"),
    )


def _mapping(raw: object, label: str) -> dict[str, object]:
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], raw)


def _string(raw: object, label: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} must be a non-empty string")
    return raw


def _int(raw: object, label: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return raw


def _number(raw: object, label: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)) or raw < 0:
        raise ValueError(f"{label} must be a non-negative number")
    return float(raw)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    runs: list[dict[str, object]] = []
    for path in arguments.run:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
        runs.append(_mapping(raw, "run"))
    report = assemble_development_report(arguments.config, tuple(runs))
    arguments.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["assemble_development_report"]
