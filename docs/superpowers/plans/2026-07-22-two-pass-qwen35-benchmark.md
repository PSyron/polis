# Constrained Qwen3.5 2B Benchmark Implementation Plan

> **Issue:** #68
>
> **Design:** `docs/superpowers/specs/2026-07-22-two-pass-qwen35-protocol-design.md`
>
> **Commit policy:** the repository's one-issue/one-focused-commit rule overrides
> per-task commits; commit all verified #68 deliverables once at the end.

## Goal

Implement and execute a reproducible, offline, two-pass Qwen3.5 2B benchmark
that can safely select or reject a frozen protocol before any analyzer wiring.
The benchmark must never use corpus labels in model input, must keep raw Polish
text and model responses outside the repository, and must not expose the frozen
holdout until a development variant passes every gate.

## Task 1: Add the diagnostic and constrained-correction contracts (TDD)

**Files:**

- Create `tests/test_two_pass_prompt_contract.py`.
- Modify `src/polis/llm/corrected_text.py`.
- Modify `src/polis/llm/__init__.py`.

**Steps:**

1. Add failing tests for the three predeclared diagnostic prompt variants,
   stable protocol/prompt hashes, JSON-schema strictness, and input delimiters.
2. Add failing tests proving the diagnostic validator accepts only `unchanged`
   or one supported focus with a unique, exact, single-line evidence fragment
   no longer than 80 characters; inflection evidence must be one token.
3. Add failing tests for the evidence-bound syntax/punctuation second pass:
   the closed `corrected_text` response, minimal changes intersecting or directly
   adjoining evidence, protected-token preservation, and safe rejection.
4. Run the focused tests and confirm they fail because the new API is absent.
5. Implement the minimum immutable request/response types, builders, validators,
   fixed schemas, fixed generation settings, and public exports.
6. Run the focused tests, existing corrected-text tests, Ruff, and mypy for the
   touched module.

## Task 2: Implement pure benchmark policy and reporting (TDD)

**Files:**

- Create `experiments/two_pass_qwen35/__init__.py`.
- Create `experiments/two_pass_qwen35/experiment.py`.
- Create `experiments/two_pass_qwen35/config.json`.
- Create `tests/test_two_pass_qwen35_benchmark.py`.

**Steps:**

1. Add failing tests for strict config loading: pinned model digest, runtime,
   corpus hash, exactly three prompt variants, thresholds, and local-only paths.
2. Add failing tests for case scoring from exact half-open edits, per-focus
   TP/FP/FN metrics, hard-negative changes, response validity, call count,
   latency percentiles, loaded memory, and swap delta.
3. Add failing tests for development eligibility and deterministic selection:
   100% valid responses, zero hard-negative suggestions, per-focus precision
   at least 0.90, per-focus recall at least 0.25, warm p95 at most 2 seconds,
   loaded memory at most 4 GiB, and swap growth at most 64 MiB.
4. Add failing tests that holdout is forbidden without a serialized frozen
   development selection and that committed reports reject raw text/responses.
5. Confirm RED, implement the smallest pure dataclasses/functions, then confirm
   GREEN and run Ruff/mypy on the new package.

## Task 3: Implement the local runner and privacy-preserving assembler (TDD)

**Files:**

- Create `experiments/two_pass_qwen35/run_benchmark.py`.
- Create `experiments/two_pass_qwen35/assemble_report.py`.
- Extend `tests/test_two_pass_qwen35_benchmark.py`.

**Steps:**

1. Add failing transport tests proving only loopback Ollama is accepted and the
   request uses schema-constrained chat, `think=false`, temperature zero, and
   the pinned model identifier.
2. Add failing orchestration tests with fakes: diagnostic abstention is one
   call; valid routing is at most two calls; invalid output safely abstains;
   inflection candidates come only from the local LanguageTool synthesizer;
   syntax/punctuation use the evidence-bound validator; corpus focus/expected
   output never appear in the request-building path.
3. Add failing CLI/assembler tests for development-only variant comparison,
   frozen-selection creation, holdout-once sentinel enforcement, aggregate
   hashes instead of raw text, and non-zero exit on a mandatory gate failure.
4. Confirm RED, implement local Ollama/LanguageTool adapters and orchestration,
   then confirm GREEN.

## Task 4: Execute development selection and conditional holdout

**Files outside repository:** raw run evidence and holdout sentinel under a
temporary benchmark directory.

**Steps:**

1. Verify Ollama 0.20.7, the full Qwen3.5 2B artifact digest, LanguageTool
   stdio availability, corpus hash, macOS/Apple M4/16 GiB metadata, and baseline
   swap usage.
2. Run all three variants on the approved development split, recording raw
   responses only outside the repository.
3. Assemble development metrics and select a variant only if every mandatory
   gate passes. If none passes, stop before holdout and record rejection.
4. If one passes, serialize the frozen selection outside the corpus, run the
   frozen holdout once, and record the sentinel before model calls so a failed
   execution cannot be silently repeated.
5. Collect warm/cold latency, loaded Ollama memory, process RSS, disk size, swap
   delta, call counts, exact edit metrics, focus metrics, and failure reasons.

## Task 5: Publish evidence and architecture decision

**Files:**

- Create `experiments/two_pass_qwen35/report.json`.
- Create `experiments/two_pass_qwen35/README.md`.
- Create `docs/architecture/decisions/0012-constrained-qwen35-protocol.md`.
- Modify `docs/architecture/README.md`.
- Modify `CHANGELOG.md`.

**Steps:**

1. Assemble the committed report from local evidence, retaining only case IDs,
   hashes, statuses, counts, aggregate metrics, provenance, and gate outcomes.
2. Document exact reproduction commands, selected/rejected status, limitations,
   privacy boundary, and why the result does or does not unblock #43.
3. Record ADR-0012 with the measured decision; never weaken gates after seeing
   results and never wire a rejected configuration into production.

## Task 6: Full verification, issue update, and focused commit

1. Run `ruff check .`.
2. Run `ruff format --check .`.
3. Run `mypy .`.
4. Run the full fast `pytest` suite and relevant opt-in LanguageTool tests.
5. Inspect `git diff --check`, report privacy, authorship, and changed-file scope.
6. Commit once as `research: benchmark constrained Qwen3.5 protocol (#68)`.
7. Push `main`; close #68 only if all acceptance criteria are evidenced. Update
   #43: remove `status:blocked` only when both development and holdout pass.
