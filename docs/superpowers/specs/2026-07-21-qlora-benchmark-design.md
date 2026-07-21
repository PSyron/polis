# MLX QLoRA benchmark design (#63)

## Objective

Measure whether a local QLoRA adapter for the pinned Bielik 1.5B MLX 8-bit
artifact improves the selected specialist correction contracts enough to
justify its runtime cost. The adapter remains a local experiment artifact and
cannot authorize automatic correction.

## Fixed inputs

- Base model: `speakleash/Bielik-1.5B-v3.0-Instruct-MLX-8bit`, revision
  `a67fe1c442b12685cf2d1c32d02359d9e52c8ddd`, 8-bit.
- Runtime: MLX-LM 0.31.3 and MLX 0.32.0.
- Dataset: the exact #62 train and validation JSONL hashes recorded in its
  manifest.
- Evaluation corpus: frozen corpus v3, without exposing expected outputs to the
  runtime.
- Prompt contracts and deterministic generation settings: #59 version 1.0.
- Seed: 42.

Evaluation caps responses at 64 tokens. The pinned tokenizer measures the
longest expected validation target at 44 tokens (p95 33), so the cap preserves
headroom while preventing malformed runaway output from dominating latency.
The cap is identical for every arm.

The runner resolves the already-cached pinned snapshot and sets offline mode.
It does not download a model. Adapter weights, prepared MLX views, logs, raw
responses, and working reports remain outside the repository.

## Training

Use completion-only loss (`mask_prompt=true`) on the chat records, QLoRA rank
8 over eight layers, batch size 1 with four-step gradient accumulation, maximum
sequence length 512, and a bounded number of updates. A short preflight run
must measure peak memory and swap before the full run. The full run is invalid
if swap grows materially while training.

The committed experiment configuration is independent of local paths. A helper
materializes `train.jsonl` and `valid.jsonl` views and invokes MLX-LM with local
paths supplied at execution time.

## Comparison and ablation

Evaluate three arms with the same case order, seed, output cap, and strict JSON
validators:

1. pinned base model with the selected specialist prompt;
2. the same model and prompt with the adapter;
3. the adapter with a minimal contract-only prompt ablation.

Arm 1 versus arm 2 isolates adapter impact. Arm 2 versus arm 3 estimates how
much of the adapted result still depends on the selected prompt scaffolding.
Validation is scored first. The frozen holdout is read exactly once for the
final base-versus-adapter comparison after configuration is fixed.

## Predeclared selection rule

The adapter is eligible only when both validation and holdout have 100% valid
structured responses, zero changed protected hard negatives, and exact edit
precision at least 0.90. It must also improve validation exact-edit F1 by at
least 0.10 absolute over the prompt-only baseline without reducing complete
output accuracy. Otherwise it is rejected. Low recall may be reported but
cannot compensate for a failed safety, validity, or precision gate.

## Evidence

Commit configuration, pure scoring/selection code, deterministic report schema,
tests, summarized learning curves, environment and artifact hashes, latency,
throughput, peak resident memory, swap delta, and an ADR. Never commit adapter
weights or analyzed raw responses.
