"""Closed configuration and gold-isolated inputs for issue #69."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median
from typing import Final, Literal, cast

from polis.core import Finding
from polis.evaluation.correction_corpus import (
    CorpusEdit,
    load_correction_corpus_json,
    select_cases_for_purpose,
)
from polis.llm import TextEdit

Focus = Literal["inflection", "syntax", "punctuation"]
Split = Literal["development", "holdout"]

_TOP_FIELDS: Final = frozenset(
    {"schema_version", "experiment_id", "sentence_only", "corpus", "models", "selection"}
)
_MODEL_NAMES: Final = (
    "qwen3-1.7b-mlx-4bit",
    "bielik-1.5b-mlx-8bit",
    "qwen3-0.6b-ollama",
)


@dataclass(frozen=True, slots=True)
class CorpusConfig:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ModelConfig:
    name: str
    engine: Literal["mlx", "ollama"]
    identifier: str
    revision: str
    license: str
    artifact_size_bytes: int


@dataclass(frozen=True, slots=True)
class SelectionThresholds:
    required_valid_response_rate: float
    maximum_negative_changes: int
    minimum_edit_precision: float
    minimum_focus_recall: float
    supported_focuses: tuple[Focus, ...]
    maximum_calls_per_sentence: int
    maximum_warm_p95_latency_ms: float
    maximum_loaded_memory_bytes: int
    maximum_swap_delta_bytes: int


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    schema_version: int
    experiment_id: str
    sentence_only: bool
    corpus: CorpusConfig
    models: tuple[ModelConfig, ...]
    selection: SelectionThresholds


@dataclass(frozen=True, slots=True)
class RoutingInput:
    """Information visible to routing; evaluation labels are absent by design."""

    source: str
    deterministic_findings: tuple[Finding, ...] = ()
    entity_spans: tuple[tuple[int, int], ...] = ()


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """Gold wrapper that is passed only to the scorer after routing."""

    case_id: str
    split: Split
    focus: Focus
    protected_negative: bool
    routing_input: RoutingInput
    expected_output: str
    gold_edits: tuple[CorpusEdit, ...]


Status = Literal["valid", "invalid_response", "unavailable", "timed_out"]
Channel = Literal[
    "deterministic_punctuation",
    "deterministic_inflection",
    "model_syntax",
]
_CHANNELS: Final[tuple[Channel, ...]] = (
    "deterministic_punctuation",
    "deterministic_inflection",
    "model_syntax",
)
_FOCUSES: Final[tuple[Focus, ...]] = ("inflection", "syntax", "punctuation")


@dataclass(frozen=True, slots=True)
class CaseObservation:
    case_id: str
    focus: str
    protected_negative: bool
    valid_response: bool
    actual_edits: tuple[TextEdit, ...]
    expected_edits: tuple[TextEdit, ...]
    channel_edits: Mapping[str, tuple[TextEdit, ...]]
    exact_output_match: bool
    latency_ms: float
    call_count: int
    status: Status
    source_char_count: int
    outcome_hash: str


@dataclass(frozen=True, slots=True)
class EditMetrics:
    true_positive_edits: int
    false_positive_edits: int
    false_negative_edits: int

    @property
    def edit_precision(self) -> float:
        denominator = self.true_positive_edits + self.false_positive_edits
        return self.true_positive_edits / denominator if denominator else 0.0

    @property
    def edit_recall(self) -> float:
        denominator = self.true_positive_edits + self.false_negative_edits
        return self.true_positive_edits / denominator if denominator else 0.0


@dataclass(frozen=True, slots=True)
class ModelMetrics:
    model: str
    split: str
    total_cases: int
    valid_responses: int
    negative_cases: int
    negative_changes: int
    true_positive_edits: int
    false_positive_edits: int
    false_negative_edits: int
    exact_output_matches: int
    median_latency_ms: float
    warm_p95_latency_ms: float
    mean_call_count: float
    maximum_call_count: int
    loaded_memory_bytes: int
    swap_delta_bytes: int
    process_rss_bytes: int
    focus_metrics: Mapping[Focus, EditMetrics]
    channel_metrics: Mapping[Channel, EditMetrics]
    case_evidence: tuple[CaseObservation, ...]

    @property
    def valid_response_rate(self) -> float:
        return self.valid_responses / self.total_cases if self.total_cases else 0.0

    @property
    def edit_precision(self) -> float:
        denominator = self.true_positive_edits + self.false_positive_edits
        return self.true_positive_edits / denominator if denominator else 0.0

    @property
    def minimum_supported_recall(self) -> float:
        recalls = [
            metrics.edit_recall
            for focus, metrics in self.focus_metrics.items()
            if focus in {"syntax", "punctuation"}
        ]
        return min(recalls) if recalls else 0.0


@dataclass(frozen=True, slots=True)
class DevelopmentSelection:
    selected: str | None
    reasons: tuple[str, ...]
    eligible_models: tuple[str, ...]


def load_experiment_config(path: Path) -> ExperimentConfig:
    """Load the frozen experiment matrix from a closed local JSON object."""

    root = _mapping(json.loads(path.read_text(encoding="utf-8")), "configuration")
    _exact_fields(root, _TOP_FIELDS, "configuration")
    if root["schema_version"] != 1:
        raise ValueError("experiment schema_version must be 1")
    if root["sentence_only"] is not True:
        raise ValueError("experiment must be sentence-only")

    corpus = _closed_mapping(root["corpus"], {"path", "sha256"}, "corpus")
    corpus_path = _string(corpus["path"], "corpus path")
    if Path(corpus_path).is_absolute() or "://" in corpus_path:
        raise ValueError("corpus path must be local and relative")

    raw_models = root["models"]
    if not isinstance(raw_models, list) or len(raw_models) != 3:
        raise ValueError("models must contain exactly three configurations")
    models = tuple(_load_model(item) for item in raw_models)
    if tuple(model.name for model in models) != _MODEL_NAMES:
        raise ValueError("models must use the frozen order and names")

    thresholds = _closed_mapping(
        root["selection"],
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
    return ExperimentConfig(
        schema_version=1,
        experiment_id=_string(root["experiment_id"], "experiment id"),
        sentence_only=True,
        corpus=CorpusConfig(corpus_path, _sha256(corpus["sha256"], "corpus hash")),
        models=models,
        selection=SelectionThresholds(
            _probability(thresholds["required_valid_response_rate"], "valid response rate"),
            _non_negative_int(thresholds["maximum_negative_changes"], "negative changes"),
            _probability(thresholds["minimum_edit_precision"], "edit precision"),
            _probability(thresholds["minimum_focus_recall"], "focus recall"),
            _focuses(thresholds["supported_focuses"]),
            _positive_int(thresholds["maximum_calls_per_sentence"], "calls per sentence"),
            _positive_number(thresholds["maximum_warm_p95_latency_ms"], "warm p95 latency"),
            _positive_int(thresholds["maximum_loaded_memory_bytes"], "loaded memory"),
            _non_negative_int(thresholds["maximum_swap_delta_bytes"], "swap delta"),
        ),
    )


def summarize_observations(
    model: str,
    split: str,
    observations: Sequence[CaseObservation],
    *,
    loaded_memory_bytes: int,
    swap_delta_bytes: int,
    process_rss_bytes: int,
) -> ModelMetrics:
    """Summarize identifier-only evidence and preserve channel separation."""

    if not observations:
        raise ValueError("at least one observation is required")
    latencies = [item.latency_ms for item in observations]
    if any(not math.isfinite(value) or value < 0 for value in latencies):
        raise ValueError("latencies must be finite and non-negative")
    scores = [_score(item.actual_edits, item.expected_edits) for item in observations]
    focus_metrics = {
        focus: _combine(
            score
            for item, score in zip(observations, scores, strict=True)
            if item.focus == focus
        )
        for focus in _FOCUSES
    }
    channel_metrics = {
        channel: _combine(
            _score(tuple(item.channel_edits.get(channel, ())), item.expected_edits)
            for item in observations
            if item.focus
            == {
                "deterministic_punctuation": "punctuation",
                "deterministic_inflection": "inflection",
                "model_syntax": "syntax",
            }[channel]
        )
        for channel in _CHANNELS
    }
    combined = _combine(scores)
    warm = latencies[1:] if len(latencies) > 1 else latencies
    return ModelMetrics(
        model=model,
        split=split,
        total_cases=len(observations),
        valid_responses=sum(item.valid_response for item in observations),
        negative_cases=sum(item.protected_negative for item in observations),
        negative_changes=sum(
            item.protected_negative and bool(item.actual_edits)
            for item in observations
        ),
        true_positive_edits=combined.true_positive_edits,
        false_positive_edits=combined.false_positive_edits,
        false_negative_edits=combined.false_negative_edits,
        exact_output_matches=sum(item.exact_output_match for item in observations),
        median_latency_ms=median(latencies),
        warm_p95_latency_ms=_percentile(warm, 0.95),
        mean_call_count=mean(item.call_count for item in observations),
        maximum_call_count=max(item.call_count for item in observations),
        loaded_memory_bytes=_non_negative_int(loaded_memory_bytes, "loaded memory"),
        swap_delta_bytes=_non_negative_int(swap_delta_bytes, "swap delta"),
        process_rss_bytes=_non_negative_int(process_rss_bytes, "process RSS"),
        focus_metrics=focus_metrics,
        channel_metrics=channel_metrics,
        case_evidence=tuple(observations),
    )


def select_development_winner(
    thresholds: SelectionThresholds, models: Sequence[ModelMetrics]
) -> DevelopmentSelection:
    """Select by frozen gates, useful recall, latency, then memory."""

    eligible: list[ModelMetrics] = []
    reasons: list[str] = []
    for metrics in models:
        failures = _gate_failures(thresholds, metrics)
        if failures:
            reasons.extend(f"{metrics.model}: {failure}" for failure in failures)
        else:
            eligible.append(metrics)
    if not eligible:
        return DevelopmentSelection(None, tuple(reasons), ())
    selected = min(
        eligible,
        key=lambda item: (
            -min(
                item.focus_metrics[focus].edit_recall
                for focus in thresholds.supported_focuses
            ),
            item.warm_p95_latency_ms,
            item.loaded_memory_bytes,
            item.model,
        ),
    )
    return DevelopmentSelection(
        selected.model,
        (),
        tuple(item.model for item in eligible),
    )


def validate_privacy_safe_report(
    raw: object, config: ExperimentConfig
) -> dict[str, object]:
    """Reject reports containing analyzed content or raw responses."""

    report = _closed_mapping(
        raw,
        {
            "schema_version",
            "experiment_id",
            "configuration_sha256",
            "decision",
            "environment",
            "models",
            "holdout",
        },
        "report",
    )
    if report["schema_version"] != 1:
        raise ValueError("report schema_version must be 1")
    if report["experiment_id"] != config.experiment_id:
        raise ValueError("report experiment_id mismatch")
    _sha256(report["configuration_sha256"], "configuration hash")
    forbidden = {
        "source",
        "source_text",
        "input",
        "expected_output",
        "corrected_text",
        "raw_response",
    }
    if _contains_key(report, forbidden):
        raise ValueError("report cannot contain raw analyzed text or model responses")
    return report


def load_cases(path: Path, *, split: Split) -> tuple[EvaluationCase, ...]:
    """Load reviewed cases while keeping routing inputs independent of gold."""

    corpus = load_correction_corpus_json(path)
    purpose = "benchmark" if split == "development" else "quality_gate"
    selected = select_cases_for_purpose(corpus, purpose=purpose)
    return tuple(
        EvaluationCase(
            case_id=case.id,
            split=split,
            focus=_focus(case.stratum, case.tags),
            protected_negative=case.stratum == "hard_negative",
            routing_input=RoutingInput(
                source=case.input,
            ),
            expected_output=case.expected_output,
            gold_edits=case.edits,
        )
        for case in selected
        if case.split == split and case.unit == "sentence"
    )


def corpus_sha256(path: Path) -> str:
    """Return the byte-level corpus digest used by the frozen configuration."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _score(
    actual: tuple[TextEdit, ...], expected: tuple[TextEdit, ...]
) -> EditMetrics:
    actual_set = set(actual)
    expected_set = set(expected)
    return EditMetrics(
        len(actual_set & expected_set),
        len(actual_set - expected_set),
        len(expected_set - actual_set),
    )


