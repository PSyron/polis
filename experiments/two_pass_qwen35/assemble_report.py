"""Assemble privacy-safe two-pass benchmark evidence from local run summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from experiments.two_pass_qwen35.experiment import (
    ExperimentConfig,
    load_experiment_config,
    validate_privacy_safe_report,
)


def assemble_report(
    config: ExperimentConfig,
    development: object,
    *,
    holdout: object | None,
) -> dict[str, object]:
    """Combine run summaries while retaining no analyzed or generated text."""

    development_payload = _run_payload(development, "development", config)
    holdout_payload = (
        None if holdout is None else _run_payload(holdout, "holdout", config)
    )
    if holdout_payload is not None and (
        holdout_payload["configuration_sha256"]
        != development_payload["configuration_sha256"]
    ):
        raise ValueError("development and holdout configurations differ")

    development_selection = _object(
        development_payload["selection"], "development selection"
    )
    selected = development_selection.get("selected")
    reasons = _string_list(development_selection.get("reasons"), "reasons")
    status = "reject"
    if isinstance(selected, str) and selected:
        if holdout_payload is None:
            status = "holdout_not_run"
            reasons = ["eligible development selection has no holdout evidence"]
        else:
            holdout_selection = _object(
                holdout_payload["selection"], "holdout selection"
            )
            if holdout_selection.get("selected") == selected:
                status = "select"
                reasons = []
            else:
                reasons = _string_list(holdout_selection.get("reasons"), "reasons")

    report: dict[str, object] = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "configuration_sha256": development_payload["configuration_sha256"],
        "decision": {
            "status": status,
            "selected_variant": selected if isinstance(selected, str) else None,
            "reasons": reasons,
        },
        "environment": development_payload["environment"],
        "variants": development_payload["metrics"],
        "holdout": None if holdout_payload is None else holdout_payload["metrics"],
    }
    return validate_privacy_safe_report(report, config)


def _run_payload(
    value: object, expected_split: str, config: ExperimentConfig
) -> dict[str, object]:
    payload = _object(value, f"{expected_split} run")
    required = {
        "schema_version",
        "experiment_id",
        "configuration_sha256",
        "split",
        "environment",
        "metrics",
        "selection",
    }
    if set(payload) != required:
        raise ValueError(f"{expected_split} run fields are invalid")
    if payload["schema_version"] != 1:
        raise ValueError("run schema_version must be 1")
    if payload["experiment_id"] != config.experiment_id:
        raise ValueError("run experiment_id mismatch")
    if payload["split"] != expected_split:
        raise ValueError("run split mismatch")
    if not isinstance(payload["metrics"], list):
        raise ValueError("run metrics must be a list")
    _object(payload["environment"], "run environment")
    _object(payload["selection"], "run selection")
    return payload


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return cast(dict[str, object], value)


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) for item in value
    ):
        raise ValueError(f"{label} must contain strings")
    return list(value)


def _load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--holdout", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    config = load_experiment_config(arguments.config)
    report = assemble_report(
        config,
        _load(arguments.development),
        holdout=_load(arguments.holdout) if arguments.holdout else None,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["assemble_report", "main"]
