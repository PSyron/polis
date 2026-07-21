# Specialist Prompt Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete issue #59 with strict, model-independent specialist request and response contracts.

**Architecture:** Harden the existing `polis.llm.corrected_text` boundary. Keep role-separated messages and canonical delimited JSON requests, validate all responses and locally derived edits before orchestration can consume them, and preserve the legacy finding contract unchanged.

**Tech Stack:** Python 3.12+, standard-library JSON/dataclasses/difflib, pytest, Ruff, mypy.

## Global Constraints

- Text remains offline and is treated only as delimited data.
- No model, model server, transport, or chat-template name enters core types.
- Model-derived changes remain unqualified suggestions under ADR-0009.
- One issue produces one focused commit; Paweł Cyroń is the sole credited author.
- No new production dependency is added.

---

### Task 1: Make request envelopes and schemas executable

**Files:**
- Modify: `src/polis/llm/corrected_text.py`
- Test: `tests/test_corrected_text_contract.py`

**Interfaces:**
- Consumes: existing `PromptRequest` builders.
- Produces: canonical delimited JSON user messages and valid closed schemas.

- [ ] Add tests that parse the delimited payload and assert embedded marker text is escaped.
- [ ] Run focused tests and confirm the new assertions fail.
- [ ] Replace the empty delimiter suffix with one canonical JSON envelope per operation.
- [ ] Remove the invalid top-level candidate-schema property closure and define two fully closed branches.
- [ ] Run focused tests and confirm they pass.

### Task 2: Validate candidate sets and protected edits

**Files:**
- Modify: `src/polis/llm/corrected_text.py`
- Test: `tests/test_corrected_text_contract.py`

**Interfaces:**
- Consumes: `FiniteCandidate`, `derive_text_edits`.
- Produces: one-span candidate sets and optional explicit protected spans.

- [ ] Add failing tests for mixed spans, duplicate forms/features, missing unchanged form, invalid lemmas, and protected-span edits.
- [ ] Implement strict candidate-record validation and protected-span validation.
- [ ] Run focused tests and confirm they pass.

### Task 3: Make failures bounded and privacy-safe

**Files:**
- Modify: `src/polis/llm/corrected_text.py`
- Test: `tests/test_corrected_text_contract.py`

**Interfaces:**
- Consumes: raw local-model response strings.
- Produces: validated values or generic `ValueError`/`TypeError` messages safe for adapter wrapping.

- [ ] Add failing tests for oversized raw responses, malformed JSON containing private text, non-finite shapes, and verifier replacement fields.
- [ ] Check raw length before decoding and translate JSON decoder failures without exception chaining.
- [ ] Run focused tests and confirm they pass.

### Task 4: Document and verify the completed contract

**Files:**
- Modify: `docs/llm-corrected-text-contract.md`
- Modify: `docs/architecture/protocols.md`
- Modify: `src/polis/llm/__init__.py`

**Interfaces:**
- Consumes: completed specialist API.
- Produces: extension guidance and explicit unqualified status.

- [ ] Export the specialist contract types and functions from `polis.llm` without changing `polis.core`.
- [ ] Document exact envelopes, limits, error behavior, runtime templating responsibility, and ADR-0009 status.
- [ ] Run focused tests, full pytest, Ruff check, Ruff format check, and mypy.
- [ ] Audit the staged diff against every #59 criterion, then commit, push, and close the issue.
