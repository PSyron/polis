# Empty Registry Fail-Closed Property Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove all generated registry fail-closed families reject invalid output for the empty default Unicode case.

**Architecture:** Strengthen the existing generated registry helper in place. Record a case only after all four invalid-output checks finish, then require case `0` through the replay-safe invariant helper.

**Tech Stack:** Python 3.12+, pytest, deterministic rule registry, repository-owned Unicode generator.

## Global Constraints

- Test-only change; do not modify registry or pipeline production behavior.
- Preserve deterministic bounded generation, safe replay metadata, half-open offsets, and offline privacy.
- Do not add dependencies, corpora, model evaluation, or unrelated refactoring.

---

### Task 1: Include and prove the empty fail-closed case

**Files:**
- Modify: `tests/test_rule_registry_properties.py`
- Create: `docs/superpowers/specs/2026-08-02-issue-144-registry-empty-design.md`
- Create: `docs/superpowers/plans/2026-08-02-issue-144-registry-empty.md`

**Interfaces:**
- Consumes: `generate_unicode_text_cases()`, `_capture_registry_error()`, `_assert_safe_registry_error()`, and `assert_structural_invariant()`.
- Produces: retained empty-case participation evidence inside `_assert_generated_fail_closed_properties()`.

- [ ] **Step 1: Add processed-case evidence while retaining the old non-empty slice**

Store processed replay indexes only after all four fail-closed checks for a case. Assert that index `0` is present using invariant `registry.fail_closed.empty_case` and replay metadata from the generated empty case.

- [ ] **Step 2: Run the focused property and verify RED**

Run: `uv run --locked --extra dev pytest tests/test_rule_registry_properties.py::test_generated_registry_invalid_output_fails_closed_without_text -q`

Expected: safe `AssertionError` for `registry.fail_closed.empty_case`, generator `unicode-structural-v1`, seed `95001`, case `0`.

- [ ] **Step 3: Include the complete generated sequence**

Remove the `[1:]` exclusion so case `0` completes the same four invalid-output checks as every other case.

- [ ] **Step 4: Run focused and complete verification**

Run the focused rule-registry property/protocol suites, complete fast pytest suite, `ruff check .`, `ruff format --check .`, and `mypy .`.

- [ ] **Step 5: Commit**

Commit all scoped files once with `test: cover empty registry fail-closed case (#144)` and no attribution trailers.
