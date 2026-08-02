# Issue #127 Evaluation Conflict Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make evaluation fixture validation reject an insertion at either
closed boundary of a selected non-empty replacement, matching ADR-0003.

**Architecture:** Keep production correction conflict detection unchanged. Make
the evaluation validator's insertion/replacement interval inclusive at both
endpoints, then express that same rule in an independently derived regression
and its dataset documentation.

**Tech Stack:** Python 3.12+, pytest, Ruff, mypy, Markdown.

## Global Constraints

- ADR-0003's correction-selection contract governs evaluator behavior.
- Do not modify `polis.correction` or any public correction API.
- Do not run evaluation, holdout, corpus scoring, or model commands.
- Do not modify corpus, holdout, sentence-safety, quality-threshold, or model-
  qualification assets; prove tracked hashes are unchanged.
- Use only `uv run --locked --extra dev` for required Python checks.
- Keep the result to one focused commit referencing `#127`, with no attribution
  trailer.

---

## File structure

- `src/polis/evaluation/dataset.py` owns schema-v1 fixture conflict validation.
- `tests/test_evaluation_dataset.py` owns observable invalid and valid fixture
  boundary behavior.
- `docs/evaluation-dataset.md` describes the evaluator's authored-data
  contract.
- `docs/superpowers/specs/2026-08-02-issue-127-evaluation-conflicts-design.md`
  records the accepted design and protected-asset inventory.

### Task 1: Align evaluation insertion conflicts

**Files:**
- Modify: `tests/test_evaluation_dataset.py:153-213`
- Modify: `src/polis/evaluation/dataset.py:168-185`
- Modify: `docs/evaluation-dataset.md:62-68`
- Create: `docs/superpowers/specs/2026-08-02-issue-127-evaluation-conflicts-design.md`
- Create: `docs/superpowers/plans/2026-08-02-issue-127-evaluation-conflicts.md`

**Interfaces:**
- Consumes: `validate_dataset(raw: object, *, source: str = "memory") -> EvaluationDataset`.
- Produces: `ValueError` containing `colliding expected findings` for an
  insertion whose offset equals a non-empty replacement's `end`.

- [x] **Step 1: Write the failing regression**

Replace the permissive parameterized test with a replacement-end test that
uses the existing fixture's `[0, 2)` correction and appends a literal insertion
at offset `2`:

```python
def test_validator_rejects_insertion_at_replacement_end() -> None:
    raw = _raw_dataset()
    raw["cases"][0]["expected_findings"].append(
        {
            "category": "punctuation",
            "start": 2,
            "end": 2,
            "original": "",
            "suggestion": ",",
            "rationale": "Adversarial insertion at a replacement end.",
        }
    )

    with pytest.raises(ValueError, match="colliding expected findings"):
        validate_dataset(raw)
```

The production mutation this catches is changing the evaluator condition back
to `< replacement_end`, which would silently allow an invalid fixture oracle.

- [x] **Step 2: Run the regression to verify RED**

Run:

```bash
uv run --locked --extra dev pytest tests/test_evaluation_dataset.py::test_validator_rejects_insertion_at_replacement_end -v
```

Expected: failure because the current half-open evaluator predicate allows the
insertion at offset `2`.

- [x] **Step 3: Write the minimal implementation and contract documentation**

Change the evaluator condition to:

```python
if any(start <= insertion <= end for start, end in replacements):
    raise ValueError(f"case {case_id} has colliding expected findings")
```

Retain the duplicate-insertion and overlapping-replacement checks. Update the
documentation to reject insertion offsets at replacement start, inside, and
end, allowing only offsets strictly outside a non-empty replacement range.
Replace the old parameterized permissive test with one strict-outside success
case at offset `3`.

- [x] **Step 4: Run focused GREEN verification**

Run:

```bash
uv run --locked --extra dev pytest tests/test_evaluation_dataset.py tests/test_conflict_detection.py tests/test_analysis_apply.py -v
```

Expected: all selected tests pass, including the new replacement-end
regression, strict-outside acceptance, production conflict detection, and
analysis application.

- [x] **Step 5: Run required repository verification**

Run:

```bash
uv run --locked --extra dev pytest -m "not research and not slow and not model"
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
git diff --check
```

Then compare the protected asset inventory with `git ls-files -s` and
`shasum -a 256`; both before/after records must be equal for every listed path.

- [x] **Step 6: Self-review and commit**

Inspect `git diff --check`, the complete diff, the acceptance criteria, and
the test mutation: replacing `<= end` with `< end` must make the new regression
fail. Commit only the five planned files plus the required agent report with:

```bash
git commit -m "fix: align evaluation insertion conflicts (#127)"
```

## Plan self-review

- Spec coverage: Task 1 maps every issue criterion to a test, the one-line
  predicate change, the documentation update, or the protected-asset check.
- Placeholder scan: no open decision, deferred implementation, or unspecified
  test behavior remains.
- Type consistency: the plan uses the existing `validate_dataset` signature
  and no new public type or interface.
