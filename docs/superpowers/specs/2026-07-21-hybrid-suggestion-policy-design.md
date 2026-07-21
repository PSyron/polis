# Hybrid Suggestion Policy Design

## Status and scope

This design completes issue #60 under accepted ADR-0008. It implements the
rules-first orchestration and safety policy with injected fakes and
model-independent interfaces. It does not select or configure a real model,
runtime, or morphology process; those remain later M5 responsibilities.

## Components

`polis.analysis.hybrid` owns three narrow pieces:

- immutable syntax and inflection tasks expressed in sentence-local Unicode
  offsets;
- a deterministic task-router protocol that identifies unresolved work;
- a specialist backend protocol that accepts the role-separated `PromptRequest`
  from #59 and returns raw JSON.

`HybridSuggestionEngine` segments the original paragraph, asks the injected
router for eligible tasks, builds #59 requests, validates responses, verifies
only changed proposals, and converts accepted edits to `Finding` suggestions in
original paragraph offsets. The default analyzer has no specialist backend or
router and therefore makes no specialist call.

## Data flow and policy

For each routed task, unchanged output stops after one model call. A changed
candidate or corrected-text proposal is deterministically validated and sent
unchanged to the accept/reject verifier, making at most two calls. Candidate
selection can only use a supplied stable ID. Syntax proposals derive local
edits without model offsets. Protected spans apply before translation to the
paragraph. The engine reports call count and the exact operation versions.

Accepted model findings have `Severity.SUGGESTION`, a model source, a
policy-calibrated confidence supplied by the engine rather than the model, and
remain reviewable. `Analyzer.correct()` selects automatic edits solely from the
versioned deterministic source policy. A qualified deterministic finding wins
any conflict; the conflicting model alternative remains in `skipped_findings`.

The existing general finding backend remains compatible and suggestion-only.
Correction analysis calls it once per sentence. Optional backend or specialist
failure is converted to a versioned `SuggestionOutcome`; deterministic
findings and corrections remain available. No successful outcome conceals an
unavailable, timed-out, or invalid optional suggestion path.

## Sync, async, privacy, and failures

`correct()` is a synchronous wrapper over the same internal coroutine used by
`correct_async()`, so ordering, calls, outcomes, and correction policy are
identical. Controlled failures expose only a stable backend name and operation
metadata. Source text, prompts, candidates, and raw responses are never placed
in errors or outcomes.

## Verification

Fast tests use authored fake routers and backends for rules-only, unchanged,
candidate selection, syntax proposal, verifier rejection, backend failures,
deterministic/model conflicts, paragraph offsets, protected tokens, call
budgets, sync/async parity, and end-to-end correction. Full pytest, Ruff,
formatting, mypy, public stubs, and documentation checks are required.
