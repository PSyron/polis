"""Pure configuration, scoring, selection, and report policy for issue #68."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Final, Literal, cast

from polis.llm import TextEdit

Focus = Literal["inflection", "syntax", "punctuation"]
Split = Literal["development", "holdout"]
Status = Literal[
    "valid",
    "invalid_response",
    "unavailable",
    "timed_out",
    "unsupported",
]

_FOCUSES: Final[tuple[Focus, ...]] = ("inflection", "syntax", "punctuation")
_VARIANTS: Final[tuple[str, ...]] = ("strict", "checklist", "counterexample")
_TOP_LEVEL_FIELDS: Final = frozenset(
    {
        "schema_version",
        "experiment_id",
        "model",
        "runtime",
        "corpus",
        "prompt_variants",
        "operation_prompt_hashes",
        "selection",
    }
)


@dataclass(frozen=True, slots=True)
class ModelConfig:
    identifier: str
    digest: str
    license: str
    artifact_size_bytes: int


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    engine: str
    version: str


@dataclass(frozen=True, slots=True)
class CorpusConfig:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class PromptVariantConfig:
    name: str
    prompt_hash: str


@dataclass(frozen=True, slots=True)
class SelectionThresholds:
    required_valid_response_rate: float
    maximum_negative_changes: int
    minimum_edit_precision: float
    minimum_focus_recall: float
    maximum_calls_per_case: int
    maximum_warm_p95_latency_ms: float
    maximum_loaded_memory_bytes: int
    maximum_swap_delta_bytes: int


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    schema_version: int
    experiment_id: str
    model: ModelConfig
    runtime: RuntimeConfig
    corpus: CorpusConfig
    prompt_variants: tuple[PromptVariantConfig, ...]
    operation_prompt_hashes: dict[str, str]
    selection: SelectionThresholds


@dataclass(frozen=True, slots=True)
class CaseObservation:
    case_id: str
    focus: str
    protected_negative: bool
    valid_response: bool
    actual_edits: tuple[TextEdit, ...]
    expected_edits: tuple[TextEdit, ...]
    exact_output_match: bool
    latency_ms: float
    call_count: int
    outcome_hash: str
    status: Status
    source_char_count: int


@dataclass(frozen=True, slots=True)
class FocusMetrics:
    total_cases: int
    valid_responses: int
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

    @property
    def edit_f1(self) -> float:
        denominator = self.edit_precision + self.edit_recall
        return (
            2 * self.edit_precision * self.edit_recall / denominator
            if denominator
            else 0.0
        )


@dataclass(frozen=True, slots=True)
class VariantMetrics:
    variant: str
    prompt_hash: str
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
    focus_metrics: dict[str, FocusMetrics]
    case_evidence: tuple[CaseObservation, ...]
    cold_latency_ms: float
    throughput_chars_per_second: float
    process_rss_bytes: int

    @property
    def valid_response_rate(self) -> float:
        return self.valid_responses / self.total_cases if self.total_cases else 0.0

    @property
    def edit_precision(self) -> float:
        denominator = self.true_positive_edits + self.false_positive_edits
        return self.true_positive_edits / denominator if denominator else 0.0

    @property
    def edit_recall(self) -> float:
        denominator = self.true_positive_edits + self.false_negative_edits
        return self.true_positive_edits / denominator if denominator else 0.0

    @property
    def edit_f1(self) -> float:
        denominator = self.edit_precision + self.edit_recall
        return (
            2 * self.edit_precision * self.edit_recall / denominator
            if denominator
            else 0.0
        )


@dataclass(frozen=True, slots=True)
class DevelopmentSelection:
    selected: str | None
    selected_prompt_hash: str | None
    reasons: tuple[str, ...]
    eligible_variants: tuple[str, ...]


def load_experiment_config(path: Path) -> ExperimentConfig:
    """Load the closed, predeclared two-pass experiment configuration."""

    root = _mapping(json.loads(path.read_text(encoding="utf-8")), "configuration")
    _exact_fields(root, _TOP_LEVEL_FIELDS, "configuration")
    if root["schema_version"] != 1:
        raise ValueError("experiment schema_version must be 1")
    model = _closed_mapping(
        root["model"],
        {"identifier", "digest", "license", "artifact_size_bytes"},
        "model",
    )
    runtime = _closed_mapping(root["runtime"], {"engine", "version"}, "runtime")
    corpus = _closed_mapping(root["corpus"], {"path", "sha256"}, "corpus")
    selection = _closed_mapping(
        root["selection"],
        {
            "required_valid_response_rate",
            "maximum_negative_changes",
            "minimum_edit_precision",
            "minimum_focus_recall",
            "maximum_calls_per_case",
            "maximum_warm_p95_latency_ms",
            "maximum_loaded_memory_bytes",
            "maximum_swap_delta_bytes",
        },
        "selection",
    )
    corpus_path = _string(corpus["path"], "corpus path")
    if Path(corpus_path).is_absolute() or "://" in corpus_path:
        raise ValueError("corpus path must be a local relative path")
    variants_raw = root["prompt_variants"]
    if not isinstance(variants_raw, list) or len(variants_raw) != 3:
        raise ValueError("prompt_variants must contain exactly three entries")
    variants = tuple(
        PromptVariantConfig(
            _string(
                _closed_mapping(item, {"name", "prompt_hash"}, "prompt variant")[
                    "name"
                ],
                "variant name",
            ),
            _sha(
                _closed_mapping(item, {"name", "prompt_hash"}, "prompt variant")[
                    "prompt_hash"
                ],
                "prompt hash",
            ),
        )
        for item in variants_raw
    )
    if tuple(item.name for item in variants) != _VARIANTS:
        raise ValueError("prompt variants must use the frozen order and names")
    operation_hashes = _closed_mapping(
        root["operation_prompt_hashes"],
        {"inflection_candidate", "syntax_correction", "punctuation_correction"},
        "operation prompt hashes",
    )
    return ExperimentConfig(
        schema_version=1,
        experiment_id=_string(root["experiment_id"], "experiment_id"),
        model=ModelConfig(
            _string(model["identifier"], "model identifier"),
            _sha(model["digest"], "model digest"),
            _string(model["license"], "model license"),
            _non_negative_int(model["artifact_size_bytes"], "artifact size"),
        ),
        runtime=RuntimeConfig(
            _string(runtime["engine"], "runtime engine"),
            _string(runtime["version"], "runtime version"),
        ),
        corpus=CorpusConfig(corpus_path, _sha(corpus["sha256"], "corpus hash")),
        prompt_variants=variants,
        operation_prompt_hashes={
            name: _sha(value, f"{name} prompt hash")
            for name, value in operation_hashes.items()
        },
        selection=SelectionThresholds(
            _probability(
                selection["required_valid_response_rate"], "valid response rate"
            ),
            _non_negative_int(
                selection["maximum_negative_changes"], "negative changes"
            ),
            _probability(selection["minimum_edit_precision"], "edit precision"),
            _probability(selection["minimum_focus_recall"], "focus recall"),
            _positive_int(selection["maximum_calls_per_case"], "calls per case"),
            _positive_number(
                selection["maximum_warm_p95_latency_ms"], "warm p95 latency"
            ),
            _positive_int(
                selection["maximum_loaded_memory_bytes"], "loaded memory"
            ),
            _non_negative_int(selection["maximum_swap_delta_bytes"], "swap delta"),
        ),
    )


def summarize_observations(
    variant: str,
    prompt_hash: str,
    split: str,
    observations: Sequence[CaseObservation],
    *,
    loaded_memory_bytes: int,
    swap_delta_bytes: int,
    process_rss_bytes: int,
) -> VariantMetrics:
    """Summarize exact edits without retaining analyzed content in evidence."""

    if not observations:
        raise ValueError("at least one observation is required")
    latencies = [item.latency_ms for item in observations]
    if any(not math.isfinite(value) or value < 0 for value in latencies):
        raise ValueError("latencies must be finite and non-negative")
    scored = [_score_edits(item.actual_edits, item.expected_edits) for item in observations]
    focus_metrics: dict[str, FocusMetrics] = {
        focus: _summarize_focus(
            [
                (item, score)
                for item, score in zip(observations, scored, strict=True)
                if item.focus == focus
            ]
        )
        for focus in _FOCUSES
    }
    warm_latencies = latencies[1:] if len(latencies) > 1 else latencies
    median, p95 = _latency_summary(warm_latencies)
    total_elapsed_ms = sum(latencies)
    throughput = (
        sum(item.source_char_count for item in observations) * 1_000
        / total_elapsed_ms
        if total_elapsed_ms
        else 0.0
    )
    return VariantMetrics(
        variant=variant,
        prompt_hash=_sha(prompt_hash, "prompt hash"),
        split=split,
        total_cases=len(observations),
        valid_responses=sum(item.valid_response for item in observations),
        negative_cases=sum(item.protected_negative for item in observations),
        negative_changes=sum(
            item.protected_negative and bool(item.actual_edits) for item in observations
        ),
        true_positive_edits=sum(score[0] for score in scored),
        false_positive_edits=sum(score[1] for score in scored),
        false_negative_edits=sum(score[2] for score in scored),
        exact_output_matches=sum(item.exact_output_match for item in observations),
        median_latency_ms=median,
        warm_p95_latency_ms=p95,
        mean_call_count=mean(item.call_count for item in observations),
        maximum_call_count=max(item.call_count for item in observations),
        loaded_memory_bytes=loaded_memory_bytes,
        swap_delta_bytes=swap_delta_bytes,
        focus_metrics=focus_metrics,
        case_evidence=tuple(observations),
        cold_latency_ms=latencies[0],
        throughput_chars_per_second=throughput,
        process_rss_bytes=process_rss_bytes,
    )


def select_development_variant(
    thresholds: SelectionThresholds,
    variants: Sequence[VariantMetrics],
) -> DevelopmentSelection:
    """Apply frozen gates and deterministic tie-breaking to development only."""

    eligible: list[VariantMetrics] = []
    reasons: list[str] = []
    for metrics in variants:
        failures = _gate_failures(thresholds, metrics)
        if failures:
            reasons.extend(f"{metrics.variant}: {failure}" for failure in failures)
        else:
            eligible.append(metrics)
    if not eligible:
        return DevelopmentSelection(None, None, tuple(reasons), ())
    selected = sorted(eligible, key=_selection_key)[0]
    return DevelopmentSelection(
        selected.variant,
        selected.prompt_hash,
        (),
        tuple(item.variant for item in eligible),
    )


def validate_privacy_safe_report(
    raw: object, config: ExperimentConfig
) -> dict[str, object]:
    """Reject committed evidence containing source, response, or corrected text."""

    report = _closed_mapping(
        raw,
        {
            "schema_version",
            "experiment_id",
            "configuration_sha256",
            "decision",
            "environment",
            "variants",
            "holdout",
        },
        "report",
    )
    if report["schema_version"] != 1:
        raise ValueError("report schema_version must be 1")
    if report["experiment_id"] != config.experiment_id:
        raise ValueError("report experiment_id mismatch")
    _sha(report["configuration_sha256"], "configuration hash")
    forbidden = {"source", "source_text", "raw_response", "corrected_text", "input"}
    if _contains_forbidden_key(report, forbidden):
        raise ValueError("report cannot contain raw analyzed text or model responses")
    return dict(report)


def _gate_failures(
    thresholds: SelectionThresholds, metrics: VariantMetrics
) -> tuple[str, ...]:
    failures: list[str] = []
    if metrics.valid_response_rate != thresholds.required_valid_response_rate:
        failures.append("structured-response gate failed")
    if metrics.negative_changes > thresholds.maximum_negative_changes:
        failures.append("protected-negative gate failed")
    if metrics.edit_precision < thresholds.minimum_edit_precision:
        failures.append("edit-precision gate failed")
    for focus in _FOCUSES:
        focus_metric = metrics.focus_metrics[focus]
        if (
            focus_metric.true_positive_edits + focus_metric.false_positive_edits
            and focus_metric.edit_precision < thresholds.minimum_edit_precision
        ):
            failures.append(f"{focus} precision gate failed")
        if focus_metric.edit_recall < thresholds.minimum_focus_recall:
            failures.append(f"{focus} recall gate failed")
    if metrics.maximum_call_count > thresholds.maximum_calls_per_case:
        failures.append("call-count gate failed")
    if metrics.warm_p95_latency_ms > thresholds.maximum_warm_p95_latency_ms:
        failures.append("latency gate failed")
    if metrics.loaded_memory_bytes > thresholds.maximum_loaded_memory_bytes:
        failures.append("memory gate failed")
    if metrics.swap_delta_bytes > thresholds.maximum_swap_delta_bytes:
        failures.append("swap gate failed")
    return tuple(failures)


def _selection_key(metrics: VariantMetrics) -> tuple[float | str, ...]:
    emitted_precisions = [
        item.edit_precision
        for item in metrics.focus_metrics.values()
        if item.true_positive_edits + item.false_positive_edits
    ]
    minimum_precision = min(emitted_precisions, default=0.0)
    macro_f1 = mean(item.edit_f1 for item in metrics.focus_metrics.values())
    return (
        -minimum_precision,
        -macro_f1,
        metrics.warm_p95_latency_ms,
        metrics.mean_call_count,
        metrics.prompt_hash,
    )


def _score_edits(
    actual: tuple[TextEdit, ...], expected: tuple[TextEdit, ...]
) -> tuple[int, int, int]:
    remaining = list(expected)
    true_positive = 0
    for edit in actual:
        try:
            index = remaining.index(edit)
        except ValueError:
            continue
        true_positive += 1
        remaining.pop(index)
    return true_positive, len(actual) - true_positive, len(remaining)


def _summarize_focus(
    items: Sequence[tuple[CaseObservation, tuple[int, int, int]]],
) -> FocusMetrics:
    return FocusMetrics(
        total_cases=len(items),
        valid_responses=sum(item.valid_response for item, _ in items),
        true_positive_edits=sum(score[0] for _, score in items),
        false_positive_edits=sum(score[1] for _, score in items),
        false_negative_edits=sum(score[2] for _, score in items),
    )


def _latency_summary(values: Sequence[float]) -> tuple[float, float]:
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
    return median, p95


def _contains_forbidden_key(value: object, forbidden: set[str]) -> bool:
    if isinstance(value, dict):
        return any(
            key in forbidden or _contains_forbidden_key(item, forbidden)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_forbidden_key(item, forbidden) for item in value)
    return False


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return cast(Mapping[str, object], value)


def _closed_mapping(
    value: object, fields: set[str], label: str
) -> Mapping[str, object]:
    result = _mapping(value, label)
    _exact_fields(result, frozenset(fields), label)
    return result


def _exact_fields(
    value: Mapping[str, object], fields: frozenset[str], label: str
) -> None:
    if set(value) != fields:
        raise ValueError(f"{label} fields are invalid")


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _sha(value: object, label: str) -> str:
    result = _string(value, label)
    if len(result) != 64 or any(character not in "0123456789abcdef" for character in result):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return result


def _non_negative_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _positive_int(value: object, label: str) -> int:
    result = _non_negative_int(value, label)
    if result == 0:
        raise ValueError(f"{label} must be positive")
    return result


def _positive_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{label} must be positive")
    return float(value)


def _probability(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if result < 0 or result > 1:
        raise ValueError(f"{label} must be between zero and one")
    return result


__all__ = [
    "CaseObservation",
    "DevelopmentSelection",
    "ExperimentConfig",
    "FocusMetrics",
    "SelectionThresholds",
    "VariantMetrics",
    "load_experiment_config",
    "select_development_variant",
    "summarize_observations",
    "validate_privacy_safe_report",
]
