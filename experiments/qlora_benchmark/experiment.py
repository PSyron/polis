"""Pure configuration, preparation, scoring, and selection logic for #63."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, cast

from polis.evaluation.finetuning_dataset import (
    FinetuningRecord,
    load_finetuning_bundle,
)

Decision = Literal["select", "reject"]

_TOP_LEVEL_FIELDS: Final = frozenset(
    {
        "schema_version",
        "experiment_id",
        "base_model",
        "runtime",
        "dataset",
        "training",
        "generation",
        "selection",
    }
)


@dataclass(frozen=True, slots=True)
class BaseModelConfig:
    identifier: str
    revision: str
    weights_sha256: str
    quantization: str


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    mlx_lm_version: str
    mlx_version: str
    python_version: str


@dataclass(frozen=True, slots=True)
class DatasetHashes:
    train_sha256: str
    validation_sha256: str
    corpus_v3_sha256: str


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    seed: int
    fine_tune_type: str
    optimizer: str
    mask_prompt: bool
    num_layers: int
    batch_size: int
    grad_accumulation_steps: int
    iters: int
    learning_rate: float
    max_seq_length: int
    steps_per_report: int
    steps_per_eval: int
    val_batches: int
    save_every: int
    grad_checkpoint: bool
    lora_parameters: dict[str, float | int]


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    seed: int
    temperature: float
    top_p: float
    max_tokens: int


@dataclass(frozen=True, slots=True)
class SelectionThresholds:
    minimum_edit_precision: float
    required_valid_response_rate: float
    maximum_negative_changes: int
    maximum_training_swap_delta_bytes: int
    minimum_validation_f1_delta: float
    minimum_complete_output_delta: float


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    schema_version: int
    experiment_id: str
    base_model: BaseModelConfig
    runtime: RuntimeConfig
    dataset: DatasetHashes
    training: TrainingConfig
    generation: GenerationConfig
    selection: SelectionThresholds


@dataclass(frozen=True, slots=True)
class ArmMetrics:
    arm: str
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
    p95_latency_ms: float
    throughput_chars_per_second: float
    loaded_memory_bytes: int | None = None

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
        if not denominator:
            return 0.0
        return 2 * self.edit_precision * self.edit_recall / denominator

    @property
    def complete_output_accuracy(self) -> float:
        return self.exact_output_matches / self.total_cases if self.total_cases else 0.0


@dataclass(frozen=True, slots=True)
class SelectionResult:
    decision: Decision
    reasons: tuple[str, ...]
    validation_f1_delta: float
    validation_complete_output_delta: float


@dataclass(frozen=True, slots=True)
class LearningCurvePoint:
    iteration: int
    kind: Literal["train", "validation"]
    loss: float
    tokens_per_second: float | None = None
    peak_memory_gb: float | None = None


def load_experiment_config(path: Path) -> ExperimentConfig:
    """Load the closed, versioned QLoRA experiment configuration."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    root = _mapping(raw, "configuration")
    _exact_fields(root, _TOP_LEVEL_FIELDS, "configuration")
    if root["schema_version"] != 1:
        raise ValueError("experiment schema_version must be 1")
    base = _closed_mapping(
        root["base_model"],
        {"identifier", "revision", "weights_sha256", "quantization"},
        "base_model",
    )
    runtime = _closed_mapping(
        root["runtime"],
        {"mlx_lm_version", "mlx_version", "python_version"},
        "runtime",
    )
    dataset = _closed_mapping(
        root["dataset"],
        {"train_sha256", "validation_sha256", "corpus_v3_sha256"},
        "dataset",
    )
    training = _closed_mapping(
        root["training"],
        {
            "seed",
            "fine_tune_type",
            "optimizer",
            "mask_prompt",
            "num_layers",
            "batch_size",
            "grad_accumulation_steps",
            "iters",
            "learning_rate",
            "max_seq_length",
            "steps_per_report",
            "steps_per_eval",
            "val_batches",
            "save_every",
            "grad_checkpoint",
            "lora_parameters",
        },
        "training",
    )
    generation = _closed_mapping(
        root["generation"],
        {"seed", "temperature", "top_p", "max_tokens"},
        "generation",
    )
    selection = _closed_mapping(
        root["selection"],
        {
            "minimum_edit_precision",
            "required_valid_response_rate",
            "maximum_negative_changes",
            "maximum_training_swap_delta_bytes",
            "minimum_validation_f1_delta",
            "minimum_complete_output_delta",
        },
        "selection",
    )
    lora = _closed_mapping(
        training["lora_parameters"], {"rank", "dropout", "scale"}, "lora_parameters"
    )
    config = ExperimentConfig(
        schema_version=1,
        experiment_id=_string(root["experiment_id"], "experiment_id"),
        base_model=BaseModelConfig(
            _string(base["identifier"], "model identifier"),
            _git_revision(base["revision"], "model revision"),
            _sha(base["weights_sha256"], "weights hash"),
            _string(base["quantization"], "quantization"),
        ),
        runtime=RuntimeConfig(
            _string(runtime["mlx_lm_version"], "mlx_lm_version"),
            _string(runtime["mlx_version"], "mlx_version"),
            _string(runtime["python_version"], "python_version"),
        ),
        dataset=DatasetHashes(
            _sha(dataset["train_sha256"], "train hash"),
            _sha(dataset["validation_sha256"], "validation hash"),
            _sha(dataset["corpus_v3_sha256"], "corpus hash"),
        ),
        training=TrainingConfig(
            _positive_int(training["seed"], "seed", allow_zero=True),
            _choice(training["fine_tune_type"], {"lora"}, "fine_tune_type"),
            _choice(training["optimizer"], {"adam"}, "optimizer"),
            _boolean(training["mask_prompt"], "mask_prompt"),
            _positive_int(training["num_layers"], "num_layers"),
            _positive_int(training["batch_size"], "batch_size"),
            _positive_int(
                training["grad_accumulation_steps"], "grad_accumulation_steps"
            ),
            _positive_int(training["iters"], "iters"),
            _positive_float(training["learning_rate"], "learning_rate"),
            _positive_int(training["max_seq_length"], "max_seq_length"),
            _positive_int(training["steps_per_report"], "steps_per_report"),
            _positive_int(training["steps_per_eval"], "steps_per_eval"),
            _positive_int(training["val_batches"], "val_batches"),
            _positive_int(training["save_every"], "save_every"),
            _boolean(training["grad_checkpoint"], "grad_checkpoint"),
            {
                "rank": _positive_int(lora["rank"], "LoRA rank"),
                "dropout": _non_negative_float(lora["dropout"], "LoRA dropout"),
                "scale": _positive_float(lora["scale"], "LoRA scale"),
            },
        ),
        generation=GenerationConfig(
            _positive_int(generation["seed"], "generation seed", allow_zero=True),
            _non_negative_float(generation["temperature"], "temperature"),
            _probability(generation["top_p"], "top_p", zero_allowed=False),
            _positive_int(generation["max_tokens"], "max_tokens"),
        ),
        selection=SelectionThresholds(
            _probability(selection["minimum_edit_precision"], "edit precision"),
            _probability(
                selection["required_valid_response_rate"], "valid response rate"
            ),
            _positive_int(
                selection["maximum_negative_changes"],
                "maximum negative changes",
                allow_zero=True,
            ),
            _positive_int(
                selection["maximum_training_swap_delta_bytes"],
                "maximum training swap delta",
                allow_zero=True,
            ),
            _probability(selection["minimum_validation_f1_delta"], "F1 delta"),
            _probability(
                selection["minimum_complete_output_delta"],
                "complete output delta",
            ),
        ),
    )
    if not config.training.mask_prompt:
        raise ValueError("completion-only QLoRA requires mask_prompt=true")
    if config.training.max_seq_length > 512:
        raise ValueError("16 GB experiment max_seq_length must not exceed 512")
    return config