def _combine(scores: Iterable[EditMetrics]) -> EditMetrics:
    typed = tuple(scores)
    return EditMetrics(
        sum(item.true_positive_edits for item in typed),
        sum(item.false_positive_edits for item in typed),
        sum(item.false_negative_edits for item in typed),
    )


def _percentile(values: Sequence[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    rank = max(1, math.ceil(quantile * len(ordered)))
    return ordered[rank - 1]


def _gate_failures(
    thresholds: SelectionThresholds, metrics: ModelMetrics
) -> tuple[str, ...]:
    failures: list[str] = []
    if metrics.valid_response_rate != thresholds.required_valid_response_rate:
        failures.append("structured-response gate failed")
    if metrics.negative_changes > thresholds.maximum_negative_changes:
        failures.append("protected-negative gate failed")
    if metrics.edit_precision < thresholds.minimum_edit_precision:
        failures.append("edit-precision gate failed")
    for focus in thresholds.supported_focuses:
        if metrics.focus_metrics[focus].edit_recall < thresholds.minimum_focus_recall:
            failures.append(f"{focus} recall gate failed")
    if metrics.maximum_call_count > thresholds.maximum_calls_per_sentence:
        failures.append("call-count gate failed")
    if metrics.warm_p95_latency_ms > thresholds.maximum_warm_p95_latency_ms:
        failures.append("latency gate failed")
    if metrics.loaded_memory_bytes > thresholds.maximum_loaded_memory_bytes:
        failures.append("loaded-memory gate failed")
    if metrics.swap_delta_bytes > thresholds.maximum_swap_delta_bytes:
        failures.append("swap gate failed")
    return tuple(failures)


def _contains_key(raw: object, forbidden: set[str]) -> bool:
    if isinstance(raw, dict):
        return any(
            key in forbidden or _contains_key(value, forbidden)
            for key, value in raw.items()
        )
    if isinstance(raw, list | tuple):
        return any(_contains_key(value, forbidden) for value in raw)
    return False


def _focuses(raw: object) -> tuple[Focus, ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("supported_focuses must be a non-empty list")
    if any(value not in _FOCUSES for value in raw) or len(set(raw)) != len(raw):
        raise ValueError("supported_focuses contain invalid or duplicate values")
    return tuple(cast(Focus, value) for value in raw)


def _load_model(raw: object) -> ModelConfig:
    model = _closed_mapping(
        raw,
        {"name", "engine", "identifier", "revision", "license", "artifact_size_bytes"},
        "model",
    )
    engine = _string(model["engine"], "model engine")
    if engine not in {"mlx", "ollama"}:
        raise ValueError("model engine must be mlx or ollama")
    return ModelConfig(
        name=_string(model["name"], "model name"),
        engine=cast(Literal["mlx", "ollama"], engine),
        identifier=_string(model["identifier"], "model identifier"),
        revision=_string(model["revision"], "model revision"),
        license=_string(model["license"], "model license"),
        artifact_size_bytes=_positive_int(model["artifact_size_bytes"], "artifact size"),
    )


def _focus(stratum: str, tags: tuple[str, ...]) -> Focus:
    if stratum in _FOCUSES:
        return stratum
    if {"inflection", "name", "surname", "case"} & set(tags):
        return "inflection"
    if {"punctuation", "quotation", "comma", "dash"} & set(tags):
        return "punctuation"
    return "syntax"


def _mapping(raw: object, label: str) -> dict[str, object]:
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{label} must be an object")
    return dict(raw)


def _closed_mapping(raw: object, names: set[str], label: str) -> dict[str, object]:
    value = _mapping(raw, label)
    _exact_fields(value, frozenset(names), label)
    return value


def _exact_fields(raw: dict[str, object], names: frozenset[str], label: str) -> None:
    if set(raw) != names:
        raise ValueError(f"{label} fields must be exactly {sorted(names)}")


def _string(raw: object, label: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise ValueError(f"{label} must be a non-empty string")
    return raw


def _sha256(raw: object, label: str) -> str:
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
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"{label} must be a positive number")
    value = float(raw)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive finite number")
    return value


def _probability(raw: object, label: str) -> float:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"{label} must be a probability")
    value = float(raw)
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(f"{label} must be between zero and one")
    return value


__all__ = [
    "CaseObservation",
    "DevelopmentSelection",
    "EditMetrics",
    "EvaluationCase",
    "ExperimentConfig",
    "ModelConfig",
    "ModelMetrics",
    "RoutingInput",
    "SelectionThresholds",
    "corpus_sha256",
    "load_cases",
    "load_experiment_config",
    "select_development_winner",
    "summarize_observations",
    "validate_privacy_safe_report",
]
