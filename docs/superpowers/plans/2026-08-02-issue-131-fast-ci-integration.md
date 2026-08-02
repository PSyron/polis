# Fast CI Generated-Invariant Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pin the accepted generated-invariant version, seed, and bounded case
budget in the existing Fast CI pytest command and document safe structural
evidence/replay limits for issue #131.

**Architecture:** The test-only no-argument generator resolves a complete,
validated three-field environment contract, so every existing generated suite
consumes the Fast CI configuration. The workflow validator separately pins the
one pytest command to the accepted values and rejects malformed placement; the
development guide records replay-safe, bounded structural evidence without
changing Polis runtime behavior.

**Tech Stack:** GitHub Actions YAML, Python standard library, pytest, existing
workflow validator, existing deterministic generator documentation, Ruff, and
mypy.

## Global Constraints

- Implement only GitHub issue #131; leave #95 open and keep #119, sentence
  safety corpora, model qualification, holdouts, research evaluation, runtime
  behavior, public contracts, and dependencies out of scope.
- Preserve offline privacy: generated and analyzed text must not be printed in
  CI configuration, validator errors, replay guidance, or failure evidence.
- Keep exactly one Fast CI `pytest`/`unittest` command with the unchanged
  `not research and not slow and not model` marker filter and the existing
  supported matrix and 10-minute timeout.
- With no generator environment fields, retain `unicode-structural-v1`, seed
  `95001`, and 64 cases. With any field, require exactly one of each accepted
  field; accept a uint64 seed and a 1--256 case budget; CI pins the exact
  version, seed, and 64-case budget and rejects absent, duplicate, invalid, or
  excessive configuration.
- Generated properties are synthetic, bounded structural evidence only;
  authored regressions and corpus gates remain authoritative for Polish
  linguistic quality.
- Create one focused commit referencing `#131`, authored only as Paweł Cyroń;
  do not push, open a pull request, close an issue, add attribution trailers,
  or track the agent report.

---

### Task 1: Enforce and document the Fast CI generated-invariant contract

**Files:**
- Modify: `.github/workflows/fast-ci.yml`
- Modify: `scripts/validate_fast_ci_workflow.py`
- Modify: `tests/test_fast_ci_workflow.py`
- Modify: `tests/generative.py`
- Modify: `tests/test_generative_harness.py`
- Modify: `docs/development/generative-invariants.md`
- Create: `docs/superpowers/specs/2026-08-02-issue-131-fast-ci-integration-design.md`
- Create: `docs/superpowers/plans/2026-08-02-issue-131-fast-ci-integration.md`
- Verify: all completed generated-property modules and existing Fast CI policy
  tests.

**Interfaces:**
- Consumes: `FAST_PYTEST_COMMAND`, `validate_contract(path)`, the #123
  generator constants, and the existing Fast CI YAML policy.
- Produces: one policy-validated Fast CI pytest step with explicit
  `POLIS_GENERATIVE_GENERATOR_VERSION`, `POLIS_GENERATIVE_SEED`, and
  `POLIS_GENERATIVE_CASES` assignments that the no-argument generated suites
  consume, plus replay-safe documentation.

- [ ] **Step 1: Write failing workflow-policy regressions**

Add the expected exact pytest command and step-level environment tests to
`tests/test_fast_ci_workflow.py`. Assert that the checked-in pytest step has
the accepted version, seed, and budget. For temporary copies of the workflow,
remove each assignment, duplicate an assignment, replace the version with
`unicode-structural-v2`, use the non-integer seed `not-a-seed`, use the
non-integer case budget `many`, and replace the 64-case budget with `257`.
Each mutated copy must make `run_validator()` return nonzero and contain a
field-specific contract error. Keep the current test that proves there is one
filtered pytest command, updated only to the new complete command string.

Add generator-harness tests with `monkeypatch`: no configuration preserves the
default 64-case sequence; the complete three-field configuration uses an
alternate valid uint64 seed and bounded budget; a partial configuration raises
`ValueError`; and an invalid version, non-uint64 seed, zero/non-numeric budget,
or budget `257` raises `ValueError`. The complete configuration test must
assert its replay seed and exact budget, proving the no-argument property path
actually consumes the settings.

