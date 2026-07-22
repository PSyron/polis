# Qwen3 1.7B sentence syntax qualification plan

**Issue:** #74

**Goal:** Qualify or reject one pinned Qwen3 1.7B MLX route for reviewable
residual syntax suggestions on one Polish sentence.

**Scope:** Sentence input only. Paragraphs, model matrices, fine-tuning, cloud
inference, automatic model corrections, and holdout tuning are excluded.

## Task 1: Freeze contracts and gates

- Add a configuration containing the one exact model revision, the frozen
  corpus hash, a small prompt-variant list, and the #74 selection gates.
- Add tests proving that routing and requests contain no gold or expected text.
- Add tests for single-sentence rejection and protected spans.

## Task 2: Implement prompt variants

- Reuse the source-only #69 evidence router.
- Add evidence-specific proposal and verifier contracts with strict JSON,
  deterministic generation, bounded edits, and at most two calls.
- Keep deterministic finding spans protected from model changes.
- Add fake-response tests for unchanged, accepted, rejected, malformed, and
  out-of-window results.

## Task 3: Implement scoring and one-shot selection

- Reuse corpus-v3 edit scoring while keeping gold in the scorer only.
- Report syntax precision/recall, valid outcomes, protected-negative changes,
  latency, memory, swap, and call counts for every predeclared variant.
- Freeze a selection only if every development gate passes.
- Permit a holdout run only from the frozen selection and reserve it atomically.

## Task 4: Run the real local experiment

- Start the pinned cached MLX snapshot on numeric loopback.
- Run the complete 69-sentence development split through each prompt variant.
- If no variant passes, keep holdout unopened. If one passes, freeze it before
  exactly one holdout run.
- Store only aggregate and privacy-safe per-case evidence.

## Task 5: Decide and verify

- Publish the reproducible report, commands, resource evidence, limitations,
  and an ADR that qualifies or rejects the exact route.
- Update the roadmap and #43 dependency status.
- Run Ruff, formatting, mypy, full pytest, and report integrity tests.
- Commit and push one focused #74 change, then close #74 only if all acceptance
  criteria are evidenced.
