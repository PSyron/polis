from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from experiments.qlora_benchmark.experiment import (
    ArmMetrics,
    build_mlx_training_config,
    load_experiment_config,
    parse_mlx_training_log,
    prepare_mlx_dataset,
    select_adapter,
    validate_report,
    verify_pinned_artifacts,
)

ROOT = Path(__file__).parents[1]
CONFIG_PATH = ROOT / "experiments" / "qlora_benchmark" / "config.json"
REPORT_PATH = ROOT / "experiments" / "qlora_benchmark" / "report.json"
DATASET = ROOT / "data" / "finetuning" / "bielik_1_5b_v1"
CORPUS = ROOT / "tests" / "fixtures" / "evaluation" / "polish_correction_corpus_v3.json"
MODEL_SNAPSHOT = (
    Path.home()
    / ".cache"
    / "huggingface"
    / "hub"
    / "models--speakleash--Bielik-1.5B-v3.0-Instruct-MLX-8bit"
    / "snapshots"
    / "a67fe1c442b12685cf2d1c32d02359d9e52c8ddd"
)


def test_committed_training_config_is_closed_pinned_and_16gb_bounded() -> None:
    config = load_experiment_config(CONFIG_PATH)

    assert config.base_model.revision == MODEL_SNAPSHOT.name
    assert config.runtime.mlx_lm_version == "0.31.3"
    assert config.training.seed == 42
    assert config.training.mask_prompt is True
    assert config.training.batch_size == 1
    assert config.training.max_seq_length == 512
    assert config.training.lora_parameters == {
        "rank": 8,
        "dropout": 0.0,
        "scale": 16.0,
    }
    assert config.selection.minimum_validation_f1_delta == 0.1
    assert config.selection.maximum_training_swap_delta_bytes == 64 * 1024 * 1024


@pytest.mark.skipif(not MODEL_SNAPSHOT.exists(), reason="pinned local model absent")
def test_pinned_local_artifact_and_dataset_hashes_match() -> None:
    config = load_experiment_config(CONFIG_PATH)
    verify_pinned_artifacts(
        config,
        model_snapshot=MODEL_SNAPSHOT,
        dataset_directory=DATASET,
        corpus_v3_path=CORPUS,
    )


def test_artifact_verification_rejects_wrong_revision(tmp_path: Path) -> None:
    config = load_experiment_config(CONFIG_PATH)
    with pytest.raises(ValueError, match="revision"):
        verify_pinned_artifacts(
            config,
            model_snapshot=tmp_path / "wrong-revision",
            dataset_directory=DATASET,
            corpus_v3_path=CORPUS,
        )


