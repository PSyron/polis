# Sentence-only category routing benchmark

This experiment implements issue #69 for one reviewed Polish sentence at a
time. The pinned LanguageTool 6.8 subset handles its two allowlisted
punctuation rules, deterministic inflection is measured separately, and a
compact local model receives only a prequalified residual syntax window.
Paragraph correction is excluded.

Routing sees only source text, deterministic findings, and locally derived
protected spans. Corpus stratum, tags, expected output, and gold edits remain in
a separate evaluation wrapper used only by scoring.

## Frozen matrix

| Configuration | Runtime | Revision | License |
| --- | --- | --- | --- |
| `qwen3-1.7b-mlx-4bit` | MLX | `3b1b1768f8f8cf8351c712464f906e86c2b8269e` | Apache-2.0 |
| `bielik-1.5b-mlx-8bit` | MLX | `a67fe1c442b12685cf2d1c32d02359d9e52c8ddd` | Apache-2.0 |
| `qwen3-0.6b-ollama` | Ollama | `sha256-7f4030143c1c477224c5434f8272c662a8b042079a0a584f0a27a1684fe2e1fa` | Apache-2.0 |

The corpus SHA-256 is
`bd2c186bb22e32f948ed6592c24bc2267c6a2a77b185bd9424310068e680a1f2`.
Development contains 69 sentence cases; 11 short paragraphs are excluded by
the sentence-only scope. Model files and caches remain outside the repository
and the runner never downloads them.

## Protocol

The router recognizes four predeclared syntax evidence kinds: government,
missing reflexive, subject agreement, and missing correlative. Unsupported
sentences make no model call. An eligible request contains the sentence as
delimited data, one exact half-open evidence window, and protected spans for
names, numbers, URLs, and quotations.

The first response has the closed shape
`{"corrected_text":"pełne zdanie"}`. The application rejects broad,
out-of-window, and protected-span changes. Unchanged stops after one call. A
proposal spends the second and final call on a binary verifier. Accepted model
output remains suggestion-only.

Ollama uses plain JSON mode, not runtime JSON Schema compilation. Qwen3 0.6B
reproducibly returned HTTP 500 with the full runtime schema (`failed to load
model vocabulary required for format`). JSON mode works, while application
validation still enforces the complete closed contract.

## Reproduction

Build the pinned local LanguageTool module:

```bash
POLIS_LT_OFFLINE=1 third_party/languagetool-pl/scripts/build.sh
```

Start one pinned MLX snapshot and run its development slice:

```bash
mlx_lm.server \
  --model /absolute/path/to/pinned-mlx-snapshot \
  --host 127.0.0.1 --port 8080 --log-level ERROR

uv run --locked --extra dev python -m \
  experiments.sentence_category_routing.run_benchmark \
  --model-name qwen3-1.7b-mlx-4bit \
  --base-url http://127.0.0.1:8080 \
  --runtime-pid PID \
  --output /private/work/qwen17.json
```

Run the installed Ollama control:

```bash
uv run --locked --extra dev python -m \
  experiments.sentence_category_routing.run_benchmark \
  --model-name qwen3-0.6b-ollama \
  --base-url http://127.0.0.1:11434 \
  --output /private/work/qwen06.json
```

Combine one run per frozen configuration:

```bash
uv run --locked --extra dev python -m \
  experiments.sentence_category_routing.assemble_report \
  --config experiments/sentence_category_routing/config.json \
  --run /private/work/qwen17.json \
  --run /private/work/bielik15.json \
  --run /private/work/qwen06.json \
  --output experiments/sentence_category_routing/report.json
```

Intermediate work files stay outside the repository. The committed report has
identifiers, counts, hashes, and aggregate metrics only.

## Development result

| Configuration | Structured | Protected changes | Overall TP / FP | Syntax precision / recall | Warm p95 | Loaded memory | Swap growth |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Qwen3 1.7B MLX 4-bit | 68/69 | 0 | 5 / 3 | 0.571 / 0.160 | 747 ms | 1.31 GB | 0 B |
| Bielik 1.5B MLX 8-bit | 58/69 | 0 | 1 / 0 | 0.000 / 0.000 | 1,076 ms | 1.91 GB | 0 B |
| Qwen3 0.6B Ollama | 68/69 | 0 | 1 / 5 | 0.000 / 0.000 | 1,022 ms | 0.79 GB | 0 B |

The deterministic LanguageTool punctuation channel produced one exact edit,
precision 1.000, and recall 0.038. Deterministic inflection produced no edit
and recall 0.000. The current two-rule subset and context-free synthesizer do
not provide contextual inflection correction.

No configuration passed 100% structured outcomes, overall precision 0.90, and
recall 0.25 for both claimed categories. No winner was frozen and holdout was
not accessed. `report.json` contains the exact aggregate evidence.

## Decision

Reject all three configurations for the production backend. Qwen3 1.7B MLX
proves that category routing improves over #68's zero true positives and meets
the speed and resource gates, but its precision and recall remain too low.
Issue #43 remains fail-closed.