def verify_pinned_artifacts(
    config: ExperimentConfig,
    *,
    model_snapshot: Path,
    dataset_directory: Path,
    corpus_v3_path: Path,
) -> None:
    """Fail closed unless every pinned local artifact matches configuration."""

    if model_snapshot.name != config.base_model.revision:
        raise ValueError("local model snapshot revision does not match configuration")
    checks = (
        (model_snapshot / "model.safetensors", config.base_model.weights_sha256),
        (dataset_directory / "train.jsonl", config.dataset.train_sha256),
        (
            dataset_directory / "validation.jsonl",
            config.dataset.validation_sha256,
        ),
        (corpus_v3_path, config.dataset.corpus_v3_sha256),
    )
    for path, expected in checks:
        if not path.is_file() or _file_sha256(path) != expected:
            raise ValueError(f"artifact hash mismatch: {path.name}")


def prepare_mlx_dataset(
    config: ExperimentConfig,
    *,
    dataset_directory: Path,
    corpus_v3_path: Path,
    output_directory: Path,
) -> dict[str, str]:
    """Create minimal MLX chat views outside the repository after isolation checks."""

    bundle = load_finetuning_bundle(
        dataset_directory, evaluation_corpus_path=corpus_v3_path
    )
    expected = {
        "train": config.dataset.train_sha256,
        "validation": config.dataset.validation_sha256,
    }
    for name, digest in expected.items():
        if _file_sha256(dataset_directory / f"{name}.jsonl") != digest:
            raise ValueError(f"{name} dataset hash mismatch")
    if _file_sha256(corpus_v3_path) != config.dataset.corpus_v3_sha256:
        raise ValueError("corpus v3 hash mismatch")
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = {
        "train": output_directory / "train.jsonl",
        "valid": output_directory / "valid.jsonl",
    }
    _write_chat_view(paths["train"], bundle.train)
    _write_chat_view(paths["valid"], bundle.validation)
    return {name: _file_sha256(path) for name, path in paths.items()}


