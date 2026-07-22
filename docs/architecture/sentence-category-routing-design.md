# Sentence Category Routing Design

- Status: Accepted for issue #69
- Date: 2026-07-22
- Owner: Paweł Cyroń

## Objective

Qualify or reject a rules-first offline correction path for one Polish sentence.
Deterministic components handle the punctuation and inflection work they can
justify from source evidence. A compact local model sees only a prequalified,
residual syntax task. Paragraph routing and paragraph-level correction are not
part of this experiment.

## Approaches considered

### 1. Deterministic categories with a syntax-only model

Run the pinned LanguageTool rule subset for qualified punctuation, use its
tagger and synthesizer as evidence for finite inflection forms, and invoke a
compact model only for a sentence that has an independently detected residual
syntax condition. This removes category classification from the model and is
the selected approach.

### 2. Project-authored punctuation and morphology heuristics

Reimplement more Polish grammar detection in Python, using LanguageTool only
as a dictionary. This could reduce Java integration, but it duplicates reviewed
linguistic assets and would need a much larger negative corpus to establish the
same precision. It is rejected for issue #69.

### 3. One category-specific model request for every category

Ask separate model prompts about punctuation, inflection, and syntax. This is
rejected because it spends calls on categories deterministic evidence can
handle, increases latency, and exceeds the two-call sentence budget when more
than one category is suspected.

## Sentence-only data flow

1. Reject empty input and input containing more than one segmented sentence
   from this experiment's eligible set.
2. Run deterministic Polis rules and the pinned LanguageTool 6.8 check
   operation without consulting corpus metadata, focus labels, or expected
   output.
3. Normalize deterministic findings and apply only sources already permitted by
   their source policy. Measure punctuation and inflection paths independently.
4. Derive one residual syntax evidence window from source text and deterministic
   findings. URLs, numbers, quoted text, and named-entity spans are protected.
5. If no residual syntax evidence exists, return the deterministic result with
   no model call.
6. Otherwise send one syntax-only request containing the sentence, exact
   evidence window, deterministic findings, and protected spans.
7. Validate the closed response schema and require either unchanged text or one
   minimal proposal wholly inside the evidence window and outside protected
   spans.
8. If a proposal exists, spend the second and final call on a binary verifier.
   Accepted model edits remain reviewable suggestions and are never applied
   automatically.

## Routing boundary

The router may inspect only the input sentence, segment offsets, deterministic
findings, and local LanguageTool analysis. It may not inspect case identifiers,
corpus stratum, tags, expected output, gold edits, or benchmark focus. A test
must prove that changing evaluation labels while preserving source evidence
does not change routing.

The first implementation is deliberately narrow. It supports only evidence
patterns that can be stated before evaluation and that produce one unambiguous
sentence-local window. Unsupported input returns no model task. Prefer no
suggestion to an unjustified suggestion.

## Model matrix

The development matrix is frozen before execution and contains at most three
compact configurations:

1. `mlx-community/Qwen3-1.7B-4bit` through the local MLX runtime;
2. `speakleash/Bielik-1.5B-v3.0-Instruct-MLX-8bit` through the local MLX
   runtime;
3. `qwen3:0.6b` through the pinned local Ollama runtime as a speed control.

Each configuration uses the same syntax-only request contract, deterministic
temperature, response limit, application validator, and two-call ceiling.
Model artifacts and caches stay outside the repository. A missing runtime or
artifact is an explicit unavailable result, never an implicit download.

## Scoring and selection

Development uses the 80 reviewed corpus-v3 development cases. The combined
pipeline reports deterministic punctuation, deterministic inflection, and
model-assisted residual syntax separately as well as together. Routing is
executed without gold; gold is opened only by the scorer after outputs are
recorded.

A configuration is eligible only with all of the following:

- 100% structured outcomes;
- zero suggestions on protected hard negatives;
- exact edit precision at least 0.90;
- recall at least 0.25 for every category the combined pipeline claims to
  support;
- warm end-to-end p95 at most 2,000 ms;
- loaded model memory at most 4 GiB;
- swap growth at most 64 MiB;
- no more than two model calls for a sentence.

The winner is selected by gate pass, then higher minimum supported-focus
recall, then lower warm p95, then lower loaded memory. The selected configuration
and all hashes are frozen before the holdout is reserved. Holdout runs once and
only if every development gate passes. Otherwise issue #43 remains fail-closed.

## Failure and privacy behavior

Malformed output, timeout, unavailable runtime, broad rewrite, protected-span
change, out-of-window edit, or verifier disagreement rejects the model proposal
without removing deterministic findings. Controlled diagnostics contain case
identifiers and aggregate metrics only. Source text, raw model responses,
weights, caches, and machine-specific work files are not committed.

## Verification

Fast tests cover sentence eligibility, gold-independent routing, evidence
windows, protected spans, schemas, application validation, selection ordering,
privacy-safe reports, and the one-shot holdout guard. The real development
benchmark is marked slow/model. The issue also requires the full repository
quality suite, distribution artifact checks, and opt-in vendored LanguageTool
integration before its single focused commit is created.
