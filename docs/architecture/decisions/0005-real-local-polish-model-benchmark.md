# ADR-0005: Do not select a real local LLM for automatic correction yet

- Status: Accepted
- Date: 2026-07-21
- Owner: Paweł Cyroń
- Issues: #42, #48

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

| Candidate | Quantization | Valid responses | Gold finding F1 | Negative safety | Median latency |
| --- | --- | ---: | ---: | --- | ---: |
| Qwen3 0.6B | Ollama default, 522 MB | 0/12 with v2; v3 emitted invalid findings | 0.000 | ineligible | 1,289 ms (v2) |
| Qwen3 1.7B | Ollama default, 1.4 GB | 12/12, empty findings | 0.000 | no changes | 390 ms (v2) |
| Bielik 1.5B v3.0 Instruct | GGUF Q8_0, 1.7 GB | 12/12, empty findings | 0.000 | no changes | 487 ms (v2) |
| Bielik 4.5B v3.0 Instruct | GGUF Q8_0, 5.1 GB | 11/12 | 0.000 | one invalid finding on a negative case | 1,581 ms |
| Qwen3 4B | Ollama default, 2.5 GB | invalid on probe | 0.000 | unsafe hallucinated span | 9,440 ms |
| Bielik Minitron 7B v3.0 Instruct | GGUF Q4_K_M, 4.5 GB on disk / 6.4 GB loaded | 2/12 | 0.000 | ineligible: ten responses failed validation | not used for selection |

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

## Decision

No real local model is selected for automatic correction in this release.
`mock-heu` remains the deterministic development backend only; it is not
evidence of contextual correction capability.

Issue #43 must not introduce a production real-model adapter until a candidate
meets explicit per-category quality gates on an expanded benchmark.

## Consequences

- The public API keeps returning deterministic rule findings and requires
  explicit selection before applying them.
- The planned sentence/paragraph convenience correction cannot claim LLM-based
  flexion or syntax coverage yet.
- A future candidate must be benchmarked with the same offline contract and
  must include memory measurement before selection.
