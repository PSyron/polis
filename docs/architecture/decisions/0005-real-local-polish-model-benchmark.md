# ADR-0005: Do not select a real local LLM for automatic correction yet

- Status: Accepted
- Date: 2026-07-21
- Owner: Paweł Cyroń
- Issues: #42, #48, #50, #51, #61

## Context

Polis requires an offline model for conservative Polish inflection, syntax, and
punctuation correction. Candidate output must pass the versioned JSON contract,
cite exact offsets, preserve correct names and marked word order, and produce
minimal corrections.

The local benchmark used Ollama 0.20.7 on an Apple M4 with 16 GB unified
memory, corpus `polis_e2e_polish_correction_corpus_v2`, seed 42, temperature
0, `think: false`, and a 512-token output cap. All requests used the local
`/api/chat` endpoint only.

## Evidence

> Historical evidence notice: the measurements below predate the repaired
> scorer from issue #55. They remain useful for comparison, but they must not
> be used to select or qualify a runtime until reproduced with a report that
> records per-case outcomes, emitted-category false positives, runtime health,
> corpus hash, and artifact metadata.

| Candidate | Quantization | Valid responses | Gold finding F1 | Negative safety | Median latency |
| --- | --- | ---: | ---: | --- | ---: |
| Qwen3 0.6B | Ollama default, 522 MB | 0/12 with v2; v3 emitted invalid findings | 0.000 | ineligible | 1,289 ms (v2) |
| Qwen3 1.7B | Ollama default, 1.4 GB | 12/12, empty findings | 0.000 | no changes | 390 ms (v2) |
| Bielik 1.5B v3.0 Instruct | GGUF Q8_0, 1.7 GB | 12/12, empty findings | 0.000 | no changes | 487 ms (v2) |
| Bielik 4.5B v3.0 Instruct | GGUF Q8_0, 5.1 GB | 11/12 | 0.000 | one invalid finding on a negative case | 1,581 ms |
| Qwen3 4B | Ollama default, 2.5 GB | invalid on probe | 0.000 | unsafe hallucinated span | 9,440 ms |
| Bielik Minitron 7B v3.0 Instruct | GGUF Q4_K_M, 4.5 GB on disk / 6.4 GB loaded | 2/12 | 0.000 | ineligible: ten responses failed validation | not used for selection |
| Bielik 11B v3.0 Instruct | GGUF Q4_K_M, 6.7 GB on disk / 8.9 GB loaded | 10/25 with finding contract | 0.000 | no negative changes, but invalid responses make it ineligible | 1,391 ms for valid finding responses |

Prompt v1 produced 0/12 valid responses for Qwen3 0.6B and Bielik 1.5B.
Prompt v2 fixed response shape for Bielik but not correction quality. Prompt v3
explicitly states the correction task; it did not establish a qualifying model.
Qwen3 4B was additionally probed after the main comparison and returned a
hallucinated correction whose `original` did not match its cited range.

Issue #48 repeated the full corpus through the versioned CLI benchmark for the
official Bielik Minitron 7B Q4_K_M artefact. `ollama ps` reported 6.4 GB loaded
on the same local runtime. Only two of twelve responses passed the strict JSON
and offset contract; exact gold-finding F1 was 0.000 for agreement, inflection,
punctuation, and syntax. The runner's latency median deliberately excludes
invalid responses; because the candidate failed the validity gate, latency is
not used to support selection.

Issue #50 tested a separate corrected-text JSON contract on the expanded
25-case corpus. Bielik Minitron 7B returned valid one-field JSON for 25/25
requests, showing that offset generation was not the only blocker. It matched
only 6/25 gold outputs and changed 8 correct negative cases. Exact output
matches were 5/17 for inflection-tagged cases and 1/16 for both syntax- and
punctuation-tagged cases. The candidate fails the mandatory zero-negative
change safety gate and every per-category quality gate.

Issue #51 evaluated the larger Bielik 11B Q4_K_M candidate on the same
25-case corpus. The strict finding contract produced only 10/25 valid
responses and no exact gold findings, so its exact finding F1 was 0.000. The
median of valid finding responses was 1,391 ms; invalid responses are excluded
from that latency statistic.

