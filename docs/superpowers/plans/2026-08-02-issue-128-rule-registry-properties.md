# Generated Rule Registry Properties Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bounded generated properties that prove the existing deterministic
rule registry preserves configured selection, execution, and finding order and
rejects invalid generated output.

**Architecture:** A test-only module consumes #123 replay cases and uses their
safe metadata to build finite fake rules and registration shapes. Independent
test-local expected sequences are compared with real
`DeterministicRuleRegistry` results; every property failure goes through the
shared privacy-safe invariant assertion.

**Tech Stack:** Python 3.12+, existing `polis.core` models and rules registry,
`tests.generative`, pytest, Ruff, and mypy.

## Global Constraints

- Implement only GitHub issue #128 and consume the already accepted #123
  deterministic bounded harness.
- Preserve all public APIs, offline privacy, deterministic registry behaviour,
  existing duplicate/incompatible validation, and authored registry/protocol
  regressions.
- Use only the harness default `unicode-structural-v1` generator, seed `95001`,
  and 64-case bounded budget; do not read ambient configuration or add a
  dependency.
- Generated failures must contain a stable invariant identifier and replay
  metadata, never generated or analyzed text.
- Do not modify production registry behaviour; stop for a separate
  regression-first bug issue if a property exposes a defect.
- Do not change #119, corpora, holdouts, model qualification, production
  dependencies, attribution, or unrelated files.
- Finish as one focused commit referencing `#128`; do not push, create a PR,
  merge, comment on, or close an issue.

---

### Task 1: Add generated registry ordering and fail-closed properties

**Files:**

- Create: `tests/test_rule_registry_properties.py`
- Create: `docs/superpowers/specs/2026-08-02-issue-128-rule-registry-properties-design.md`
- Create: `docs/superpowers/plans/2026-08-02-issue-128-rule-registry-properties.md`

**Interfaces:**

- Consumes: `DeterministicRuleRegistry`, `RuleRegistration`,
  `DuplicateRuleSourceError`, `DuplicateFindingError`,
  `IncompatibleRuleOutputError`, `AnalysisOptions`, `Category`, `Finding`,
  `Source`, `generate_unicode_text_cases`, `UNICODE_FAMILIES`, and
  `assert_structural_invariant`.
- Produces: bounded pytest coverage for `registry.order.*`,
  `registry.selection.*`, `registry.find.*`, and `registry.fail_closed.*`
  invariants without modifying any production contract.

- [x] **Step 1: Write the failing generated-property tests**

Create `tests/test_rule_registry_properties.py` with tests that call absent
`_assert_registry_order_properties()` and
`_assert_generated_fail_closed_properties()`. The protected production changes
are source sorting, unordered selection/result accumulation, changed execution
order, and missing duplicate or incompatible-output rejection.

```python
def test_generated_registry_order_and_category_subsets_are_deterministic() -> None:
    _assert_registry_order_properties()


def test_generated_registry_invalid_output_fails_closed_without_text() -> None:
    _assert_generated_fail_closed_properties()
```

For the privacy assertion, use one generated case as the `find()` input and
require every captured accepted registry error to include only the intended
safe message and omit `case.text`.

- [x] **Step 2: Run the focused test and verify RED**

Run `uv run --locked --extra dev pytest tests/test_rule_registry_properties.py -v`.
Expected: both tests fail with `NameError` for their missing helper, proving
the generated guardrail does not yet exist. Do not add the helpers until that
failure is observed and recorded. If the real registry fails a structural
invariant after the helpers are added, stop and report its replay metadata for
a new regression-first bug issue.

- [x] **Step 3: Add minimal real-registry property helpers**

Add a test-local fake `Rule` with a safe `Source`, fixed declared `Category`,
and fixed ordered `Finding` tuple. Build at most four registrations per replay
case from a literal ordered category catalogue and safe replay-derived source
names. Build at least three distinct registration orders per case (configured,
reversed, and replay-permuted with explicit index tie-breakers). For every
order, request two distinct registered categories so at least two rules are
selected and at least one registration is excluded:

