# ADR-0013: Reject the sentence-only category-routing matrix

- Status: Accepted
- Date: 2026-07-22
- Owner: Paweł Cyroń
- Issue: #69

## Context

ADR-0012 rejected category-neutral Qwen3.5 2B because no prompt produced an
exact true-positive edit. Issue #69 tested the preferred follow-up:
deterministic routing removes classification from the model, the pinned
LanguageTool subset owns qualified punctuation evidence, and a compact local
model sees only one residual syntax task for one sentence.

The implementation keeps gold outside routing, protects names, numbers, URLs,
and quotations, bounds each proposal to one evidence window, and permits at
most two model calls. The frozen development matrix contained Qwen3 1.7B MLX
4-bit, Bielik 1.5B MLX 8-bit, and Qwen3 0.6B through Ollama. All work remained
local; no raw text, responses, weights, or caches entered the repository.

On 69 sentence cases, Qwen3 1.7B was strongest. It returned 68 structured
outcomes, changed no protected negative, produced four exact syntax edits and
three false positives (precision 0.571, recall 0.160), and ran at about 747 ms
warm p95 with about 1.31 GB loaded RSS. Bielik returned 58 structured outcomes
and no exact syntax edit. Qwen3 0.6B returned 68 structured outcomes, no exact
syntax edit, and five false-positive syntax edits. All stayed within latency,
memory, and swap limits.

The deterministic punctuation channel produced one exact edit at precision
1.000 and recall 0.038. Deterministic inflection produced no contextual edit.
The current LanguageTool subset remains far below the punctuation recall gate,
while synthesis alone cannot select an inflected form.

## Decision

Reject all three exact configurations for the #43 production suggestion
backend. Do not freeze a winner and do not access corpus-v3 holdout.

Keep the sentence router, evidence contract, protected-span validator,
privacy-safe scorer, Ollama JSON-mode regression, and holdout-once guard as
experimental evidence. They do not qualify a model or deterministic source.

## Consequences

- #43 remains fail-closed and blocked.
- Category routing improves on #68, but is not release-ready.
- Paragraph correction remains outside this experiment.
- The next useful work must improve deterministic coverage: a broader reviewed
  Polish LanguageTool rule allowlist and a gold-independent contextual
  inflection detector/ranker are the measured gaps.
- Another prompt-only comparison of these same configurations is not justified
  without new deterministic evidence or a materially different operation.

## Alternatives considered

- **Lower the gates.** Rejected because malformed and false edits would become
  production suggestions.
- **Open holdout for Qwen3 1.7B.** Rejected by the frozen one-shot policy.
- **Select Bielik for zero false syntax edits.** Rejected because it had zero
  syntax utility and only 58/69 structured outcomes.
