# Constrained Qwen3.5 2B two-pass benchmark

Issue #68 evaluates the protocol specified in #67. The exact
`qwen3.5:2b-mxfp8` configuration is rejected. No production backend is enabled,
and the frozen corpus-v3 holdout was not opened because no development variant
passed the mandatory gates.

## Frozen configuration

- Model: `qwen3.5:2b-mxfp8`, full digest
  `3a4a00dbfb1dd2c9e4cb2052bd61c37ee45e9b7a71a022bc4101d29e868c9e30`.
- License: Apache-2.0; local artifact size: 3,117,471,137 bytes.
- Runtime: Ollama 0.20.7 with the MLX runner on an Apple M4 Mac mini, 16 GiB
  unified memory, macOS 15.3.1, arm64.
- Corpus: `polish_correction_corpus_v3.json`, SHA-256
  `bd2c186bb22e32f948ed6592c24bc2267c6a2a77b185bd9424310068e680a1f2`.
- Generation: seed 42, temperature 0, top-p 0.95, `num_ctx=4096`;
  diagnostics use at most 128 output tokens.
- Diagnostic hashes: `strict` `159fc7d8…a5805`, `checklist`
  `3837e181…15db6`, and `counterexample` `dc65176a…25390`.
- Second-pass hashes: inflection candidate `9b1fb3d1…91bc1`, syntax
  `e3ec179a…5d407`, and punctuation `0970d9dd…2d394`.

The full values and every threshold are in `config.json`. `verify_prompt_hashes`
reconstructs all prompts before inference and fails closed on any mismatch.

## Runtime compatibility finding

An initial local pilot found that this Ollama MLX artifact ignored the native
JSON Schema supplied in `format` and generated explanatory fields. The
application validator correctly rejected every response. The final frozen
prompts therefore state the only permitted JSON shapes explicitly while still
requesting runtime schema enforcement. This transport correction was verified
before the reported development run; the invalid pilot was not scored and its
local evidence was not committed.

## Development result

All three predeclared variants ran once over the same 80 human-reviewed
development cases. Exact half-open edits were scored; unchanged hard negatives
were protected. Memory is Ollama's post-variant `size_vram`; RSS is the local
MLX runner process. Warm latency excludes the first case.

| Variant | Valid | Negative changes | TP / FP / FN | Cold / warm p95 | Throughput | Calls mean / max | Loaded / RSS | Swap growth |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| strict | 62/80 | 0/20 | 0 / 5 / 81 | 2,420 / 2,784 ms | 43.1 char/s | 1.30 / 2 | 5.392 / 2.641 GB | 0 B |
| checklist | 66/80 | 1/20 | 0 / 4 / 81 | 2,686 / 2,886 ms | 33.4 char/s | 1.53 / 2 | 8.629 / 2.664 GB | 0 B |
| counterexample | 80/80 | 0/20 | 0 / 0 / 81 | 867 / 355 ms | 121.3 char/s | 1.00 / 1 | 10.636 / 2.659 GB | 92,662,661 B |

Every focus had zero exact true-positive edits and zero recall. `strict` and
`checklist` also failed response validity, edit precision, syntax precision,
warm p95, and loaded-memory gates; `checklist` changed one protected negative.
`counterexample` was structurally valid, fast, and safe but returned unchanged
for every case, so it failed all three per-focus recall gates and the explicit
unchanged-only exclusion. Ollama's reported loaded allocation also accumulated
above the 4 GiB limit across the sequential run. Process RSS stayed near
2.7 GB, but final swap growth also exceeded the 64 MiB threshold.

`report.json` contains the complete aggregate, per-focus, resource, and
case-ID/hash evidence. It contains no source sentence, corrected sentence, raw
response, model file, or cache.

## Reproduction

Install the pinned model explicitly, build the vendored LanguageTool Polish
module, and keep work files outside the repository:

```bash
third_party/languagetool-pl/scripts/build.sh
ollama pull qwen3.5:2b-mxfp8
run_dir="$(mktemp -d /tmp/polis-two-pass-qwen35.XXXXXX)"
uv run python -m experiments.two_pass_qwen35.run_benchmark \
  --config experiments/two_pass_qwen35/config.json \
  --work-dir "$run_dir" \
  --split development
```

The development command exits with status 2 when no variant qualifies. It does
not create `selection.json`; therefore this rejected result cannot reserve or
run the holdout. For an eligible future configuration, a separate holdout call
would first atomically create `holdout.started`, preventing a silent rerun.

Assemble a privacy-safe rejection report:

```bash
uv run python -m experiments.two_pass_qwen35.assemble_report \
  --config experiments/two_pass_qwen35/config.json \
  --development "$run_dir/development.json" \
  --output experiments/two_pass_qwen35/report.json
```

## Consequence

The failure is not solved by accepting a larger rewrite surface or relaxing
precision. Qwen3.5 2B with `think=false` cannot reliably route all three Polish
categories, while `think=true` exhausted the tested reasoning budget without a
final response and was already too slow. A future experiment should use
deterministic category routing and reserve a small model for one narrowly
defined residual operation, or predeclare a different compact model. It needs a
new issue and new development protocol; the corpus-v3 holdout remains untouched
by #68.