def test_prepared_mlx_data_contains_only_chat_messages(tmp_path: Path) -> None:
    config = load_experiment_config(CONFIG_PATH)
    hashes = prepare_mlx_dataset(
        config,
        dataset_directory=DATASET,
        corpus_v3_path=CORPUS,
        output_directory=tmp_path,
    )
    assert set(hashes) == {"train", "valid"}
    assert (
        len((tmp_path / "train.jsonl").read_text(encoding="utf-8").splitlines())
        == 1_200
    )
    assert (
        len((tmp_path / "valid.jsonl").read_text(encoding="utf-8").splitlines()) == 240
    )
    first = json.loads(
        (tmp_path / "train.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert set(first) == {"messages"}
    assert [message["role"] for message in first["messages"]] == [
        "system",
        "user",
        "assistant",
    ]


def test_mlx_config_uses_only_explicit_local_paths(tmp_path: Path) -> None:
    config = load_experiment_config(CONFIG_PATH)
    actual = build_mlx_training_config(
        config,
        model_snapshot=tmp_path / config.base_model.revision,
        data_directory=tmp_path / "data",
        adapter_directory=tmp_path / "adapter",
        iterations=2,
    )
    assert actual["train"] is True
    assert actual["iters"] == 2
    assert actual["mask_prompt"] is True
    assert actual["model"] == str(tmp_path / config.base_model.revision)
    assert actual["data"] == str(tmp_path / "data")
    assert actual["adapter_path"] == str(tmp_path / "adapter")


def test_learning_curve_parser_extracts_train_and_validation_evidence() -> None:
    points = parse_mlx_training_log(
        "Iter 1: Val loss 2.345, Val took 1.2s\n"
        "Iter 10: Train loss 1.234, Learning Rate 1.000e-05, "
        "It/sec 0.500, Tokens/sec 123.400, Trained Tokens 1000, Peak mem 4.200 GB\n"
    )
    assert [(point.iteration, point.kind, point.loss) for point in points] == [
        (1, "validation", 2.345),
        (10, "train", 1.234),
    ]
    assert points[1].tokens_per_second == 123.4
    assert points[1].peak_memory_gb == 4.2


def test_selection_accepts_only_material_safe_adapter() -> None:
    config = load_experiment_config(CONFIG_PATH)
    validation_base = _metrics(
        "prompt_only", "validation", tp=30, fp=10, fn=30, exact=70
    )
    validation_adapter = _metrics(
        "adapter", "validation", tp=48, fp=2, fn=12, exact=100
    )
    holdout_base = _metrics("prompt_only", "holdout", tp=20, fp=8, fn=40, exact=70)
    holdout_adapter = _metrics("adapter", "holdout", tp=42, fp=4, fn=18, exact=95)

    result = select_adapter(
        config.selection,
        validation_base=validation_base,
        validation_adapter=validation_adapter,
        holdout_base=holdout_base,
        holdout_adapter=holdout_adapter,
    )

    assert result.decision == "select"
    assert result.reasons == ()
    assert result.validation_f1_delta >= 0.1


def test_selection_rejects_material_training_swap_growth() -> None:
    config = load_experiment_config(CONFIG_PATH)
    base = _metrics("prompt_only", "validation", tp=30, fp=10, fn=30, exact=70)
    adapter = _metrics("adapter", "validation", tp=48, fp=2, fn=12, exact=100)
    result = select_adapter(
        config.selection,
        validation_base=base,
        validation_adapter=adapter,
        holdout_base=replace(base, split="holdout", total_cases=160),
        holdout_adapter=_metrics("adapter", "holdout", tp=42, fp=4, fn=18, exact=95),
        training_swap_delta_bytes=64 * 1024 * 1024 + 1,
    )
    assert result.decision == "reject"
    assert "training swap gate failed" in result.reasons


@pytest.mark.parametrize(
    ("mutation", "reason"),
    (
        ({"valid_responses": 239}, "structured-response"),
        ({"negative_changes": 1}, "protected-negative"),
        ({"false_positive_edits": 8}, "edit-precision"),
        ({"true_positive_edits": 31, "false_negative_edits": 29}, "material F1"),
    ),
)
def test_selection_rejects_each_failed_gate(
    mutation: dict[str, int], reason: str
) -> None:
    config = load_experiment_config(CONFIG_PATH)
    base = _metrics("prompt_only", "validation", tp=30, fp=10, fn=30, exact=70)
    adapter = replace(
        _metrics("adapter", "validation", tp=48, fp=2, fn=12, exact=100),
        **cast(dict[str, Any], mutation),
    )
    holdout_base = replace(base, arm="prompt_only", split="holdout", total_cases=160)
    holdout_adapter = _metrics("adapter", "holdout", tp=42, fp=4, fn=18, exact=95)

    result = select_adapter(
        config.selection,
        validation_base=base,
        validation_adapter=adapter,
        holdout_base=holdout_base,
        holdout_adapter=holdout_adapter,
    )

    assert result.decision == "reject"
    assert any(reason in item for item in result.reasons)


def test_report_requires_all_arms_and_rejects_raw_text() -> None:
    config = load_experiment_config(CONFIG_PATH)
    focus_metrics: dict[str, object] = {
        "inflection": {},
        "syntax": {},
        "punctuation": {},
    }
    arms: list[dict[str, object]] = [
        {"arm": "prompt_only", "split": "validation", "focus_metrics": focus_metrics},
        {"arm": "adapter", "split": "validation", "focus_metrics": focus_metrics},
        {
            "arm": "adapter_prompt_ablation",
            "split": "validation",
            "focus_metrics": focus_metrics,
        },
        {"arm": "prompt_only", "split": "holdout", "focus_metrics": focus_metrics},
        {"arm": "adapter", "split": "holdout", "focus_metrics": focus_metrics},
    ]
    report: dict[str, object] = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "configuration_sha256": "0" * 64,
        "environment": {},
        "artifacts": {},
        "training": {},
        "arms": arms,
        "selection": {},
    }
    assert validate_report(report, config)["arms"] == arms
    cast(list[dict[str, object]], report["arms"])[0]["source_text"] = "private"
    with pytest.raises(ValueError, match="raw analyzed text"):
        validate_report(report, config)


def test_committed_report_rejects_adapter_without_raw_text() -> None:
    config = load_experiment_config(CONFIG_PATH)
    raw = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    report = validate_report(raw, config)
    assert (
        report["configuration_sha256"]
        == hashlib.sha256(CONFIG_PATH.read_bytes()).hexdigest()
    )
    selection = cast(dict[str, object], report["selection"])
    assert selection["decision"] == "reject"
    assert selection["reasons"] == [
        "holdout structured-response gate failed",
        "holdout protected-negative gate failed",
        "holdout edit-precision gate failed",
    ]
    assert "source_text" not in REPORT_PATH.read_text(encoding="utf-8")
    assert "raw_response" not in REPORT_PATH.read_text(encoding="utf-8")
    arms = cast(list[dict[str, object]], report["arms"])
    for arm in arms:
        focus_metrics = cast(dict[str, object], arm["focus_metrics"])
        assert set(focus_metrics) == {"inflection", "syntax", "punctuation"}


def _metrics(
    arm: str,
    split: str,
    *,
    tp: int,
    fp: int,
    fn: int,
    exact: int,
) -> ArmMetrics:
    total = 240 if split == "validation" else 160
    return ArmMetrics(
        arm=arm,
        split=split,
        total_cases=total,
        valid_responses=total,
        negative_cases=60 if split == "validation" else 40,
        negative_changes=0,
        true_positive_edits=tp,
        false_positive_edits=fp,
        false_negative_edits=fn,
        exact_output_matches=exact,
        median_latency_ms=500.0,
        p95_latency_ms=700.0,
        throughput_chars_per_second=70.0,
    )