def build_mlx_training_config(
    config: ExperimentConfig,
    *,
    model_snapshot: Path,
    data_directory: Path,
    adapter_directory: Path,
    iterations: int | None = None,
) -> dict[str, object]:
    """Translate the path-independent contract into MLX-LM 0.31.3 options."""

    training = config.training
    return {
        "model": str(model_snapshot),
        "train": True,
        "fine_tune_type": training.fine_tune_type,
        "optimizer": training.optimizer,
        "data": str(data_directory),
        "seed": training.seed,
        "num_layers": training.num_layers,
        "batch_size": training.batch_size,
        "iters": iterations if iterations is not None else training.iters,
        "val_batches": training.val_batches,
        "learning_rate": training.learning_rate,
        "steps_per_report": training.steps_per_report,
        "steps_per_eval": training.steps_per_eval,
        "grad_accumulation_steps": training.grad_accumulation_steps,
        "adapter_path": str(adapter_directory),
        "save_every": training.save_every,
        "max_seq_length": training.max_seq_length,
        "grad_checkpoint": training.grad_checkpoint,
        "lora_parameters": training.lora_parameters,
        "mask_prompt": training.mask_prompt,
        "report_to": None,
    }


def select_adapter(
    thresholds: SelectionThresholds,
    *,
    validation_base: ArmMetrics,
    validation_adapter: ArmMetrics,
    holdout_base: ArmMetrics,
    holdout_adapter: ArmMetrics,
    training_swap_delta_bytes: int = 0,
) -> SelectionResult:
    """Apply the predeclared adapter eligibility and improvement rule."""

    reasons: list[str] = []
    if training_swap_delta_bytes > thresholds.maximum_training_swap_delta_bytes:
        reasons.append("training swap gate failed")
    for metrics in (validation_adapter, holdout_adapter):
        label = metrics.split
        if metrics.valid_response_rate != thresholds.required_valid_response_rate:
            reasons.append(f"{label} structured-response gate failed")
        if metrics.negative_changes > thresholds.maximum_negative_changes:
            reasons.append(f"{label} protected-negative gate failed")
        if metrics.edit_precision < thresholds.minimum_edit_precision:
            reasons.append(f"{label} edit-precision gate failed")
    f1_delta = validation_adapter.edit_f1 - validation_base.edit_f1
    complete_delta = (
        validation_adapter.complete_output_accuracy
        - validation_base.complete_output_accuracy
    )
    if f1_delta < thresholds.minimum_validation_f1_delta:
        reasons.append("validation material F1 improvement gate failed")
    if complete_delta < thresholds.minimum_complete_output_delta:
        reasons.append("validation complete-output non-regression gate failed")
    if holdout_adapter.edit_f1 < holdout_base.edit_f1:
        reasons.append("holdout edit F1 regressed")
    return SelectionResult(
        decision="reject" if reasons else "select",
        reasons=tuple(reasons),
        validation_f1_delta=f1_delta,
        validation_complete_output_delta=complete_delta,
    )


