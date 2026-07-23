# PR #118 Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the consumed #115 holdout as immutable negative evidence while removing its rejected runtime experiment, restoring green CI, and making the artifact and one-shot contracts auditable.

**Architecture:** Treat the wheel, sdist, frozen gate, marker, and final report as evidence produced by the pre-verdict evaluation snapshot. Active runtime and reusable evaluator maintenance may move forward after that snapshot, but the holdout is never loaded or executed again. The rejected nominal-agreement extension is removed from `src`, while provenance and documentation explain the separation.

**Tech Stack:** Python 3.12+, pytest, Ruff, mypy, Git/GitHub Actions.

## Global Constraints

- Never load, inspect, rerun, or tune against the consumed holdout.
- Preserve `experiments/sentence_safety_gate/frozen_gate.json`, `holdout.started`, and `report.json` byte-for-byte.
- Keep analyzed text offline and preserve scorer-only gold access.
- Prefer no suggestion to an unjustified suggestion.
- Do not add production dependencies.
- Keep GitHub metadata, code, identifiers, and technical documentation in English.

---

### Task 1: Establish the immutable evaluation boundary

**Files:**
- Create: `experiments/sentence_safety_gate/evaluated_source.json`
- Modify: `experiments/sentence_safety_gate/README.md`
- Modify: `docs/superpowers/specs/2026-07-23-installed-sentence-safety-gate-design.md`
- Test: `tests/test_sentence_safety_gate.py`

**Interfaces:**
- Consumes: the evaluated source commit and the wheel/sdist hashes already retained by `frozen_gate.json`.
- Produces: a closed provenance record that distinguishes evaluated inputs from post-verdict maintenance.

- [x] **Step 1: Verify the evaluated source identity**

Run:

```bash
git cat-file -t 24cda9a
git show -s --format='%H%n%T' 24cda9a
```

Expected: a commit object and its full commit/tree identities.

- [x] **Step 2: Write the failing provenance test**

Add a test that loads `evaluated_source.json`, requires a closed schema, and checks that its wheel and sdist hashes match `frozen_gate.json`.

- [x] **Step 3: Run the test and verify RED**

Run:

```bash
uv run pytest tests/test_sentence_safety_gate.py::test_evaluated_source_provenance_matches_frozen_artifacts -q
```

Expected: FAIL because `evaluated_source.json` does not exist.

- [x] **Step 4: Add the minimal provenance record**

Create a JSON object containing schema version, evaluated commit/tree identities, frozen wheel/sdist hashes, and an explicit `post_verdict_changes_are_not_evaluated` flag.

- [x] **Step 5: Run the test and verify GREEN**

Run the test from Step 3 and expect PASS.

### Task 2: Remove the rejected nominal-agreement runtime extension

**Files:**
- Modify: `src/polis/rules/contextual_inflection.py`
- Modify: `tests/test_contextual_inflection_rule.py`
- Modify: `docs/limitations.md`

**Interfaces:**
- Consumes: the existing contextual-inflection behavior from `origin/main`.
- Produces: no `feminine_accusative_agreement` evidence or suggestion in active runtime.

- [x] **Step 1: Convert the positive extension tests into an abstention regression**

For the two development examples, assert that active runtime emits no contextual-inflection finding and does not alter text.

- [x] **Step 2: Run the regression and verify RED**

Run:

```bash
uv run pytest tests/test_contextual_inflection_rule.py -k feminine_accusative -q
```

Expected: FAIL because the extension still emits a reviewable suggestion.

- [x] **Step 3: Remove only the extension**

Remove the evidence kind, surface trigger, rank dispatch, ranker, and minimal-edit helper added for `feminine_accusative_agreement`. Preserve all pre-existing contextual-inflection behavior.

- [x] **Step 4: Run the regression and verify GREEN**

Run the command from Step 2 and expect PASS.

### Task 3: Make future holdout reservations durable