- [ ] **Step 2: Run the focused policy test and verify RED**

Run:

```bash
uv run --locked --extra dev pytest tests/test_fast_ci_workflow.py -v
```

Expected: the workflow regressions fail because the command has no
generated-invariant assignments, and the harness configuration regressions
fail because the no-argument generator ignores the test-only environment.
Record the commands, nonzero status, and missing-configuration failure before
changing the harness, workflow, or validator.

- [ ] **Step 3: Make the minimal policy and workflow changes**

Put exactly this environment mapping on the existing `Run pytest suite` step in
`.github/workflows/fast-ci.yml`:

```yaml
env:
  POLIS_GENERATIVE_GENERATOR_VERSION: unicode-structural-v1
  POLIS_GENERATIVE_SEED: 95001
  POLIS_GENERATIVE_CASES: 64
```

Keep the `uv run --locked --extra dev pytest -m "not research and not slow and
not model"` command byte-exact. In `tests/generative.py`, make the
no-argument call resolve `POLIS_GENERATIVE_GENERATOR_VERSION`,
`POLIS_GENERATIVE_SEED`, and `POLIS_GENERATIVE_CASES`: no fields means current
defaults, any field means all are required, version must be exact, seed must be
in `[0, 2**64 - 1]`, and budget must be in `[1, 256]`. Explicit seed/count
arguments retain the direct fixture contract. In
`scripts/validate_fast_ci_workflow.py`, define the accepted generator version,
seed, 64-case budget, maximum 256 cases, and expected complete command as
policy constants. Require that exact command on the existing pytest step, then
retain the existing single-command regex check. Add compact validation that
reports missing, duplicate, or invalid version/seed/budget fields without
echoing any workflow text.

- [ ] **Step 4: Run the focused policy test and verify GREEN**

Run:

```bash
uv run --locked --extra dev pytest tests/test_fast_ci_workflow.py -v
```

Expected: every workflow contract test, including the new missing, invalid, and
excessive cases, passes.

- [ ] **Step 5: Document replay and evidence boundaries**

Extend `docs/development/generative-invariants.md` with the Fast CI command's
pinned generator version, seed, and 64-case budget; the supported Unicode
families; the five completed invariant modules; a replay command that uses
only version/seed/case metadata and never prints text; the existing 10-minute
Fast CI bound; and residual risks. State explicitly that structural evidence
does not replace authored regressions or corpus gates and establishes no broad
Polish linguistic-quality result.

- [ ] **Step 6: Run focused generated evidence and full verification**

Run fresh:

```bash
uv run --locked --extra dev pytest tests/test_fast_ci_workflow.py -v
uv run --locked --extra dev pytest \
  tests/test_segmentation_properties.py \
  tests/test_generated_finding_fidelity.py \
  tests/test_correction_properties.py \
  tests/test_rule_registry_properties.py \
  tests/test_generated_pipeline_parity.py -v
uv run --locked --extra dev pytest -m "not research and not slow and not model"
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
git diff --check
```

The complete supported GitHub Actions matrix is verified only after the branch
is pushed to its separate reviewed pull request; do not claim that external
matrix evidence locally.

- [ ] **Step 7: Self-review and commit the focused issue change**

Confirm the diff changes only the listed test-support, workflow-policy,
evidence-document, and required design/plan files; it has one pytest command,
intact exclusions, no analyzed text, no runtime/dependency/corpus/holdout/model
changes, and no placeholder text. Stage only these eight files, inspect the staged diff and
whitespace, and commit:

```bash
git commit -m "ci: integrate bounded generated invariants (#131)"
```

Keep the report outside the repository or in ignored scratch space. Inspect
the committed diff before handoff and report the missing external CI-matrix
evidence as the next permitted action.

## Plan self-review

- The failing policy and harness tests precede every configuration, workflow,
  or validator change and each required malformed configuration has a concrete
  mutation.
- The plan preserves exactly one filtered pytest invocation and all stated
  exclusions while requiring the accepted version, seed, and bounded budget.
- The documentation task covers replay safety, budget, Unicode families,
  completed invariants, structural-versus-linguistic evidence, and residual
  risks without making a runtime or corpus claim.
