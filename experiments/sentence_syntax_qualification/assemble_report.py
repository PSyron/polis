"""Assemble the frozen issue #74 prompt-variant report without raw text."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from experiments.sentence_category_routing.experiment import SelectionThresholds

from .experiment import load_qualification_config

_FORBIDDEN = {
    "source",
    "source_text",
    "input",
    "expected_output",
    "corrected_text",
    "raw_response",
    "prompt",
    "messages",
}


def assemble_development_report(
    config_path: Path, runs: tuple[dict[str, object], ...]
) -> dict[str, object]:
    """Validate one development run per frozen prompt variant and select."""

    config = load_qualification_config(config_path)
    config_hash = hashlib.sha256(config_path.read_bytes()).hexdigest()
    if len(runs) != len(config.variants):
        raise ValueError("development report requires every frozen variant")
    if _contains_forbidden(runs):
        raise ValueError("development runs must remain privacy-safe")
    by_variant: dict[str, dict[str, object]] = {}
    environments: dict[str, object] = {}
    for run in runs:
        if set(run) != {
            "schema_version",
            "experiment_id",
            "configuration_sha256",
            "environment",
            "metrics",
        }:
            raise ValueError("run fields are invalid")
        if (
            run["schema_version"] != 1
            or run["experiment_id"] != config.experiment_id
            or run["configuration_sha256"] != config_hash
        ):
            raise ValueError("run identity does not match configuration")
        metrics = _mapping(run["metrics"], "metrics")
        variant = _string(metrics.get("model"), "variant")
        if variant not in config.variants or variant in by_variant:
            raise ValueError("run variant is unexpected or duplicated")
        if metrics.get("split") != "development":
            raise ValueError("development report cannot contain another split")
        by_variant[variant] = metrics
        environments[variant] = run["environment"]
    if set(by_variant) != set(config.variants):
        raise ValueError("development variants are incomplete")

    reasons: list[str] = []
    eligible: list[str] = []
    for variant in config.variants:
        failures = _gate_failures(by_variant[variant], config.selection)
        if failures:
            reasons.extend(f"{variant}: {failure}" for failure in failures)
        else:
            eligible.append(variant)
    selected = (
        min(
            eligible,
            key=lambda name: (
                -_syntax_recall(by_variant[name]),
                _number(by_variant[name].get("warm_p95_latency_ms"), "warm p95"),
                _integer(by_variant[name].get("loaded_memory_bytes"), "memory"),
                name,
            ),
        )
        if eligible
        else None
    )
    report: dict[str, object] = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "configuration_sha256": config_hash,
        "decision": {
            "selected": selected,
            "eligible_variants": eligible,
            "reasons": reasons,
        },
        "environment": {
            "runs": [
                {"variant": variant, "metadata": environments[variant]}
                for variant in config.variants
            ]
        },
        "variants": [by_variant[variant] for variant in config.variants],
        "holdout": (
            None
            if selected is not None
            else {
                "status": "unopened",
                "reason": "no development variant passed every gate",
            }
        ),
    }
    if _contains_forbidden(report):
        raise ValueError("assembled report must remain privacy-safe")
    return report


def _gate_failures(
    metrics: dict[str, object], thresholds: SelectionThresholds
) -> tuple[str, ...]:
    failures: list[str] = []
    total = _integer(metrics.get("total_cases"), "total cases")
    valid = _integer(metrics.get("valid_responses"), "valid responses")
    if total <= 0 or valid / total != thresholds.required_valid_response_rate:
        failures.append("structured-response gate failed")
    if (
        _integer(metrics.get("negative_changes"), "negative changes")
        > thresholds.maximum_negative_changes
    ):
        failures.append("protected-negative gate failed")
    if _syntax_precision(metrics) < thresholds.minimum_edit_precision:
        failures.append("syntax precision gate failed")
    if _syntax_recall(metrics) < thresholds.minimum_focus_recall:
        failures.append("syntax recall gate failed")
    if (
        _integer(metrics.get("maximum_call_count"), "maximum calls")
        > thresholds.maximum_calls_per_sentence
    ):
        failures.append("call-count gate failed")
    if (
        _number(metrics.get("warm_p95_latency_ms"), "warm p95")
        > thresholds.maximum_warm_p95_latency_ms
    ):
        failures.append("latency gate failed")
    if (
        _integer(metrics.get("loaded_memory_bytes"), "loaded memory")
        > thresholds.maximum_loaded_memory_bytes
    ):
        failures.append("loaded-memory gate failed")
    if (
        _integer(metrics.get("swap_delta_bytes"), "swap")
        > thresholds.maximum_swap_delta_bytes
    ):
        failures.append("swap gate failed")
    return tuple(failures)


def _syntax_precision(metrics: dict[str, object]) -> float:
    channel = _mapping(metrics.get("channel_metrics"), "channel metrics")
    syntax = _mapping(channel.get("model_syntax"), "model syntax metrics")
    return _number(syntax.get("edit_precision"), "syntax precision")


def _syntax_recall(metrics: dict[str, object]) -> float:
    channel = _mapping(metrics.get("channel_metrics"), "channel metrics")
    syntax = _mapping(channel.get("model_syntax"), "model syntax metrics")
    return _number(syntax.get("edit_recall"), "syntax recall")


def _contains_forbidden(raw: object) -> bool:
    if isinstance(raw, dict):
        return any(
            key in _FORBIDDEN or _contains_forbidden(value)
            for key, value in raw.items()
        )
    if isinstance(raw, list | tuple):
        return any(_contains_forbidden(value) for value in raw)
    return False


def _mapping(raw: object, label: str) -> dict[str, object]:
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], raw)


def _string(raw: object, label: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} must be a non-empty string")
    return raw


def _integer(raw: object, label: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return raw


def _number(raw: object, label: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float) or raw < 0:
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
