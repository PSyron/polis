"""Evaluate one pinned MLX model arm without committing raw analyzed text."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast

from experiments.qlora_benchmark.experiment import (
    ArmMetrics,
    load_experiment_config,
    summarize_latencies,
    verify_pinned_artifacts,
)
from experiments.role_prompt_benchmark.run_benchmark import _infer_focus
from polis.evaluation.correction_corpus import (
    load_correction_corpus_json,
)
from polis.evaluation.finetuning_dataset import (
    FinetuningRecord,
    load_finetuning_bundle,
)
from polis.llm import (
    FiniteCandidate,
    build_specialist_corrected_text_prompt_request,
)
from polis.llm.corrected_text import (
    SpecialistFocus,
    derive_text_edits,
    validate_candidate_selection_response,
    validate_corrected_text_response,
)

ROOT = Path(__file__).parents[2]
DEFAULT_CONFIG = ROOT / "experiments" / "qlora_benchmark" / "config.json"
DEFAULT_DATASET = ROOT / "data" / "finetuning" / "bielik_1_5b_v1"
DEFAULT_CORPUS = (
    ROOT / "tests" / "fixtures" / "evaluation" / "polish_correction_corpus_v3.json"
)

ArmName = Literal["prompt_only", "adapter", "adapter_prompt_ablation"]
SplitName = Literal["validation", "holdout"]


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    id: str
    source: str
    expected: str
    focus: SpecialistFocus
    negative: bool
    messages: tuple[dict[str, str], ...]
    protocol_id: str
    candidates: tuple[FiniteCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class CaseEvidence:
    case_id: str
    valid_response: bool
    exact_output_match: bool
    negative_changed: bool
    true_positive_edits: int
    false_positive_edits: int
    false_negative_edits: int
    elapsed_ms: float
    output_sha256: str


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--model-snapshot", type=Path, required=True)
    parser.add_argument("--adapter-path", type=Path)
    parser.add_argument(
        "--arm",
        choices=("prompt_only", "adapter", "adapter_prompt_ablation"),
        required=True,
    )
    parser.add_argument("--split", choices=("validation", "holdout"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    config = load_experiment_config(args.config)
    verify_pinned_artifacts(
        config,
        model_snapshot=args.model_snapshot,
        dataset_directory=DEFAULT_DATASET,
        corpus_v3_path=DEFAULT_CORPUS,
    )
    arm = cast(ArmName, args.arm)
    split = cast(SplitName, args.split)
    if arm == "prompt_only" and args.adapter_path is not None:
        raise ValueError("prompt_only arm cannot load an adapter")
    if arm != "prompt_only" and args.adapter_path is None:
        raise ValueError("adapter arms require --adapter-path")
    if split == "holdout" and arm == "adapter_prompt_ablation":
        raise ValueError("prompt ablation is validation-only")
    output = args.output.resolve()
    if _inside(output, ROOT):
        raise ValueError("raw evaluation evidence must stay outside the repository")

    os.environ.update(
        {
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
        }
    )
    import mlx.core as mx  # type: ignore[import-not-found]
    from mlx_lm import generate, load  # type: ignore[import-not-found]
    from mlx_lm.sample_utils import make_sampler  # type: ignore[import-not-found]

    cases = _validation_cases(arm) if split == "validation" else _holdout_cases()
    model, tokenizer = load(
        str(args.model_snapshot.resolve()),
        adapter_path=str(args.adapter_path.resolve()) if args.adapter_path else None,
    )
    sampler = make_sampler(
        temp=config.generation.temperature,
        top_p=config.generation.top_p,
    )
    evidence: list[CaseEvidence] = []
    output_characters = 0
    for index, case in enumerate(cases):
        mx.random.seed(config.generation.seed)
        prompt = tokenizer.apply_chat_template(
            list(case.messages), tokenize=False, add_generation_prompt=True
        )
        started = time.perf_counter()
        raw = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=config.generation.max_tokens,
            sampler=sampler,
            verbose=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1_000
        output_characters += len(raw)
        evidence.append(_score_case(case, raw, elapsed_ms))
        if (index + 1) % 20 == 0:
            print(f"{arm}/{split}: {index + 1}/{len(cases)}", flush=True)
    metrics = _summarize(
        arm,
        split,
        evidence,
        output_characters=output_characters,
        loaded_memory_bytes=round(mx.get_peak_memory()),
    )
    payload = {
        "schema_version": 1,
        "experiment_id": config.experiment_id,
        "arm": arm,
        "split": split,
        "model_revision": config.base_model.revision,
        "adapter_sha256": (
            _sha256(args.adapter_path / "adapters.safetensors")
            if args.adapter_path
            else None
        ),
        "metrics": _metrics_payload(metrics),
        "case_evidence": [asdict(item) for item in evidence],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(output)
    return 0


def _validation_cases(arm: ArmName) -> tuple[EvaluationCase, ...]:
    bundle = load_finetuning_bundle(
        DEFAULT_DATASET, evaluation_corpus_path=DEFAULT_CORPUS
    )
    return tuple(
        _from_training_record(record, ablate=arm.endswith("ablation"))
        for record in bundle.validation
    )


def _from_training_record(record: FinetuningRecord, *, ablate: bool) -> EvaluationCase:
    expected = _record_expected_output(record)
    messages = (
        _ablation_messages(record)
        if ablate
        else tuple(
            {"role": message.role, "content": message.content}
            for message in record.messages[:2]
        )
    )
    return EvaluationCase(
        id=record.id,
        source=record.source_text,
        expected=expected,
        focus=cast(SpecialistFocus, record.focus),
        negative=record.category == "no_change",
        messages=messages,
        protocol_id=record.protocol_id,
        candidates=record.candidates,
    )


def _holdout_cases() -> tuple[EvaluationCase, ...]:
    corpus = load_correction_corpus_json(DEFAULT_CORPUS)
    cases = []
    for case in corpus.cases:
        if case.split != "holdout":
            continue
        focus = _infer_focus(case.tags, case.stratum)
        request = build_specialist_corrected_text_prompt_request(
            case.input, focus=focus
        )
        cases.append(
            EvaluationCase(
                id=case.id,
                source=case.input,
                expected=case.expected_output,
                focus=focus,
                negative=not case.edits,
                messages=request.messages,
                protocol_id=request.protocol_id,
            )
        )
    if len(cases) != 160:
        raise ValueError("frozen holdout must contain 160 cases")
    return tuple(cases)


def _ablation_messages(record: FinetuningRecord) -> tuple[dict[str, str], ...]:
    if record.protocol_id == "specialist-candidate-selection":
        payload: dict[str, object] = {
            "text": record.source_text,
            "candidates": [asdict(candidate) for candidate in record.candidates],
        }
        instruction = (
            'Wybierz candidate_id albo zwróć {"unchanged":true}. Odpowiedz JSON.'
        )
    else:
        payload = {"focus": record.focus, "text": record.source_text}
        instruction = "Zwróć JSON z jednym polem corrected_text."
    return (
        {"role": "system", "content": "Koryguj minimalnie tekst w języku polskim."},
        {
            "role": "user",
            "content": instruction
            + "\n<INPUT_JSON_START>\n"
            + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            + "\n</INPUT_JSON_END>",
        },
    )


def _record_expected_output(record: FinetuningRecord) -> str:
    if record.target.corrected_text is not None:
        return cast(str, record.target.corrected_text)
    selected = next(
        candidate
        for candidate in record.candidates
        if candidate.candidate_id == record.target.candidate_id
    )
    return cast(
        str,
        record.source_text[: selected.start]
        + selected.form
        + record.source_text[selected.end :],
    )


def _score_case(case: EvaluationCase, raw: str, elapsed_ms: float) -> CaseEvidence:
    valid = True
    try:
        if case.protocol_id == "specialist-candidate-selection":
            candidate_id = validate_candidate_selection_response(
                raw,
                candidate_ids=[candidate.candidate_id for candidate in case.candidates],
            )
            corrected = case.source
            if candidate_id is not None:
                selected = next(
                    candidate
                    for candidate in case.candidates
                    if candidate.candidate_id == candidate_id
                )
                corrected = (
                    case.source[: selected.start]
                    + selected.form
                    + case.source[selected.end :]
                )
        else:
            corrected = validate_corrected_text_response(
                raw, source_text=case.source, focus=case.focus
            )
        predicted_edits = set(derive_text_edits(case.source, corrected))
    except (ValueError, TypeError, json.JSONDecodeError):
        valid = False
        corrected = case.source
        predicted_edits = set()
    gold_edits = set(derive_text_edits(case.source, case.expected))
    true_positives = len(predicted_edits & gold_edits)
    false_positives = len(predicted_edits - gold_edits)
    false_negatives = len(gold_edits - predicted_edits)
    return CaseEvidence(
        case_id=case.id,
        valid_response=valid,
        exact_output_match=valid and corrected == case.expected,
        negative_changed=case.negative and bool(predicted_edits),
        true_positive_edits=true_positives,
        false_positive_edits=false_positives,
        false_negative_edits=false_negatives,
        elapsed_ms=elapsed_ms,
        output_sha256=hashlib.sha256(corrected.encode("utf-8")).hexdigest(),
    )


def _summarize(
    arm: ArmName,
    split: SplitName,
    evidence: list[CaseEvidence],
    *,
    output_characters: int,
    loaded_memory_bytes: int,
) -> ArmMetrics:
    median, p95 = summarize_latencies([item.elapsed_ms for item in evidence])
    seconds = sum(item.elapsed_ms for item in evidence) / 1_000
    return ArmMetrics(
        arm=arm,
        split=split,
        total_cases=len(evidence),
        valid_responses=sum(item.valid_response for item in evidence),
        negative_cases=60 if split == "validation" else 40,
        negative_changes=sum(item.negative_changed for item in evidence),
        true_positive_edits=sum(item.true_positive_edits for item in evidence),
        false_positive_edits=sum(item.false_positive_edits for item in evidence),
        false_negative_edits=sum(item.false_negative_edits for item in evidence),
        exact_output_matches=sum(item.exact_output_match for item in evidence),
        median_latency_ms=median,
        p95_latency_ms=p95,
        throughput_chars_per_second=output_characters / seconds if seconds else 0.0,
        loaded_memory_bytes=loaded_memory_bytes,
    )


def _metrics_payload(metrics: ArmMetrics) -> dict[str, object]:
    payload = asdict(metrics)
    payload.update(
        {
            "valid_response_rate": metrics.valid_response_rate,
            "edit_precision": metrics.edit_precision,
            "edit_recall": metrics.edit_recall,
            "edit_f1": metrics.edit_f1,
            "complete_output_accuracy": metrics.complete_output_accuracy,
        }
    )
    return payload


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
