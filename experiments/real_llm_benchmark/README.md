# Real local LLM benchmark

This experiment measures a model against approved records from correction
corpus v3 before it can be selected for the optional correction backend. It is
not part of fast CI and does not make a model a production dependency.

The committed v3 records initially have `pending-human-review` status and an
unfrozen holdout. Corpus approval is checked before runtime preflight, and the
runner fails before inference while no development case has been approved. It
never accepts pending candidates and never exposes holdout cases; the frozen
holdout belongs exclusively to the quality-gate path. The evaluation corpus is
prohibited as training data. The legacy v2 E2E fixture remains available only
when passed explicitly for reproducibility of historical runs.

## Preconditions

- Install Ollama and download a candidate model explicitly.
- Start the local Ollama service on loopback.
- Keep the machine offline after the model is present. The runner accepts only
  loopback URLs and sends the corpus text only to that local service.

For the Bielik Minitron 7B experiment, the explicit candidate is:

```bash
ollama pull hf.co/speakleash/Bielik-Minitron-7B-v3.0-Instruct-GGUF:Q4_K_M
```
For GGUF stacks served through a local OpenAI-compatible endpoint (including MLX),
an example candidate is `Llama-PLLuM-8B-instruct-2512`.

## Run

```bash
uv run python experiments/real_llm_benchmark/run_benchmark.py \
  --engine auto \
  --model hf.co/speakleash/Bielik-Minitron-7B-v3.0-Instruct-GGUF:Q4_K_M \
  --cache-probe \
  > experiments/real_llm_benchmark/results.json
```

`--cache-probe` sends each case twice with the identical versioned prompt. The
report records the first request as `cold_elapsed_ms` and the immediate repeat
as `warm_elapsed_ms`, together with cold and warm p50/p95 aggregates. Without
this flag, the only request is recorded as cold latency and the warm metrics
remain zero. Use the flag for every runtime comparison that evaluates prompt
cache benefit.

On macOS the benchmark defaults to `--engine mlx` for local inference stacks that
can provide an OpenAI-compatible chat endpoint. If needed, you can override to
`ollama` explicitly.

For MLX style local servers, use the default URL or provide your own:

```bash
mlx_lm.server \
  --model mlx-community/Qwen3-1.7B-4bit \
  --host 127.0.0.1 \
  --port 8080 \
  --prompt-cache-size 8 \
  --chat-template-args '{"enable_thinking":false}'

uv run python experiments/real_llm_benchmark/run_benchmark.py \
  --engine mlx \
  --base-url http://127.0.0.1:8080 \
  --model <local-model-id>
```

For Qwen reasoning variants, `enable_thinking=false` is required: otherwise
reasoning tokens can consume the JSON response budget before a finding payload
is emitted.

For Ollama, keep the same command shape:

```bash
uv run python experiments/real_llm_benchmark/run_benchmark.py \
  --engine ollama \
  --base-url http://127.0.0.1:11434 \
  --model <model-id>
```

The runner performs a health preflight before it sends any corpus case. With
`--engine auto`, it tries the preferred local runtime first and then the other
supported local runtime; it never changes the requested model identifier. An
explicit engine fails before scoring when its endpoint or requested model is
unavailable.

Generated reports are local evidence and must not be committed. They contain
only case identifiers and aggregate evidence, never analyzed source text or raw
model responses. A report records:

- the selected engine, requested model identifier, runtime version, artifact
  revision, quantization, hardware class, cold-start flag, and loaded memory
  when the runtime exposes it;
- SHA-256 of the exact corpus file;
- per-case status, exact TP/FP/FN, exact corrected-output result, validity,
  latency, and call count;
- aggregate exact category metrics, negative-case changes, response validity,
  generic p50/p95 latency, separate cold and warm p50/p95 latency, and
  character throughput.

Use the optional provenance flags when the local runtime cannot expose all
artifact details itself:

```bash
uv run python experiments/real_llm_benchmark/run_benchmark.py \
  --engine ollama \
  --model <model-id> \
  --artifact-revision <immutable-artifact-revision> \
  --quantization <quantization> \
  --runtime-version <runtime-version> \
  --hardware-class "Apple M4, 16 GB unified memory" \
  --operating-system "macOS 15.3.1" \
  --cold-start
```

Some OpenAI-compatible local servers, including the MLX server used in this
experiment, do not expose loaded memory through their HTTP API. Record a
measurement from a local process monitor explicitly in that case:

```bash
--loaded-memory-bytes <measured-byte-count>
```

The explicit value is provenance, not an estimate by the benchmark runner.

## Interpretation

`valid_empty` is a schema-valid response with no findings. It is not evidence
of linguistic recall: positive cases contribute their exact false negatives.
`invalid_schema`, `invalid_span`, `duplicate`, `conflict`, and
`application_failure` are recorded per case and make the run ineligible for a
safety claim. `unavailable` and `timed_out` are runtime outcomes, not zero
quality scores.

Every false positive is attributed to the category emitted by the model,
including on negative cases. Exact category metrics require category, original
span, original text, and replacement to match gold data. Existing ADR claims
are historical measurements only until a candidate is reproduced with this
runner.

## Selection rules

A candidate is immediately unsafe when one response fails strict JSON
validation, produces a duplicate/conflicting finding set, or changes a
negative case. The report itself does not invent quality thresholds:
per-category precision, recall, and F1 are used to record a measured baseline
in the ADR before any selection. A selected model also needs an explicit memory
observation and a documented offline smoke test.
