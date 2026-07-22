# Qwen3 1.7B sentence syntax qualification

Issue #74 tests whether materially different prompt operation can make the
smallest previously useful MLX model safe enough for reviewable residual syntax
suggestions on one Polish sentence. Paragraphs are not evaluated.

## Frozen scope

- model: `mlx-community/Qwen3-1.7B-4bit` at revision
  `3b1b1768f8f8cf8351c712464f906e86c2b8269e`;
- runtime: MLX-LM 0.31.3 with MLX 0.32.0 and thinking disabled;
- corpus: 69 development sentences from corpus v3 at SHA-256
  `bd2c186bb22e32f948ed6592c24bc2267c6a2a77b185bd9424310068e680a1f2`;
- configuration SHA-256:
  `9858f54577af201f9f4c134fc49e4498f32158dd0b1b2ca724a94957f6dca1f8`;
- no cloud calls, downloads during analysis, paragraph inputs, training, or
  automatic model corrections.

The source-only #69 router detects one of four residual syntax evidence kinds.
Gold edits, focus labels, and expected text remain in the scorer only. Names,
numbers, URLs, quotations, explicit entity spans, and deterministic finding
spans are protected. Every eligible sentence uses at most two model calls.

## Prompt operations

1. `generic_verified-v1` repeats the #69 proposal and generic verifier as the
   baseline.
2. `evidence_checklist_verified-v1` gives a separate instruction for
   government, missing reflexive `się`, subject agreement, or a missing
   `im…, tym…` correlative, then uses an evidence-specific verifier.
3. `diagnose_then_correct-v1` first asks only for the grammatical requirement
   and then asks a separate prompt to apply that diagnosis.

All responses use closed JSON schemas, deterministic generation, bounded
evidence windows, and validated minimal edits. A whitespace-equivalent
correlative insertion is normalized to the corpus's canonical half-open
offset without changing the produced sentence.

## Development result

| Variant | Valid | TP / FP / FN | Precision | Recall | Warm p95 | RSS | Max calls |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Generic + verifier | 68/69 | 4 / 3 / 21 | 0.571 | 0.160 | 742 ms | 1.327 GB | 2 |
| Evidence checklist + verifier | 67/69 | 1 / 0 / 24 | 1.000 | 0.040 | 661 ms | 1.327 GB | 2 |
| Diagnosis + correction | 69/69 | 2 / 1 / 23 | 0.667 | 0.080 | 1,062 ms | 1.327 GB | 2 |

All variants changed zero protected negatives, added zero swap, stayed below
the 2-second latency and 4-GiB memory limits, and respected the two-call cap.
None simultaneously reached response rate 1.00, precision 0.90, and recall
0.25. No variant was selected and corpus-v3 holdout remains unopened.

The experiment shows that splitting the work into multiple prompts does not
make this 1.7B model reliable for the current open-ended syntax operation. The
checklist increases precision only by abstaining almost everywhere; diagnostic
text from the small model does not provide a dependable intermediate state.

## Reproduction

Use the already prepared pinned snapshot. Model preparation may require network
access, but the server and all benchmark commands below run locally:

```console
/path/to/mlx_lm.server \
  --model /path/to/snapshot/3b1b1768f8f8cf8351c712464f906e86c2b8269e \
  --host 127.0.0.1 --port 8080 --log-level ERROR \
  --chat-template-args '{"enable_thinking":false}'

uv run --locked --extra dev python -m \
  experiments.sentence_syntax_qualification.run_benchmark \
  --variant generic_verified-v1 \
  --base-url http://127.0.0.1:8080 --runtime-pid PID \
  --output /private/work/generic.json
```

Repeat the run for the other two frozen variants, then assemble the report:

```console
uv run --locked --extra dev python -m \
  experiments.sentence_syntax_qualification.assemble_report \
  --config experiments/sentence_syntax_qualification/config.json \
  --run /private/work/generic.json \
  --run /private/work/checklist.json \
  --run /private/work/diagnose.json \
  --output experiments/sentence_syntax_qualification/report.json
```

Raw model responses and analyzed text are not written to the committed report.
The report retains only aggregate metrics and identifier-only case evidence.
