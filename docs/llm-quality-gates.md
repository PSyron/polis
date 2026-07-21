# Local LLM quality gates

Polis selects a local model only after it passes the versioned E2E corpus. A
model that is fast, fluent, or merely produces JSON is not selected by itself.
The gates apply to the exact finding span and replacement, not to a rewritten
sentence that happens to look plausible.

## Mandatory safety gates

- **100%** of corpus responses must pass the strict response schema and exact
  source-span validation.
- **0** negative cases may be changed or receive a finding. This includes
  correct inflected names, surnames, and marked but grammatical word order.
- Requests must remain local after the explicit model download; the runtime
  endpoint must be loopback-only.

Failure of any safety gate rejects the model regardless of quality metrics.

## Per-category quality gates

For `inflection`, `syntax`, and `punctuation`, exact finding precision, recall,
and F1 must each be at least **0.90**. The benchmark reports an additional
global precision, recall, and F1, but a strong global score cannot compensate
for a weak category.

The 0.90 threshold is a release gate, not a claim that the current baseline
reaches it. The baselines documented in ADR-0005 are below the gate; they
demonstrate why no candidate has been selected yet. Any future relaxation
requires a new ADR with measured risk, a corpus review, and an explicit safety
analysis.

## Selection evidence

The selection issue must link the generated benchmark report, record the exact
model and quantization, loaded memory observation, runtime version, corpus
version, and offline smoke result. Only then may the production adapter issue
proceed.
