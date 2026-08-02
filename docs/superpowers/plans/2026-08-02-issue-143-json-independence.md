# Independent Canonical JSON Property Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Demonstrate canonical JSON determinism across two independently constructed equivalent generated results.

**Architecture:** Strengthen the existing test-only generated fidelity property in place. Construct two results through separate `_generated_findings` calls, compare their identities, structures, encodings, and round trips, and preserve replay-safe failures.

**Tech Stack:** Python 3.12+, pytest, repository-owned deterministic Unicode generator.

## Global Constraints

- Test-only change; do not modify production serializers or public contracts.
- Preserve synthetic deterministic data, bounded budgets, safe replay metadata, and offline privacy.
- Do not add dependencies, corpora, model evaluation, or unrelated refactoring.

---

### Task 1: Strengthen independent canonical JSON evidence

**Files:**
- Modify: `tests/test_generated_finding_fidelity.py`
- Create: `docs/superpowers/specs/2026-08-02-issue-143-json-independence-design.md`
- Create: `docs/superpowers/plans/2026-08-02-issue-143-json-independence.md`

**Interfaces:**
- Consumes: `_generated_findings(text: str) -> tuple[Finding, ...]`, `AnalysisResult.to_json()`, and `AnalysisResult.from_json()`.
- Produces: strengthened `test_generated_results_have_deterministic_lossless_canonical_json()` coverage only.

- [ ] **Step 1: Add the independent-result assertions with a deliberately divergent second construction**

Construct `independent_result` separately, initially with an empty issues tuple, and assert structural equality plus byte-identical JSON using `assert_structural_invariant`.

- [ ] **Step 2: Run the focused property and verify RED**

Run: `uv run --locked --extra dev pytest tests/test_generated_finding_fidelity.py::test_generated_results_have_deterministic_lossless_canonical_json -q`

Expected: fail with safe `result.independent_construction` replay metadata because the second construction diverges.

- [ ] **Step 3: Make the second construction independently equivalent**

Replace the empty issues tuple with a fresh `_generated_findings(case.text)` call. Retain assertions that result and finding objects are distinct, both values are equal, encodings are byte-identical, and both round-trip losslessly.

- [ ] **Step 4: Run focused and complete verification**

Run the focused generated fidelity suite, complete fast pytest suite, `ruff check .`, `ruff format --check .`, and `mypy .`.

- [ ] **Step 5: Commit**

Commit all scoped files once with `test: strengthen canonical JSON independence (#143)` and no attribution trailers.
