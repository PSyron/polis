"""Frozen configuration and gold-independent inputs for issue #74."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from experiments.sentence_category_routing.experiment import (
    CorpusConfig,
    ModelConfig,
    SelectionThresholds,
)
from polis.core import Finding

Variant = Literal[
    "generic_verified-v1",
    "evidence_checklist_verified-v1",
    "diagnose_then_correct-v1",
]
_VARIANTS: tuple[Variant, ...] = (
    "generic_verified-v1",
    "evidence_checklist_verified-v1",
    "diagnose_then_correct-v1",
)


@dataclass(frozen=True, slots=True)
class QualificationInput:
    """Source-only information visible to routing and prompt construction."""

    source: str
    deterministic_findings: tuple[Finding, ...] = ()
    entity_spans: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    name: str
    version: str
    framework: str
    framework_version: str
    chat_template_args: dict[str, bool]


@dataclass(frozen=True, slots=True)
class QualificationConfig:
    schema_version: int
    experiment_id: str
    sentence_only: bool
    corpus: CorpusConfig
    model: ModelConfig
    runtime: RuntimeConfig
    variants: tuple[Variant, ...]
    selection: SelectionThresholds


def load_qualification_config(path: Path) -> QualificationConfig:
    """Load the closed one-model sentence qualification configuration."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version",
        "experiment_id",
        "sentence_only",
        "corpus",
        "model",
        "runtime",
        "variants",
        "selection",
    }:
        raise ValueError("qualification configuration fields are invalid")
    if raw["schema_version"] != 1 or raw["sentence_only"] is not True:
        raise ValueError("qualification must use schema 1 and sentence-only mode")
    corpus = _closed(raw["corpus"], {"path", "sha256"}, "corpus")
    corpus_path = _string(corpus["path"], "corpus path")
    if Path(corpus_path).is_absolute() or "://" in corpus_path:
        raise ValueError("corpus path must be local and relative")
    model = _closed(
        raw["model"],
        {"name", "engine", "identifier", "revision", "license", "artifact_size_bytes"},
        "model",
    )
    if model["engine"] != "mlx":
        raise ValueError("qualification model engine must be mlx")
    runtime = _closed(
        raw["runtime"],
        {
            "name",
            "version",
            "framework",
            "framework_version",
            "chat_template_args",
        },
        "runtime",
    )
    chat_args = _closed(
        runtime["chat_template_args"],
        {"enable_thinking"},
        "chat template arguments",
    )
    if chat_args["enable_thinking"] is not False:
        raise ValueError("Qwen qualification must disable thinking")
    variants = raw["variants"]
    if not isinstance(variants, list) or tuple(variants) != _VARIANTS:
        raise ValueError("qualification variants do not match the frozen order")
    selection = _closed(
        raw["selection"],
        {
            "required_valid_response_rate",
            "maximum_negative_changes",
            "minimum_edit_precision",
            "minimum_focus_recall",
            "supported_focuses",
            "maximum_calls_per_sentence",
            "maximum_warm_p95_latency_ms",
            "maximum_loaded_memory_bytes",
            "maximum_swap_delta_bytes",
        },
        "selection",
    )
    if selection["supported_focuses"] != ["syntax"]:
        raise ValueError("qualification supports syntax only")
    return QualificationConfig(
        1,
        _string(raw["experiment_id"], "experiment id"),
        True,
        CorpusConfig(corpus_path, _digest(corpus["sha256"], "corpus hash")),
        ModelConfig(
            _string(model["name"], "model name"),
            "mlx",
            _string(model["identifier"], "model identifier"),
            _string(model["revision"], "model revision"),
            _string(model["license"], "model license"),
            _positive_int(model["artifact_size_bytes"], "artifact size"),
        ),
        RuntimeConfig(
            _string(runtime["name"], "runtime name"),
            _string(runtime["version"], "runtime version"),
            _string(runtime["framework"], "framework name"),
            _string(runtime["framework_version"], "framework version"),
            {"enable_thinking": False},
        ),
        cast(tuple[Variant, ...], tuple(variants)),
        SelectionThresholds(
            _probability(selection["required_valid_response_rate"], "valid rate"),
            _non_negative_int(selection["maximum_negative_changes"], "negative changes"),
            _probability(selection["minimum_edit_precision"], "precision"),
            _probability(selection["minimum_focus_recall"], "recall"),
            ("syntax",),
            _positive_int(selection["maximum_calls_per_sentence"], "calls"),
            _positive_number(selection["maximum_warm_p95_latency_ms"], "latency"),
            _positive_int(selection["maximum_loaded_memory_bytes"], "memory"),
            _non_negative_int(selection["maximum_swap_delta_bytes"], "swap"),
        ),
    )


def _closed(raw: object, names: set[str], label: str) -> dict[str, object]:
    if not isinstance(raw, dict) or set(raw) != names:
        raise ValueError(f"{label} fields are invalid")
    return cast(dict[str, object], raw)


def _string(raw: object, label: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} must be a non-empty string")
    return raw


def _digest(raw: object, label: str) -> str:
    value = _string(raw, label)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _non_negative_int(raw: object, label: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return raw


def _positive_int(raw: object, label: str) -> int:
    value = _non_negative_int(raw, label)
    if value == 0:
        raise ValueError(f"{label} must be positive")
    return value


def _positive_number(raw: object, label: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float) or raw <= 0:
        raise ValueError(f"{label} must be positive")
    return float(raw)


def _probability(raw: object, label: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise ValueError(f"{label} must be a probability")
    value = float(raw)
    if not 0 <= value <= 1:
        raise ValueError(f"{label} must be a probability")
    return value


__all__ = [
    "QualificationConfig",
    "QualificationInput",
    "RuntimeConfig",
    "Variant",
    "load_qualification_config",
]
