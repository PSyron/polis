# Generated Pipeline Parity Properties Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bounded deterministic generated evidence that synchronous and
asynchronous analysis pipeline calls have identical successful and controlled
failure behavior.

**Architecture:** A single test module consumes #123's Unicode/replay harness,
the unchanged pipeline entry points, and narrow deterministic fakes for the
`RuleRegistry` and `LocalFindingBackend` protocols. It observes real pipeline
results, fragment translation, normalization, and error canonicalization while
keeping generated failure diagnostics replay-safe.

**Tech Stack:** Python 3.12+, pytest, `tests.generative`, public Polis core
models/protocols, existing analysis pipeline, Ruff, and mypy.

## Global Constraints

- Implement only GitHub issue #130; #95 stays open and #119 is out of scope.
- Use only #123's `unicode-structural-v1` default seed `95001` and 64-case
  budget; no ambient configuration, new dependency, live backend, network,
  corpus, holdout, model, or evaluation path is allowed.
- Preserve public/error contracts, ADR-0003 atomic all-or-error behavior,
  ADR-0018 pipeline ownership, offline privacy, canonical order, and Unicode
  code-point half-open offsets `[start, end)`.
- Generated failure diagnostics may expose only structural invariant names and
  replay metadata. They must never expose analyzed text, fragment text,
  prompts, unsafe backend messages, or unsafe backend context.
- Do not alter `src/`, retry policy, CI configuration, corpora, holdouts,
  models, evaluation data, dependencies, attribution, or unrelated files. A
  discovered production defect is a stop condition for a separate
  regression-first bug issue.
- Finish as one focused commit referencing `#130`; do not push, create a PR,
  merge, comment on, or close an issue. Keep the agent report untracked.

---

### Task 1: Add generated sync/async pipeline parity properties

**Files:**

- Create: `tests/test_generated_pipeline_parity.py`
- Create: `docs/superpowers/specs/2026-08-02-issue-130-pipeline-parity-design.md`
- Create: `docs/superpowers/plans/2026-08-02-issue-130-pipeline-parity.md`
- Create: `.superpowers/sdd/issue-130-agent-report.md` (git-ignored handoff)
- Verify: `tests/generative.py`, `src/polis/analysis/pipeline.py`,
  `src/polis/analyzer.py`, `src/polis/core/protocols.py`,
  `src/polis/core/models.py`, and existing pipeline/analyzer/protocol tests.

**Interfaces:**

- Consumes: `generate_unicode_text_cases()`, `UNICODE_FAMILIES`,
  `assert_structural_invariant()`, `analyze_text()`, `analyze_text_async()`,
  `RuleRegistry`, `LocalFindingBackend`, `Finding`, and public controlled
  `PolisError` subclasses.
- Produces: fast, bounded generated structural evidence only; no public or
  production interface.

- [x] **Step 1: Write the failing generated parity test**

Create `tests/test_generated_pipeline_parity.py` first with the following
minimal real-pipeline entry point. Do not define
`_assert_generated_success_parity` yet; its NameError is the proof that the
new guardrail is initially absent. The mutation this test protects is a sync
wrapper, normalization, fragment-translation, or error-canonicalization
regression that makes the two entry points observably differ.

```python
from __future__ import annotations

from tests.generative import generate_unicode_text_cases


def test_generated_sync_and_async_success_results_are_equal() -> None:
    for case in generate_unicode_text_cases():
        _assert_generated_success_parity(case)
```

Run:

```bash
uv run --locked --extra dev pytest tests/test_generated_pipeline_parity.py -v
```

Expected: the one test fails with `NameError` for
`_assert_generated_success_parity`. Record command, non-zero exit status, and
the expected failure in `.superpowers/sdd/issue-130-agent-report.md` before
adding any test support. If a real pipeline invariant fails after the helper
exists, stop without changing production code.

- [x] **Step 2: Add minimal deterministic success and offset properties**

Add test-local `GeneratedRegistry` and `GeneratedBackend` fakes. The registry
returns one stable rule insertion at literal offset `[0, 0)` for every source,
including empty input.
The backend returns zero findings for an empty fragment and two valid
fragment-local findings in reverse literal local-span order for non-empty
fragments: a replacement over `[0, 1)` and, when the fragment has more than
one code point, a deletion over `[len(fragment)-1, len(fragment))`. Give them
distinct stable `rule:generated-parity` and `llm:generated-parity` sources,
fixed presentation fields, and suggestions that differ from originals.