A Polish specialist workflow then asked three separate corrected-text
questions about inflection, syntax, and punctuation and accepted a correction
only after deterministic validation and consensus. It produced a valid
consensus for 19/25 cases, matched 15/25 complete expected outputs, and changed
0/10 negative cases. Exact output coverage was 7/17 inflection-tagged cases,
7/16 syntax-tagged cases, and 8/16 punctuation-tagged cases. Controlled
specialist requests took approximately four to seven seconds each. This is a
large improvement over the single finding prompt, but it still fails the 100%
validity gate and remains far below the 0.90 per-category release gates.

### Reproduced runtime comparison (#61)

Issue #61 repeated the strict finding benchmark with the same 25-case corpus
split and prompt contract on macOS 15.3.1, Apple M4 Mac mini with 16 GB unified
memory.
The corpus SHA-256 was
`d5ce257f78a67ad2bdc6ed71ed1ec4f4403d0f287a71db7a316e68bd32f4d468`.
Each case was sent twice; the first call is the cache-cold measurement and the
immediate repeat is cache-warm. Both runs were local-only and had 25/25
schema-valid responses, zero changes to negative cases, and exact finding F1
of 0.000 (42 false negatives, no true positives). Thus the table compares
runtime cost and transport validity, not correction quality.

| Runtime / candidate | Artifact and configuration | Loaded memory | Cold p50/p95 | Warm p50/p95 | Throughput |
| --- | --- | ---: | ---: | ---: | ---: |
| MLX-LM 0.31.3 / MLX 0.32.0 | `mlx-community/Qwen3-1.7B-4bit`, revision `3b1b1768f8f8cf8351c712464f906e86c2b8269e`, 4-bit, `enable_thinking=false` | 1,305,067,520 B RSS | 380 / 405 ms | 318 / 332 ms | 135.8 chars/s |
| Ollama 0.20.7 | `qwen3:1.7b`, artifact `8f68893c685c`, Ollama default quantization | 2,355,771,424 B | 387 / 394 ms | 335 / 339 ms | 122.4 chars/s |
| MLX-LM 0.31.3 / MLX 0.32.0 | `speakleash/Bielik-1.5B-v3.0-Instruct-MLX-8bit`, revision `a67fe1c442b12685cf2d1c32d02359d9e52c8ddd`, 8-bit | 1,830,961,152 B RSS | 664 / 695 ms | 592 / 597 ms | 76.4 chars/s |
| Ollama 0.20.7 | `hf.co/speakleash/Bielik-1.5B-v3.0-Instruct-GGUF:Q8_0`, artifact `9ab8e213bb88`, Q8_0 | 2,145,648,640 B | 487 / 492 ms | 438 / 442 ms | 95.9 chars/s |

MLX-LM does not expose loaded memory through its OpenAI-compatible API; the
MLX value is an explicit macOS process RSS observation recorded in the report.
The server initially produced invalid responses because Qwen reasoning was
enabled; `enable_thinking=false` is necessary for this JSON-only benchmark
contract. MLX is faster and uses less memory for Qwen, while Ollama is faster
for Bielik. Neither runtime/model combination qualifies for correction because
valid empty findings have zero recall.

Measured installed sizes on that machine were 289,324 KiB for the `mlx-lm`
tool environment and 494,516 KiB for `Ollama.app`. Artifact cache sizes were
960,980 KiB for MLX Qwen and 1,661,112 KiB for MLX Bielik; `ollama list`
reported 1.4 GB for Qwen3 1.7B and 1.7 GB for Bielik 1.5B Q8_0. These values
include local packaging or cache overhead where applicable and are operational
observations, not model-parameter sizes.

## Decision

No real local model is selected for automatic correction in this release.
`mock-heu` remains the deterministic development backend only; it is not
evidence of contextual correction capability.

Issue #43 must not introduce a production real-model adapter until a candidate
meets explicit per-category quality gates on an expanded benchmark.

The next evaluation may combine a deterministic Polish rule engine with a
smaller local model, but that hybrid must receive its own benchmark and
architecture decision before it becomes a production dependency.

## Consequences

- The public API keeps returning deterministic rule findings and requires
  explicit selection before applying them.
- The planned sentence/paragraph convenience correction cannot claim LLM-based
  flexion or syntax coverage yet.
- A future candidate must be benchmarked with the same offline contract and
  must include memory measurement before selection.
