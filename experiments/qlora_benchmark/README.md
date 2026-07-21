# Bielik 1.5B MLX QLoRA benchmark

Issue #63 tests whether the pinned Bielik 1.5B MLX 8-bit model becomes a safe
Polish correction suggestion backend after narrow QLoRA training. The adapter
is rejected for production use.

## Fixed artifacts and configuration

- Model: `speakleash/Bielik-1.5B-v3.0-Instruct-MLX-8bit`, revision
  `a67fe1c442b12685cf2d1c32d02359d9e52c8ddd`, model weights SHA-256
  `4439362cc0cf36925d1769b51b81bb5a9b44c7eaa81be35768c9e89a5c560560`.
- Runtime: MLX-LM 0.31.3, MLX 0.32.0, Python 3.13.12.
- Hardware: Apple M4 Mac mini with 16 GB unified memory, macOS 15.3.1.
- Dataset: #62 train and validation hashes from `config.json`.
- Frozen corpus v3 SHA-256:
  `bd2c186bb22e32f948ed6592c24bc2267c6a2a77b185bd9424310068e680a1f2`.
- Generation: greedy, seed 42, 64-token cap. The longest expected validation
  target is 44 tokens with the pinned tokenizer.

The configuration uses completion-only loss, rank 8, eight adapted layers,
batch size 1, four-step gradient accumulation, 300 iterations, learning rate
`1e-5`, and sequence length 512. All model access was forced offline. Official
references are the [MLX-LM QLoRA guide](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md)
and the [Bielik model card](https://huggingface.co/speakleash/Bielik-1.5B-v3.0-Instruct).

## Training result

| Metric | Result |
| --- | ---: |
| Wall time | 206.3 s |
| Initial / final validation loss | 1.440 / 0.002 |
| Mean reported training throughput | 59.9 tokens/s |
| Peak MLX memory | 2.617 GB |
| Peak process RSS | 1,971,175,424 B |
| Swap growth | 0 B |
| Adapter size | 10,563,220 B |
| Adapter SHA-256 | `3d08a11801c3707ac92101f235cd7564372fef01f4e8a37335bde73042217160` |

Adapter weights, checkpoints, prepared training views, logs, and raw arm
reports remain in the local artifact cache and are not committed.

## Comparison

Every arm used the same case order and strict JSON validators. Prompt-only and
adapted arms used the #59 specialist prompt. The ablation retained the adapter
but replaced the specialist prompt with a minimal contract-only instruction.
The holdout used the corrected-text specialist for every focus because #63 does
not include a gold-independent finite-candidate detector for inflection. This
keeps the base and adapter comparison identical, but it does not qualify the
finite-candidate inflection path for production.

| Arm / split | Valid | Negative changes | Edit P / R / F1 | Exact outputs | Median / p95 | Peak MLX memory |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Prompt-only / validation | 10/240 | 0/60 | 0.000 / 0.000 / 0.000 | 0/240 | 1,184 / 1,503 ms | 2.035 GB |
| Adapter / validation | 240/240 | 0/60 | 1.000 / 1.000 / 1.000 | 240/240 | 778 / 1,011 ms | 2.335 GB |
| Adapter + prompt ablation / validation | 240/240 | 0/60 | 1.000 / 1.000 / 1.000 | 240/240 | 659 / 885 ms | 2.204 GB |
| Prompt-only / holdout | 0/160 | 0/40 | 0.000 / 0.000 / 0.000 | 0/160 | 1,108 / 1,212 ms | 2.032 GB |
| Adapter / holdout | 152/160 | 7/40 | 0.833 / 0.588 / 0.690 | 108/160 | 720 / 864 ms | 2.279 GB |

Validation does not demonstrate generalization: the prompt ablation remains
perfect, showing that the adapter learned the controlled synthetic task shape.
The independent holdout is materially better than prompt-only, but fails all
three mandatory suggestion-safety gates: valid responses must be 100%,
protected negatives changed must be zero, and edit precision must be at least
0.90.

## Reproduction

Prepare an exact local snapshot and keep the work directory outside the repo:

```bash
uv run python -m experiments.qlora_benchmark.run_training \
  --config experiments/qlora_benchmark/config.json \
  --model-snapshot /absolute/path/to/pinned/snapshot \
  --work-dir /absolute/path/outside/polis/qlora-run \
  --mlx-lora /absolute/path/to/mlx_lm.lora
```

Run each arm through the MLX-LM environment with the local project installed,
then assemble the privacy-safe summary:

```bash
uv run python -m experiments.qlora_benchmark.assemble_report \
  --training-metadata /outside/polis/training-metadata.json \
  --arm-report /outside/polis/prompt-only-validation.json \
  --arm-report /outside/polis/adapter-validation.json \
  --arm-report /outside/polis/adapter-ablation-validation.json \
  --arm-report /outside/polis/prompt-only-holdout.json \
  --arm-report /outside/polis/adapter-holdout.json \
  --output experiments/qlora_benchmark/report.json
```

`report.json` contains aggregate and per-focus metrics, artifact metadata,
resource evidence, and learning curves. It contains no analyzed source text or
raw model responses.