Define `_pipeline_results(text)` to run `analyze_text()` and
`asyncio.run(analyze_text_async())` with exactly the same inputs. Define the
missing success helper from Step 1 to call it, submit equality to
`assert_structural_invariant(..., invariant="pipeline.sync_async.equal",
replay=case.replay)`, and compare the returned tuple with a hand-built
canonical sequence: the rule insertion first, followed by each sentence
fragment's replacement then tail deletion in source order. For every finding
verify bounds and `original == case.text[start:end]` through replay-safe
assertions. For each `llm:generated-parity` finding independently verify the
hand-translated fragment-local span and original source slice.

Add a second property that obtains default cases twice, checks exact 64-case
budget, equal replay sequences, equal parity signatures, and a family union
equal to `UNICODE_FAMILIES`. Use only shared structural assertions and the
last replay for run-level conditions. Do not assert fake call counts or use a
mock framework.

- [x] **Step 3: Add controlled-failure parity properties**

Parameterize a failure-mode fixture over `BackendUnavailableError`,
`AnalysisTimeoutError`, and `InvalidBackendResponseError`. For the matching
fake backend mode, raise that type with an unsafe backend message/context that
includes only a test sentinel and the received fragment. Invoke both public
pipeline entry points through a helper that captures a `PolisError` without
formatting the exception. Require the type, `code`, `retryable`, and context
to match each other and these hand-derived canonical values:

```python
BackendUnavailableError, "backend.unavailable", True
AnalysisTimeoutError, "analysis.timeout", True
InvalidBackendResponseError, "backend.invalid_response", False
context == {"operation": "generated.analysis.llm", "backend": "generated-backend"}
```

Use the current generated case's replay metadata for every asserted condition.
Convert any diagnostic privacy check to a boolean first, then pass it through
`assert_structural_invariant`; neither raw error nor generated source may be
included in an assertion message. Confirm the canonical message/context do not
contain the test sentinel or source/fragment text.

- [x] **Step 4: Verify focused generated and existing contract tests**

Run each command and require a zero exit status:

```bash
uv run --locked --extra dev pytest tests/test_generated_pipeline_parity.py -v
uv run --locked --extra dev pytest tests/test_analysis_pipeline.py tests/test_analyzer_languagetool_config.py tests/test_api_contract.py tests/test_protocols.py -v
```

The first command proves successful parity, canonical ordering, offset/slice
translation, controlled failures, privacy-safe replay, determinism, and fixed
budget. The second preserves existing pipeline, analyzer, API/error, and
protocol contracts. A failure showing a production defect stops this issue.

- [x] **Step 5: Self-review the generated guardrail**

Review `tests/test_generated_pipeline_parity.py` against the issue/design:
each test must name a behavior-breaking mutation; expectations must be literal
or hand-derived; fake outputs must be input-specific; and assertions must
target real pipeline results/errors, not calls to a fake. Confirm no source
text is formatted into a test failure and no live/model/network/corpus/holdout
path is imported or called. Run:

```bash
git diff --check
git diff -- src/polis
rg -n "TBD|TODO|issue-119|holdout|corpus|requests|httpx|socket|urllib" \
  tests/test_generated_pipeline_parity.py \
  docs/superpowers/specs/2026-08-02-issue-130-pipeline-parity-design.md \
  docs/superpowers/plans/2026-08-02-issue-130-pipeline-parity.md
```

- [ ] **Step 6: Run complete verification and make the focused commit**

Run fresh:

```bash
uv run --locked --extra dev pytest tests/test_generated_pipeline_parity.py -v
uv run --locked --extra dev pytest tests/test_analysis_pipeline.py tests/test_analyzer_languagetool_config.py tests/test_api_contract.py tests/test_protocols.py -v
uv run --locked --extra dev pytest -m "not research and not slow and not model"
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
git diff --check
```

Stage only the new test and design/plan documents, verify the staged diff, and
create the required single commit:

```bash
git add \
  tests/test_generated_pipeline_parity.py \
  docs/superpowers/specs/2026-08-02-issue-130-pipeline-parity-design.md \
  docs/superpowers/plans/2026-08-02-issue-130-pipeline-parity.md
git diff --cached --check
git diff --cached --stat
git commit -m "test: add generated pipeline parity properties (#130)"
```

- [ ] **Step 7: Record the handoff and inspect the committed change**

Write `.superpowers/sdd/issue-130-agent-report.md` with the issue number,
design and plan paths, exact RED/GREEN results, changed files, acceptance
evidence, self-review, all verification results, known limitations, and the
next permitted action. Keep it untracked. Review `git show --check --stat
HEAD` and the full committed diff before reporting status.

## Plan self-review

- Success parity, canonical order, fragment-local offset translation,
  controlled-error equivalence, replay determinism/budget, and offline-only
  execution each have a concrete test step.
- The plan changes a single test module and its required design/plan artifacts;
  it prohibits production repair and all excluded data/model work.
- Test-local names and public interfaces are defined before later steps use
  them; no placeholder implementation or dependency is required.
