# Generated Public Finding and Result Fidelity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bounded deterministic generated tests that prove public finding
and result offset fidelity, canonical normalization, and JSON round trips.

**Architecture:** A single test module consumes #123's hash-indexed Unicode
harness and existing public APIs. It builds a small hand-ordered set of valid
findings per case, uses replay-safe structural assertions, and exercises
invalid results at the `AnalysisResult` constructor boundary. No production API
or dependency changes are needed.

**Tech Stack:** Python 3.12+, pytest, existing `tests.generative`, public Polis
models/JSON helpers, Ruff, and mypy.

## Global Constraints

- Implement only GitHub issue #124; #95 remains open, and #119 is out of scope.
- Preserve public contracts, offline privacy, Unicode code-point half-open
  offsets `[start, end)`, deterministic bounded replay, existing linguistic
  behavior, and the #123 harness.
- Use #123's `unicode-structural-v1` generator with its fixed seed `95001` and
  default budget `64`; do not read ambient seed or budget configuration.
- Generated failure diagnostics may expose only safe invariant identifiers,
  structural identifiers, and replay metadata; they must never expose analyzed
  text.
- Do not alter `src/`, sentence-safety corpora, holdouts, model qualification,
  dependencies, Fast-CI configuration, or unrelated files. If a property finds
  a production defect, stop and create no fix in this issue.
- One issue equals one focused commit, with no co-author, automation
  attribution, or tool signature.

---

### Task 1: Add generated public finding and result fidelity properties

**Files:**
- Create: `tests/test_generated_finding_fidelity.py`
- Create: `docs/superpowers/specs/2026-08-02-issue-124-finding-result-fidelity-design.md`
- Create: `docs/superpowers/plans/2026-08-02-issue-124-finding-result-fidelity.md`
- Create: `.superpowers/sdd/issue-124-agent-report.md` (git-ignored handoff)
- Verify: `tests/generative.py`, `src/polis/core/models.py`,
  `src/polis/core/serialization.py`, and `src/polis/analysis/__init__.py`

**Interfaces:**
- Consumes: `generate_unicode_text_cases()`, `assert_structural_invariant()`,
  `AnalysisResult`, `Finding.create`, `normalize_findings`, and the public JSON
  methods.
- Produces: deterministic property evidence only; it creates no public runtime
  interface.

- [ ] **Step 1: Write the failing generated-safeguard test**

Create `tests/test_generated_finding_fidelity.py` first. Import the #123
harness and public models. Define a missing local fixture builder named
`_generated_findings(text: str) -> tuple[Finding, ...]` only through its use in
the properties; do not add it yet. For each generated case, construct an
`AnalysisResult` with `_generated_findings(case.text)` and call
`assert_structural_invariant` for bounds and exact original slices. Add the
normalization, canonical JSON round-trip, and negative invalid-slice/out-of-
bounds properties below. Every failure must call the shared assertion helper
with `case.replay`; never use an assertion that formats `case.text`.

Use these hand-derived expectations:

```python
# `_generated_findings` returns this exact canonical sequence.
# All entries use a fixed valid category/source/severity/message/explanation.
insertion = Finding.create(original="", suggestion=".", start=0, end=0, ...)
replacement = Finding.create(
    original=text[0], suggestion=_replacement_for(text[0]), start=0, end=1, ...
)
deletion = Finding.create(
    original=text[-1], suggestion="", start=len(text) - 1, end=len(text), ...
)
```

For empty text, expect only the insertion. For one code point, expect the
insertion then replacement. For longer text, expect insertion, replacement,
then deletion. Generate three deterministic permutations of that tuple—original,
reversed, and a one-step rotation—and require `normalize_findings` to return
the original tuple under `AnalysisOptions()`. For invalid cases, construct a
same-length incorrect first-code-point original and an empty insertion at
`len(text) + 1`; require `AnalysisResult` to reject both and ensure its message
does not contain the generated text.

Name the break before writing the body: removal of the new generated
fidelity property or a public-boundary regression that accepts a mismatched or
out-of-bounds finding must make the test fail. Expected canonical order is the
literal fixture construction order, not a duplicate of the production sort
key.

- [ ] **Step 2: Run the focused test and record RED**

Run:

```bash
uv run --locked --extra dev pytest tests/test_generated_finding_fidelity.py -v
```

Expected: collection fails with an import/name error for the intentionally
missing `_generated_findings` safeguard fixture. Record the exact command,
exit status, and output in `.superpowers/sdd/issue-124-agent-report.md` before
writing the fixture. If instead a public invariant fails, stop; do not modify
production code in this issue.

- [ ] **Step 3: Implement the smallest test-local fixture support**

Implement `_generated_findings` and `_replacement_for` in the new test module.
Keep them test-local and direct: `_replacement_for` returns `"x"` unless the
original code point is `"x"`, then `"y"`; it must differ from its input.
`_generated_findings` returns the exact canonical sequence described in Step 1,
with `Finding.create` and literal valid presentation fields. Do not change
`tests/generative.py`, `src/`, or a public contract.

Implement a local helper that runs a callable, confirms it raises `TypeError`
or `ValueError`, and confirms `case.text` is absent from its message. Its
caller then submits the resulting boolean to `assert_structural_invariant`;
this keeps failure output replay-safe. Build a new valid result independently
for the JSON test, encode it twice, decode it, and assert encoded JSON remains
exactly equal after the round trip. Rebuild findings twice and compare their ID
tuples for stable identity.

- [ ] **Step 4: Run the focused properties and record GREEN**

Run:

```bash
uv run --locked --extra dev pytest tests/test_generated_finding_fidelity.py -v
```

Expected: every generated property passes. If any production invariant fails,
record its replay metadata and stop without a production change.

- [ ] **Step 5: Self-review scope and test quality**

Check that the test names the boundary regression it catches, exercises real
public code rather than mocks, uses literal/hand-derived canonical order, and
does not format generated text into a failure. Confirm the diff changes only
the new test and the required design/plan documents, plus the git-ignored
report. Run:

```bash
git diff --check
git diff --stat
rg -n "TBD|TODO|PRIVATE_SENTINEL|issue-119|sentence_safety|holdout" \
  tests/test_generated_finding_fidelity.py \
  docs/superpowers/specs/2026-08-02-issue-124-finding-result-fidelity-design.md \
  docs/superpowers/plans/2026-08-02-issue-124-finding-result-fidelity.md
```

- [ ] **Step 6: Run all verification and create the focused commit**

Run each command fresh and record its exit status and concise result:

```bash
uv run --locked --extra dev pytest tests/test_generated_finding_fidelity.py -v
uv run --locked --extra dev pytest tests/test_public_models.py tests/test_analysis_normalization.py -v
uv run --locked --extra dev pytest -m "not research and not slow and not model"
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
git diff --check
```

Then stage only the new test and both documents, verify the staged diff, and
create the single commit:

```bash
git add \
  tests/test_generated_finding_fidelity.py \
  docs/superpowers/specs/2026-08-02-issue-124-finding-result-fidelity-design.md \
  docs/superpowers/plans/2026-08-02-issue-124-finding-result-fidelity.md
git diff --cached --check
git diff --cached --stat
git commit -m "test: add generated finding fidelity properties (#124)"
```

- [ ] **Step 7: Write the handoff report and self-review the committed diff**

Write `.superpowers/sdd/issue-124-agent-report.md` with the design and plan
paths, exact RED/GREEN commands and outputs, changed files, complete command
results, acceptance-criterion evidence, self-review results, and any risks.
Review `git show --check --stat HEAD` and the committed diff. The report is
git-ignored and must not be staged.
