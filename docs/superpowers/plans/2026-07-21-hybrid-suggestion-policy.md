# Hybrid Suggestion Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete #60 with safe rules-first specialist suggestions for sentences and paragraphs.

**Architecture:** Add an injected hybrid suggestion engine in `analysis`, then make `Analyzer.correct` and `correct_async` share one coroutine that merges its reviewable findings with source-policy deterministic corrections. Keep all real model/runtime selection out of scope.

**Tech Stack:** Python 3.12+, asyncio, existing Polis models/segmentation/#59 contracts, pytest, Ruff, mypy.

## Global Constraints

- All text processing is offline and model input is data, never instructions.
- Automatic correction is granted only by the explicit deterministic source policy.
- Model findings are always suggestions, including verifier-accepted findings.
- Original offsets are half-open Python Unicode code-point ranges.
- No model or runtime name is hard-coded in core or public result models.
- One focused #60 completion commit; Paweł Cyroń is the sole credited author.

---

### Task 1: Specialist task and engine contracts

**Files:**
- Create: `src/polis/analysis/hybrid.py`
- Test: `tests/test_hybrid_suggestion_engine.py`

**Interfaces:**
- Produces: `InflectionTask`, `SyntaxTask`, `SpecialistTaskRouter`, `SpecialistBackend`, `HybridSuggestionEngine`, and `HybridSuggestionRun`.

- [ ] Add failing tests for empty routing, unchanged candidate, changed candidate with verification, changed syntax, and verifier rejection.
- [ ] Implement strict task validation, request construction, response validation, and suggestion findings.
- [ ] Verify one-call unchanged and two-call changed budgets.

### Task 2: Paragraph safety and optional failure outcomes

**Files:**
- Modify: `src/polis/analysis/hybrid.py`
- Test: `tests/test_hybrid_suggestion_engine.py`

**Interfaces:**
- Consumes: sentence-local tasks and original deterministic findings.
- Produces: paragraph-offset suggestions plus safe run status and call count.

- [ ] Add failing tests for Unicode paragraph offsets, protected names/numbers/URLs/quotations, invalid response, timeout, and unavailable backend.
- [ ] Translate accepted edits exactly once from sentence to paragraph coordinates.
- [ ] Preserve completed suggestions and return explicit failure status without source text.

### Task 3: Shared synchronous and asynchronous correction orchestration

**Files:**
- Modify: `src/polis/analyzer.py`
- Modify: `src/polis/__init__.py`
- Modify: `tests/typecheck/stubs/polis/__init__.pyi`
- Test: `tests/test_suggestion_outcomes.py`
- Test: `tests/test_conservative_correction.py`

**Interfaces:**
- Produces: `Analyzer.correct_async(text)` and enriched `SuggestionOutcome.model_calls`.

- [ ] Add failing tests for one backend pass, deterministic fallback, model-only skipped findings, deterministic conflict priority, and sync/async parity.
- [ ] Replace the repeated-backend correction path with one shared coroutine.
- [ ] Merge specialist suggestions only into the review/skipped path and retain explicit outcomes.

### Task 4: Documentation and complete verification

**Files:**
- Modify: `docs/public-api.md`
- Modify: `docs/limitations.md`
- Modify: `docs/privacy.md`
- Modify: `docs/architecture/protocols.md`

- [ ] Document injection, call budgets, failure outcomes, suggestion-only behavior, offsets, and current no-real-model limitation.
- [ ] Run focused tests, full pytest, Ruff check, Ruff format check, mypy, and public API/type checks.
- [ ] Audit all #60 criteria, commit, push, and close #60.
