# Issue #129 Correction Properties Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic, privacy-safe generated properties that guard the
accepted correction conflict, application, and fail-closed selection contract.

**Architecture:** The test module derives descriptors from the #123 synthetic
Unicode cases, converts them to real public findings/results, and compares
production behavior with independent ADR-0003 oracle and reconstruction
helpers. Production code is unchanged.

**Tech Stack:** Python 3.12+, existing `tests.generative`, pytest, Ruff, mypy,
and Markdown.

## Global Constraints

- Use only the #123 `unicode-structural-v1` synthetic generator, seed `95001`,
  and its 64-case bounded default; do not add dependencies or read environment
  configuration.
- Preserve ADR-0003's closed insertion-boundary conflict rule, atomic
  `AnalysisResult.apply` validation, right-to-left application, and public
  contracts exactly.
- Keep every failure text privacy-safe: invariant identifier plus replay
  metadata only; never interpolate generated/analyzed text or corrected output.
- Do not alter production correction behavior, automatic-correction policy,
  corpora, holdouts, models, evaluation, or linguistic behavior. Stop and
  report a production defect for a separate regression-first issue.
- Use `apply_patch` for edits. Keep one focused commit referencing `#129` with
  no attribution trailer. Keep `.superpowers` reports untracked.

---

## File structure

- `tests/test_correction_properties.py` contains generated descriptors,
  independent oracle/reconstruction helpers, and all #129 properties.
- `docs/development/generative-invariants.md` records the correction guardrail
  and its structural-only boundary.
- `docs/superpowers/specs/2026-08-02-issue-129-correction-properties-design.md`
  records the approved design.
- `docs/superpowers/plans/2026-08-02-issue-129-correction-properties.md`
  records this execution plan.

### Task 1: Generated correction contract properties

**Files:**
- Create: `tests/test_correction_properties.py`
- Modify: `docs/development/generative-invariants.md`
- Create: `docs/superpowers/specs/2026-08-02-issue-129-correction-properties-design.md`
- Create: `docs/superpowers/plans/2026-08-02-issue-129-correction-properties.md`

**Interfaces:**
- Consumes: `generate_unicode_text_cases() -> tuple[SyntheticTextCase, ...]`,
  `assert_structural_invariant(condition, *, invariant, replay) -> None`,
  `findings_conflict(first, second) -> bool`,
  `sort_findings_for_application(findings) -> tuple[Finding, ...]`, and
  `AnalysisResult.apply(issue_ids) -> str`.
- Produces: test-only properties with no new public runtime API.

- [x] **Step 1: Write the generated test module**

Create real `Finding` values from each synthetic source span. Write separate
properties for the symmetric ADR oracle, replay-derived compatible
normalization/right-to-left reconstruction over every non-empty subset and
selected-ID permutation, and fail-closed conflict/stale/unknown/duplicate/
uncorrectable selections. Every observable property assertion must use:

```python
assert_structural_invariant(
    observed == expected,
    invariant="correction.apply.reconstruction",
    replay=case.replay,
)
```

The production mutations this catches are changing the insertion endpoint
predicate, sorting selected edits left-to-right, applying before validation,
or accepting invalid selections.

- [x] **Step 2: Run focused RED evidence**

Run the new property module after deliberately changing one production branch
in a temporary, uncommitted mutation. Confirm the matching property fails with
only invariant/replay metadata, restore the exact production source using
`apply_patch`, then verify the worktree contains no production diff. This is
required because the accepted production contract comes from merged
prerequisites and #129 adds tests only.

- [x] **Step 3: Run focused GREEN evidence**

Run:

```bash
uvx --from 'uv==0.11.2' uv run --locked --extra dev pytest tests/test_correction_properties.py -v
uvx --from 'uv==0.11.2' uv run --locked --extra dev pytest tests/test_conflict_detection.py tests/test_analysis_apply.py tests/test_automatic_correction_policy.py -v
```

All properties and the existing contract/policy regressions must pass.

- [x] **Step 4: Document the guardrail**

Append a correction-properties section that names the #123 source, ADR oracle,
compatible edit shapes, right-to-left reconstruction, selection permutations,
atomic failure cases, and replay/privacy contract. State that the coverage is
structural, bounded, synthetic, and not linguistic or evaluation evidence.

- [x] **Step 5: Run repository verification and self-review**

Run:

```bash
uvx --from 'uv==0.11.2' uv run --locked --extra dev pytest -m "not research and not slow and not model"
uvx --from 'uv==0.11.2' uv run --locked --extra dev ruff check .
uvx --from 'uv==0.11.2' uv run --locked --extra dev ruff format --check .
uvx --from 'uv==0.11.2' uv run --locked --extra dev mypy .
git diff --check
```

Inspect the complete diff for production/policy/data changes, re-read #129 and
ADR-0003, and verify generated failure paths include neither `case.text` nor
derived output. Commit only the four listed files with:

```bash
git commit -m "test: add correction properties (#129)"
```

## Plan self-review

- Spec coverage: Task 1 maps each #129 acceptance criterion to a property or
  documentation update, while focused and repository checks cover the required
  test matrix.
- Placeholder scan: the plan specifies exact files, interfaces, invariant
  names, commands, and stop condition without deferred behavior.
- Type consistency: all interfaces are existing public/test-support interfaces;
  the plan introduces no runtime type or API.