```python
registry = DeterministicRuleRegistry(registrations)
expected_rules = tuple(spec.source for spec in registrations)
expected_selected = tuple(
    spec.source for spec in registrations if spec.category in requested
)
expected_findings = tuple(
    finding.id
    for spec in registrations
    if spec.category in requested
    for finding in spec.findings
)
```

Compare the corresponding real `rules()`, `selected_rules(requested)`, and
two repeated `find(case.text, options=AnalysisOptions(categories=requested))`
calls using `assert_structural_invariant`. Assert selected-rule order,
execution order, cross-rule finding-source order, and within-rule finding-ID
order independently. First verify the default cases' family union equals
`UNICODE_FAMILIES`. Keep all expected sequences test-local; do not call registry
methods to build them.

For every replay case, construct and assert the exact accepted error type for:

```python
DeterministicRuleRegistry((registration, duplicate_source_registration))
registry.find(case.text, options=AnalysisOptions(categories=None))  # duplicate ID
registry.find(case.text, options=AnalysisOptions(categories=None))  # wrong source
registry.find(case.text, options=AnalysisOptions(categories=None))  # wrong category
```

Use separate registry instances for the three `find()` failures. Convert a
missing error, a wrong registry-error subtype, or an unexpected exception into
an `assert_structural_invariant` failure containing only a
`registry.fail_closed.*` identifier and matching replay metadata. Separately
check that accepted error messages omit `case.text`. Do not add a production
helper or change the registry.

- [x] **Step 4: Run focused, existing registry, and protocol tests to verify GREEN**

Run:

```bash
uv run --locked --extra dev pytest \
  tests/test_rule_registry_properties.py tests/test_rules.py tests/test_protocols.py -v
```

Every generated property and authored registry/protocol regression must pass.
A generated property failure is a stop condition; do not repair production code
in this issue.

- [x] **Step 5: Self-review the issue boundary**

Run:

```bash
git diff --check
git diff -- src/polis
git status --short
rg -n "TBD|TODO|PRIVATE" tests/test_rule_registry_properties.py \
  docs/superpowers/specs/2026-08-02-issue-128-rule-registry-properties-design.md \
  docs/superpowers/plans/2026-08-02-issue-128-rule-registry-properties.md
```

Expect no whitespace errors, no `src/polis` diff, no placeholders, and only
the three issue files plus the untracked controller report. Re-read every
acceptance criterion and apply the mutation check: source sorting, reversed
selection, reordered rule output, duplicate acceptance, and incompatible output
acceptance must each make a property fail.

- [x] **Step 6: Run required verification**

```bash
uv run --locked --extra dev pytest \
  tests/test_rule_registry_properties.py tests/test_rules.py tests/test_protocols.py -v
uv run --locked --extra dev pytest -m "not research and not slow and not model"
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
git diff --check
```

Every command must exit zero. Do not commit if a generated property finds a
production defect; preserve only safe replay metadata and stop.

- [x] **Step 7: Write the handoff report and create one focused commit**

Write `.superpowers/sdd/issue-128-agent-report.md` with the design/plan paths,
RED and GREEN evidence, changed files, all command results, acceptance review,
self-review, and risks. Keep it untracked. Stage only the test, design, and
plan files and commit:

```bash
git commit -m "test: add rule registry ordering properties (#128)"
```

Do not push, create a pull request, merge, or mutate GitHub.

## Plan self-review

- The task covers configured rule order, category-subset relative order,
  repeated calls, registration permutations, finding order, every requested
  invalid registration/output class, and privacy-safe diagnostics.
- Expected values use test-local ordered specifications rather than production
  ordering logic, and every assertion exercises the real registry.
- The plan has no production-code task, API change, dependency, or linguistic
  scope expansion.
- Every required focused, fast-suite, static, and whitespace verification
  command is explicit.