**Files:**
- Modify: `experiments/sentence_safety_gate/gate.py`
- Modify: `tests/test_sentence_safety_gate.py`

**Interfaces:**
- Consumes: `reserve_holdout_once(...)`.
- Produces: a marker flushed and fsynced before holdout materialization; on POSIX, the parent directory is fsynced too.

- [x] **Step 1: Write the failing fsync regression**

Monkeypatch `os.fsync`, reserve a temporary marker, and assert one file fsync plus one parent-directory fsync on POSIX.

- [x] **Step 2: Run the test and verify RED**

Run:

```bash
uv run pytest tests/test_sentence_safety_gate.py::test_holdout_reservation_is_durable_before_returning -q
```

Expected: FAIL because no fsync call is made.

- [x] **Step 3: Implement durable reservation**

Flush and fsync the marker inside the exclusive-create context. After closing it, open and fsync the parent directory on POSIX. Do not weaken exclusive creation or existing-marker failure.

- [x] **Step 4: Run reservation tests and verify GREEN**

Run:

```bash
uv run pytest tests/test_sentence_safety_gate.py -k 'reservation' -q
```

Expected: all selected tests PASS.

### Task 4: Scope the native runner integration test correctly

**Files:**
- Modify: `tests/test_sentence_safety_runner.py`

**Interfaces:**
- Consumes: the explicit `macos-arm64-v1` release profile.
- Produces: the POSIX shebang/resource integration runs only on macOS arm64; platform-neutral protocol tests remain in the fast matrix.

- [x] **Step 1: Record the existing RED evidence**

Use the retained GitHub Actions logs showing both Windows 3.12 and 3.14 fail in `test_runner_reuses_one_analyzer_for_multiple_sentence_requests`.

- [x] **Step 2: Add the release-profile guard**

Define the same `MACOS_ARM64_RELEASE_PROFILE` predicate used by `tests/test_sentence_safety_installation.py` and apply it only to the native runner reuse test.

- [x] **Step 3: Verify collection and local execution**

Run:

```bash
uv run pytest tests/test_sentence_safety_runner.py -q
```

Expected on macOS arm64: all tests PASS. Windows CI should skip only the native reuse test.

### Task 5: Correct evidence documentation

**Files:**
- Modify: `docs/performance-baseline.md`
- Modify: `docs/quality-baseline.md`
- Modify: `docs/limitations.md`
- Modify: `experiments/sentence_safety_gate/README.md`
- Modify: `docs/superpowers/specs/2026-07-23-installed-sentence-safety-gate-design.md`

**Interfaces:**
- Consumes: exact values from `report.json` and identities from `evaluated_source.json`.
- Produces: documentation that does not call the rejected runtime extension qualified and does not claim final HEAD was the evaluated artifact source.

- [x] **Step 1: Replace stale development performance values**

Use the exact development performance object retained in `report.json`.

- [x] **Step 2: Document the negative-evidence boundary**

State that the evaluated snapshot produced the frozen artifacts and report; post-verdict fixes were not evaluated on the consumed holdout.

- [x] **Step 3: Remove production qualification language**

Document that the nominal-agreement extension was rejected and removed from active runtime after the holdout verdict.

### Task 6: Verify and publish the review fixes

**Files:**
- Verify all modified files.

**Interfaces:**
- Consumes: Tasks 1-5.
- Produces: a green, reviewable PR update without a holdout rerun.

- [x] **Step 1: Prove frozen evidence was not modified**

Compare the three evidence files against commit `17612bf`:

```bash
git diff --exit-code 17612bf -- experiments/sentence_safety_gate/frozen_gate.json experiments/sentence_safety_gate/holdout.started experiments/sentence_safety_gate/report.json
```

- [x] **Step 2: Run focused and full quality checks**

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy .
git diff --check
```

- [x] **Step 3: Review the final diff**

Confirm only #115 review fixes and evidence clarification are present.

- [ ] **Step 4: Commit and push**

Create a focused review-fix commit referencing #115 and push the existing branch without force.
