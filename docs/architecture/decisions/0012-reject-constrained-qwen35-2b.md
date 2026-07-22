# ADR-0012: Reject the constrained Qwen3.5 2B protocol

- Status: Accepted
- Date: 2026-07-22
- Owner: Paweł Cyroń
- Issue: #68

## Context

ADR-0009 rejected direct specialist prompting and ADR-0011 rejected the Bielik
1.5B QLoRA configuration. Issue #67 consequently specified a two-pass protocol:
one diagnostic call may name one focus and exact source fragment, then one
constrained operation may select a LanguageTool inflection form or return an
evidence-bound syntax or punctuation correction.

Issue #68 implemented the closed schemas, application validators, prompt and
artifact hashes, privacy-safe runner, development selection, and holdout-once
guard. It evaluated the pinned Apache-2.0 `qwen3.5:2b-mxfp8` digest through
Ollama 0.20.7 on the 16 GiB Apple M4 target. The model remained optional and
local; no text, response, weights, or cache entered the repository.

The final development matrix used three predeclared prompts on 80 reviewed
cases. `strict` returned 62 valid outcomes and five false-positive edits;
`checklist` returned 66 valid outcomes, four false-positive edits, and changed
one protected negative. Neither produced an exact true-positive edit. Their
warm p95 values were 2.776 and 2.897 seconds, above the 2-second gate.

`counterexample` returned 80/80 valid outcomes, changed no protected negative,
and had a 383 ms warm p95, but it returned unchanged for every case. It therefore
had zero exact recall for inflection, syntax, and punctuation. All variants had
zero exact true-positive edits. Ollama's reported loaded allocation also rose
above the 4 GiB gate, reaching 10,636,404,490 bytes after the final sequential
variant; local runner RSS remained about 2.7 GB and swap growth was 92,662,661
bytes, also above the 64 MiB gate.

No variant passed development, so no configuration was frozen and the 160-case
holdout was not accessed.

## Decision

Reject the exact constrained Qwen3.5 2B MXFP8 configuration from #68 for the
#43 production suggestion backend.

Do not weaken the response-validity, protected-negative, precision, recall,
latency, memory, or two-call gates. Do not enable the unchanged-only variant:
its safety is achieved by providing no useful correction capability.

## Consequences

- #43 remains fail-closed and blocked; no real local-model backend is selected.
- The two-pass request types and validators remain reusable experimental
  contracts, but they confer no production qualification.
- The corpus-v3 holdout remains unconsumed by this experiment.
- A follow-up must be a new predeclared experiment. The preferred direction is
  deterministic category routing with a small model limited to one residual
  task, rather than another category-neutral prompt over the same model.
- Runtime-native JSON schema cannot be trusted for this Ollama MLX artifact;
  application validation remains authoritative and prompts must state exact
  response shapes.