def validate_report(raw: object, config: ExperimentConfig) -> dict[str, object]:
    """Validate committed summary evidence without accepting raw model text."""

    report = _closed_mapping(
        raw,
        {
            "schema_version",
            "experiment_id",
            "configuration_sha256",
            "environment",
            "artifacts",
            "training",
            "arms",
            "selection",
        },
        "report",
    )
    if report["schema_version"] != 1:
        raise ValueError("report schema_version must be 1")
    if report["experiment_id"] != config.experiment_id:
        raise ValueError("report experiment_id mismatch")
    arms = report["arms"]
    if not isinstance(arms, list) or len(arms) < 5:
        raise ValueError("report must contain validation, ablation, and holdout arms")
    required_pairs = {
        ("prompt_only", "validation"),
        ("adapter", "validation"),
        ("adapter_prompt_ablation", "validation"),
        ("prompt_only", "holdout"),
        ("adapter", "holdout"),
    }
    actual_pairs: set[tuple[str, str]] = set()
    for arm_raw in arms:
        arm = _mapping(arm_raw, "report arm")
        if "raw_response" in arm or "source_text" in arm:
            raise ValueError("report cannot contain raw analyzed text")
        name = _string(arm.get("arm"), "arm name")
        split = _string(arm.get("split"), "arm split")
        focus_metrics = _mapping(arm.get("focus_metrics"), "focus metrics")
        if set(focus_metrics) != {"inflection", "syntax", "punctuation"}:
            raise ValueError("report focus metrics are incomplete")
        for focus, metrics in focus_metrics.items():
            _mapping(metrics, f"{focus} focus metrics")
        actual_pairs.add((name, split))
    if not required_pairs <= actual_pairs:
        raise ValueError("report comparison arms are incomplete")
    return dict(report)


def summarize_latencies(values: Sequence[float]) -> tuple[float, float]:
    if not values or any(value < 0 or not math.isfinite(value) for value in values):
        raise ValueError("latencies must be finite non-negative values")
    ordered = sorted(values)
    median = ordered[len(ordered) // 2]
    p95 = ordered[math.ceil(0.95 * len(ordered)) - 1]
    return median, p95


def parse_mlx_training_log(text: str) -> tuple[LearningCurvePoint, ...]:
    """Extract stable learning-curve fields from MLX-LM 0.31.3 console output."""

    points: list[LearningCurvePoint] = []
    pattern = re.compile(
        r"Iter\s+(?P<iteration>\d+):\s+"
        r"(?P<kind>Train|Val) loss (?P<loss>\d+(?:\.\d+)?)"
        r"(?P<rest>[^\n]*)"
    )
    for match in pattern.finditer(text):
        rest = match.group("rest")
        tokens = re.search(r"Tokens/sec\s+([0-9.]+)", rest)
        memory = re.search(r"Peak mem\s+([0-9.]+)\s+GB", rest)
        points.append(
            LearningCurvePoint(
                iteration=int(match.group("iteration")),
                kind="train" if match.group("kind") == "Train" else "validation",
                loss=float(match.group("loss")),
                tokens_per_second=float(tokens.group(1)) if tokens else None,
                peak_memory_gb=float(memory.group(1)) if memory else None,
            )
        )
    return tuple(points)


def _write_chat_view(path: Path, records: Sequence[FinetuningRecord]) -> None:
    lines = []
    for record in records:
        messages = [
            {"role": message.role, "content": message.content}
            for message in record.messages
        ]
        lines.append(
            json.dumps(
                {"messages": messages}, ensure_ascii=False, separators=(",", ":")
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
        raise ValueError(f"{label} fields are malformed")


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _sha(value: object, label: str) -> str:
    text = _string(value, label)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return text


def _git_revision(value: object, label: str) -> str:
    text = _string(value, label)
    if len(text) != 40 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{label} must be a lowercase 40-character revision")
    return text


def _choice(value: object, choices: set[str], label: str) -> str:
    text = _string(value, label)
    if text not in choices:
        raise ValueError(f"{label} is unsupported")
    return text


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{label} must be a boolean")
    return value


def _positive_int(value: object, label: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    if value < 0 if allow_zero else value <= 0:
        raise ValueError(f"{label} is out of range")
    return value


def _non_negative_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{label} is out of range")
    return result


def _positive_float(value: object, label: str) -> float:
    result = _non_negative_float(value, label)
    if result == 0:
        raise ValueError(f"{label} must be positive")
    return result


def _probability(value: object, label: str, *, zero_allowed: bool = True) -> float:
    result = _non_negative_float(value, label)
    if result > 1 or (not zero_allowed and result == 0):
        raise ValueError(f"{label} must be in the permitted probability range")
    return result


__all__ = [
    "ArmMetrics",
    "ExperimentConfig",
    "LearningCurvePoint",
    "SelectionResult",
    "build_mlx_training_config",
    "load_experiment_config",
    "prepare_mlx_dataset",
    "parse_mlx_training_log",
    "select_adapter",
    "summarize_latencies",
    "validate_report",
    "verify_pinned_artifacts",
]
