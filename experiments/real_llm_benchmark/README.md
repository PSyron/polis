# Real local LLM benchmark

This experiment measures a model against the versioned E2E corpus before it can
be selected for the optional correction backend. It is not part of fast CI and
does not make a model a production dependency.

## Preconditions

- Install Ollama and download a candidate model explicitly.
- Start the local Ollama service on loopback.
- Keep the machine offline after the model is present. The runner accepts only
  loopback URLs and sends the corpus text only to that local service.

For the Bielik Minitron 7B experiment, the explicit candidate is:

```bash
ollama pull hf.co/speakleash/Bielik-Minitron-7B-v3.0-Instruct-GGUF:Q4_K_M
```

## Run

```bash
uv run python experiments/real_llm_benchmark/run_benchmark.py \
  --model hf.co/speakleash/Bielik-Minitron-7B-v3.0-Instruct-GGUF:Q4_K_M \
  > experiments/real_llm_benchmark/results.json
```

The JSON report records valid response count, changed negative cases, median
latency, and exact finding metrics for every category represented by a gold
finding. Generated reports are local evidence and must not be committed.

## Selection rules

A candidate is immediately unsafe when one response fails strict JSON
validation or when it changes a negative case. The report itself does not
invent quality thresholds: per-category precision, recall, and F1 are used to
record a measured baseline in the ADR before any selection. A selected model
also needs an explicit memory observation and a documented offline smoke test.
