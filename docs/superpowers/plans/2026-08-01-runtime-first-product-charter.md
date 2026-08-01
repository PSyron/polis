# Runtime-First Product Charter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the runtime-first charter the unambiguous project authority, split product delivery from optional model research, and reconcile the complete open M5/M6 GitHub portfolio before closing #120.

**Architecture:** Revise the living product specification in place, record the superseding decision in ADR-0020, and enforce the new authority with executable documentation-policy tests. Keep repository changes reviewable and merge them before applying an exact, idempotent GitHub migration that moves product and research work into separate milestones, closes only explicitly superseded issues, and closes #120 last.

**Tech Stack:** Markdown, Python 3.12+, pytest 9, Ruff 0.15, strict mypy, uv 0.11.2, Hatchling, GitHub CLI 2.95+, GitHub Actions.

## Global Constraints

- Work only on issue #120 until the migration is complete.
- Use the short-lived branch `codex/runtime-first-charter` from current `origin/main`.
- Keep code, identifiers, ADRs, plans, and GitHub metadata in English; `PROMPT.md` remains Polish.
- Polis must be a complete offline product without a local model, Java process, network service, or research corpus.
- A local model is optional, disabled by default, always review-only, and never a runtime release dependency.
- LanguageTool remains optional, local-only, version-pinned, and disabled by default.
- Preserve public API behavior, JSON schemas, finding identity, Unicode half-open offsets, privacy boundaries, correction conflict behavior, and fail-closed semantics.
- Do not change runtime source files or add production dependencies in this migration.
- Do not rerun consumed holdouts or edit research reports, results, corpora, or model artifacts.
- Preserve historical evidence; close superseded issues as not planned, never as completed.
- Prepare and review the exact GitHub mutation set before applying any live metadata changes.
- Do not close #120 until repository changes are merged and the post-mutation GitHub inventory passes.

---

## File map

| File | Responsibility |
| --- | --- |
| `PROMPT.md` | Living product charter and source of truth |
| `docs/architecture/decisions/0020-runtime-first-product-charter.md` | Accepted decision that supersedes the mandatory-model critical path |
| `docs/architecture/README.md` | ADR index |
| `tests/test_product_charter_policy.py` | Executable product/research authority and portfolio contract |
| `docs/project/ROADMAP.md` | Active product lane, optional research lane, future architecture, and historical record |
| `docs/project/RISKS.md` | Risks introduced or resolved by the portfolio split |
| `docs/limitations.md` | Current product claims without old mandatory-M5 language |
| `docs/llm-quality-gates.md` | Optional model-promotion evidence, not runtime release authority |
| `docs/prerelease-candidate.md` | Runtime-only prerelease gates |
| `docs/compatibility.md` | Compatibility and optional-extension guarantees |
| `README.md` | User-facing runtime-first summary and charter link |
| `docs/project/runtime-first-portfolio-disposition.md` | Exact, auditable before/after GitHub mutation manifest |

## Task 0: Establish the post-PR-121 baseline

**Files:**
- Read only: `PROMPT.md`, `docs/project/ROADMAP.md`, `docs/project/RISKS.md`, `docs/limitations.md`, `tests/test_hybrid_architecture_policy.py`
- No files modified.

**Interfaces:**
- Consumes: branch `codex/runtime-first-charter` at commit `2ab0bc3`.
- Produces: recorded local and GitHub baseline for later comparison.

- [ ] **Step 1: Confirm branch and worktree state**

Run:

```console
git status --short --branch
git log -2 --oneline --decorate
git merge-base origin/main HEAD
```

Expected: clean `codex/runtime-first-charter`; HEAD contains only the committed design above current `origin/main`.

- [ ] **Step 2: Run the current product path**

Run:

```console
uv run --locked --extra dev pytest -m "not research and not slow and not model"
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
```

Expected: all commands pass. Record exact test counts.

- [ ] **Step 3: Capture the live portfolio baseline**

Run:

```console
gh api 'repos/PSyron/polis/milestones?state=all&per_page=100'
gh issue list --repo PSyron/polis --state open --limit 100 \
  --json number,title,labels,milestone,state
```

Confirm:

- M5 has 14 open issues: #43, #64, #66, #76, #84–#90, #92, #93, and #119;
- M6 has #95–#100;
- #120 is open with no milestone;
- no `status:superseded` label exists yet.

- [ ] **Step 4: Commit**

No commit is created for this baseline task.

## Task 1: Make the runtime-first charter authoritative

**Files:**
- Create: `docs/architecture/decisions/0020-runtime-first-product-charter.md`
- Create: `tests/test_product_charter_policy.py`
- Modify: `PROMPT.md`
- Modify: `docs/architecture/README.md`
- Test: `tests/test_product_charter_policy.py`

**Interfaces:**
- Consumes: the accepted design in `docs/superpowers/specs/2026-08-01-runtime-first-product-charter-design.md`.
- Produces: authoritative charter phrases and ADR-0020, consumed by Tasks 2 and 3.

- [ ] **Step 1: Add failing authority tests**

Create `tests/test_product_charter_policy.py` with these paths and assertions:

```python
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "PROMPT.md"
ADR = ROOT / "docs" / "architecture" / "decisions" / (
    "0020-runtime-first-product-charter.md"
)
ARCHITECTURE_INDEX = ROOT / "docs" / "architecture" / "README.md"
ROADMAP = ROOT / "docs" / "project" / "ROADMAP.md"
PORTFOLIO = ROOT / "docs" / "project" / "runtime-first-portfolio-disposition.md"


def test_prompt_defines_a_complete_runtime_without_a_model() -> None:
    prompt = PROMPT.read_text(encoding="utf-8")

    for phrase in (
        "Polis jest kompletnym produktem bez lokalnego modelu językowego",
        "Model lokalny jest opcjonalnym rozszerzeniem",
        "nie blokuje wydania runtime'u",
        "zawsze pozostaje sugestią wymagającą jawnej akceptacji",
    ):
        assert phrase in prompt

    assert "po zainstalowaniu zależności i lokalnego modelu" not in prompt
    assert (
        "Powinien łączyć szybkie, deterministyczne reguły z lokalnym, "
        "niewielkim modelem językowym"
    ) not in prompt


def test_accepted_charter_adr_supersedes_only_the_mandatory_model_path() -> None:
    assert ADR.exists()
    decision = ADR.read_text(encoding="utf-8")

    for phrase in (
        "Status: Accepted",
        "complete product without a local language model",
        "always review-only",
        "never blocks a runtime release",
        "consumed holdouts",
        "Issue #120",
    ):
        assert phrase in decision


def test_architecture_index_links_the_runtime_first_charter() -> None:
    index = ARCHITECTURE_INDEX.read_text(encoding="utf-8")
    assert "0020-runtime-first-product-charter.md" in index
```

The roadmap and portfolio constants are intentionally unused until Tasks 2 and 3. Add `# noqa: F841` only if Ruff reports a violation; do not weaken project lint configuration.

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```console
uv run --locked --extra dev pytest tests/test_product_charter_policy.py -v
```

Expected: FAIL because ADR-0020 and the required charter language do not exist.

- [ ] **Step 3: Revise `PROMPT.md` in place**

Make these decisions explicit in Polish:

- replace the mandatory rules-plus-model vision with the exact sentence `Polis jest kompletnym produktem bez lokalnego modelu językowego`;
- add `Model lokalny jest opcjonalnym rozszerzeniem` and state that its research `nie blokuje wydania runtime'u`;
- change first-version item 3 to require deterministic analyzers and permit explicitly configured optional local extensions;
- change item 8 so offline operation requires only default dependencies, not a model;
- describe `llm` as an optional protocol, prompt, and validation layer;
- require a separate accepted issue and ADR before selecting a supported model configuration;
- rename the LLM rules section to optional-model rules and state that every model-derived or model-selected edit `zawsze pozostaje sugestią wymagającą jawnej akceptacji`;
- rename proposed M2 to optional local-model research and state that M2 never blocks M3/M4 runtime delivery;
- preserve privacy, testing, API, evaluation, and failure-handling requirements.

Do not delete the `llm` module requirement or historical evaluation requirements. Change their authority and sequencing only.

- [ ] **Step 4: Add ADR-0020**

Create an accepted ADR with these sections:

```markdown
# ADR-0020: Adopt a runtime-first product charter

**Status: Accepted**
**Date:** 2026-08-01
**Issue:** #120

## Context
## Decision
## Product release authority
## Optional model extension
## Portfolio consequences
## Compatibility and safety
## Consequences
## Superseded authority
```

Record that Polis is a complete product without a local language model, model output is always review-only, research never blocks runtime release, LanguageTool remains optional, consumed holdouts remain immutable, and only the mandatory-model critical path is superseded. Preserve ADR-0008's automatic-versus-reviewable safety rules.

- [ ] **Step 5: Index ADR-0020**

Add an `Accepted` row to `docs/architecture/README.md` immediately after ADR-0019.

- [ ] **Step 6: Run focused checks**

Run:

```console
uv run --locked --extra dev pytest tests/test_product_charter_policy.py -v
uv run --locked --extra dev ruff check tests/test_product_charter_policy.py
uv run --locked --extra dev ruff format --check tests/test_product_charter_policy.py
git diff --check
```

Expected: authority tests pass; unused Task 2/3 constants do not cause lint failures.

- [ ] **Step 7: Commit**

```console
git add PROMPT.md docs/architecture/README.md \
  docs/architecture/decisions/0020-runtime-first-product-charter.md \
  tests/test_product_charter_policy.py
git commit -m "docs: adopt runtime-first product charter (#120)"
```

## Task 2: Replace the mandatory M5 release graph with product and research lanes

**Files:**
- Modify: `docs/project/ROADMAP.md`
- Modify: `docs/project/RISKS.md`
- Modify: `docs/limitations.md`
- Modify: `docs/llm-quality-gates.md`
- Modify: `docs/prerelease-candidate.md`
- Modify: `docs/compatibility.md`
- Modify: `README.md`
- Modify: `tests/test_product_charter_policy.py`
- Modify: `tests/test_hybrid_architecture_policy.py`
- Test: `tests/test_product_charter_policy.py`, `tests/test_hybrid_architecture_policy.py`, `tests/test_package_smoke.py`, `tests/test_prerelease_candidate.py`

**Interfaces:**
- Consumes: authoritative phrases and ADR-0020 from Task 1.
- Produces: one active product delivery graph and one optional research graph.

- [ ] **Step 1: Add failing roadmap and release-policy tests**

Append to `tests/test_product_charter_policy.py`:

```python
def test_roadmap_separates_product_delivery_from_optional_research() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")

    for heading in (
        "## Active product lane",
        "## Optional research lane",
        "## Future product architecture",
        "## Historical delivery record",
    ):
        assert heading in roadmap

    for phrase in (
        "#120 -> #84 -> #95",
        "#119 -> #76 -> (#85 + #86) -> #87 -> (#88 + #89) -> #90",
        "Research outcomes do not block runtime releases",
    ):
        assert phrase in roadmap

    assert "#76 -> #84" not in roadmap
    assert "M5 majority-error graph from umbrella #93 is authoritative" not in roadmap


def test_release_docs_do_not_require_model_research() -> None:
    documents = {
        path.name: path.read_text(encoding="utf-8")
        for path in (
            ROOT / "README.md",
            ROOT / "docs" / "limitations.md",
            ROOT / "docs" / "llm-quality-gates.md",
            ROOT / "docs" / "prerelease-candidate.md",
            ROOT / "docs" / "compatibility.md",
        )
    }

    joined = "\n".join(documents.values())
    assert "optional model research never blocks a runtime release" in joined
    assert "tracked by M5 and [#43]" not in joined
    assert "until later M5 selection" not in joined
```

Update `tests/test_hybrid_architecture_policy.py` so the historical M5 order test checks only that the completed historical record remains documented. Remove assertions that require #43 to precede #64 as the active delivery path. Keep ADR-0008 safety assertions unchanged.

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```console
uv run --locked --extra dev pytest \
  tests/test_product_charter_policy.py \
  tests/test_hybrid_architecture_policy.py \
  tests/test_package_smoke.py \
  tests/test_prerelease_candidate.py -v
```

Expected: new roadmap/release-policy tests fail on old M5 authority language.

- [ ] **Step 3: Restructure the roadmap**

At the top of `docs/project/ROADMAP.md`, after delivery rules, add the active sections in this order:

1. `## Active product lane`
   - `#120 -> #84 -> #95`;
   - product release gates are contracts, privacy, deterministic behavior, versioned automatic policy, packaging, offline installation, and release identity;
   - #84 is independent from #76; new automatic privileges still need evidence.
2. `## Optional research lane`
   - exact graph `#119 -> #76 -> (#85 + #86) -> #87 -> (#88 + #89) -> #90`;
   - exact sentence `Research outcomes do not block runtime releases`;
   - no due date and no product dependency edge.
3. `## Future product architecture`
   - #96–#100 remain M6 and do not block current releases.
4. `## Superseded M5 release train`
   - #43, #64, #66, #92, and #93 are superseded by ADR-0020;
   - their acceptance criteria are not represented as completed.
5. `## Historical delivery record`
   - retain completed M0–M5 history below this heading;
   - remove active critical-path text and the `#76 -> #84` edge;
   - label old M5 dependency tables as historical evidence.

Do not erase completed issue history or experiment outcomes.

- [ ] **Step 4: Align risks and product documentation**

Update the listed files consistently:

- `RISKS.md`: add mandatory-model recoupling, false completion claims on superseded issues, and issue-metadata drift; assign #120/#84/#95 as appropriate owners. Reclassify old model risks as optional research risks.
- `limitations.md`: remove statements that production support waits for #43 or later M5 selection. Preserve exact failed qualification results and state that optional model research never blocks a runtime release.
- `llm-quality-gates.md`: label suggestion/model gates as promotion evidence for an optional extension; retain deterministic automatic-correction gates as product policy.
- `prerelease-candidate.md`: state that runtime prerelease verification does not execute or depend on model research or consumed holdouts.
- `compatibility.md`: state that model backends are optional extensions and absence is not a degraded core-runtime state.
- `README.md`: link ADR-0020 and state that Polis is complete without a model; preserve the no-qualified-model limitation.

- [ ] **Step 5: Run focused documentation checks**

Run:

```console
uv run --locked --extra dev pytest \
  tests/test_product_charter_policy.py \
  tests/test_hybrid_architecture_policy.py \
  tests/test_package_smoke.py \
  tests/test_prerelease_candidate.py -v
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
git diff --check
```

Expected: all checks pass and historical evidence remains present without active mandatory-model release language.

- [ ] **Step 6: Commit**

```console
git add README.md docs/compatibility.md docs/limitations.md \
  docs/llm-quality-gates.md docs/prerelease-candidate.md \
  docs/project/RISKS.md docs/project/ROADMAP.md \
  tests/test_hybrid_architecture_policy.py tests/test_product_charter_policy.py
git commit -m "docs: separate product and research delivery (#120)"
```

## Task 3: Record the exact portfolio migration contract

**Files:**
- Create: `docs/project/runtime-first-portfolio-disposition.md`
- Modify: `tests/test_product_charter_policy.py`
- Test: `tests/test_product_charter_policy.py`

**Interfaces:**
- Consumes: active product/research lanes from Task 2.
- Produces: the authoritative before/after manifest used for live GitHub mutations in Task 6.

- [ ] **Step 1: Add a failing exact-disposition test**

Append:

```python
def test_portfolio_manifest_covers_every_affected_open_issue_exactly_once() -> None:
    portfolio = PORTFOLIO.read_text(encoding="utf-8")
    product = {84, 95, 120}
    research = {76, 85, 86, 87, 88, 89, 90, 119}
    superseded = {43, 64, 66, 92, 93}
    future = {96, 97, 98, 99, 100}

    groups = (product, research, superseded, future)
    assert all(
        left.isdisjoint(right)
        for index, left in enumerate(groups)
        for right in groups[index + 1 :]
    )
    for issue in set().union(*groups):
        assert portfolio.count(f"| #{issue} |") == 1

    for phrase in (
        "Runtime 0.x Hardening",
        "Research — Optional Local Model Qualification",
        "status:superseded",
        "not planned",
        "acceptance criteria were not completed",
    ):
        assert phrase in portfolio
```

- [ ] **Step 2: Run the test and verify failure**

Run:

```console
uv run --locked --extra dev pytest \
  tests/test_product_charter_policy.py::test_portfolio_manifest_covers_every_affected_open_issue_exactly_once -v
```

Expected: FAIL because the manifest does not exist.

- [ ] **Step 3: Create the portfolio manifest**

Create `docs/project/runtime-first-portfolio-disposition.md` with:

- decision authority: #120, ADR-0020, and the accepted charter spec;
- current baseline date and repository;
- exact milestone definitions:
  - `Runtime 0.x Hardening`: active product safety and invariant work; no due date;
  - `Research — Optional Local Model Qualification`: optional evidence work; no due date;
- an exact table with one row for every issue below:

| Group | Issues | Target state |
| --- | --- | --- |
| Product | #84, #95, #120 | Open; `Runtime 0.x Hardening`; #84 unblocked from #76 |
| Research | #76, #85–#90, #119 | Open; research milestone; internal research blockers only |
| Superseded | #43, #64, #66, #92, #93 | Closed as `not planned`; add `status:superseded`; remove `status:blocked` |
| Future product | #96–#100 | Open; remain in M6; no current-release dependency |

The actual manifest table must use one row per issue with columns for current state, target state, labels, milestone, dependency/body change, and closure reason.

Include these exact mutation rules:

- #84 body replaces `Depends on completion of #76` with an implementation-independent section; remove `status:blocked`.
- #95 body records product-hardening disposition and move.
- #100 treats #95 as an external hardening prerequisite, not an M6 child; its child checklist is #96–#99.
- #76 body names #119 as its current research dependency; other research bodies retain internal research dependencies.
- every research body says it does not block runtime releases.
- superseded comments say `The acceptance criteria were not completed.` and identify surviving work.
- #120 changes to `type:decision`, `area:core`, `priority:P0`, and the runtime milestone.
- M5 closes only after its open issue count reaches zero.
- #120 closes only after every live-state assertion passes.

- [ ] **Step 4: Run focused checks**

Run:

```console
uv run --locked --extra dev pytest tests/test_product_charter_policy.py -v
uv run --locked --extra dev ruff check tests/test_product_charter_policy.py
uv run --locked --extra dev ruff format --check tests/test_product_charter_policy.py
git diff --check
```

- [ ] **Step 5: Commit**

```console
git add docs/project/runtime-first-portfolio-disposition.md \
  tests/test_product_charter_policy.py
git commit -m "docs: record runtime-first portfolio migration (#120)"
```

## Task 4: Verify the repository migration

**Files:**
- No new tracked files.
- Review: every file changed in Tasks 1–3.

**Interfaces:**
- Consumes: completed repository migration commits.
- Produces: a branch eligible for independent review and publication.

- [ ] **Step 1: Run the product suite**

```console
uv run --locked --extra dev pytest -m "not research and not slow and not model"
```

Expected: all product tests pass.

- [ ] **Step 2: Run static checks**

```console
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
```

- [ ] **Step 3: Verify release artifacts and offline installation**

Create a new temporary output directory with `mktemp -d`, then run:

```console
uv run --locked --extra dev python -m build --no-isolation --outdir "$POLIS_CHARTER_DIST"
uv run --locked --extra dev python scripts/verify_distribution_artifacts.py --dist "$POLIS_CHARTER_DIST"
uv run --locked --extra dev python scripts/verify_distribution_install.py --dist "$POLIS_CHARTER_DIST"
```

Use a task-specific variable named `POLIS_CHARTER_DIST`; never repurpose `HOME` or another system variable.

- [ ] **Step 4: Collect, but do not execute, research tests**

```console
uv run --locked --extra dev pytest -m research --collect-only -q
```

Record the count. Do not execute consumed holdouts.

- [ ] **Step 5: Review final branch state**

```console
git diff --check origin/main..HEAD
git status --short --branch
git log --oneline --decorate origin/main..HEAD
```

Expected: clean branch, no generated artifacts, and focused #120 commits only.

- [ ] **Step 6: Independent whole-branch review**

Review the full range from `git merge-base origin/main HEAD` to `HEAD`. Require no Critical, High, or Medium findings. Fix any findings through a fresh implementer and scoped re-review before publication.

## Task 5: Publish, review, and merge the repository changes

**Files:**
- No additional tracked files unless review findings require a focused fix.

**Interfaces:**
- Consumes: clean reviewed branch from Task 4.
- Produces: merged charter and migration manifest on `main`.

- [ ] **Step 1: Push the branch**

```console
git push -u origin codex/runtime-first-charter
```

- [ ] **Step 2: Open a draft PR to `main`**

Use title:

```text
docs: adopt runtime-first product charter
```

The body must summarize the authority change, product/research lanes, exact portfolio migration, validation, and the fact that live GitHub mutations occur only after merge. Use `Refs #120`, not `Closes #120`.

- [ ] **Step 3: Wait for remote CI and review**

Require every Fast CI matrix job to pass. Resolve actionable review findings through focused commits and rerun the relevant local and remote checks.

- [ ] **Step 4: Mark ready and merge**

After green CI and clean review, mark the PR ready and squash-merge it to `main`. Delete the remote feature branch. Do not close #120 through the PR body.

- [ ] **Step 5: Confirm merge**

```console
git fetch origin --prune
git log -1 --oneline origin/main
gh pr view --repo PSyron/polis --json state,mergedAt,mergeCommit,url
```

Expected: PR state `MERGED`, and `origin/main` contains the charter squash commit.

## Task 6: Apply the live GitHub portfolio migration

**Files:**
- Read: `docs/project/runtime-first-portfolio-disposition.md` from merged `origin/main`.
- Scratch only: exact issue body/comment files under the ignored SDD workspace.
- No tracked repository files modified.

**Interfaces:**
- Consumes: merged manifest and ADR-0020.
- Produces: live GitHub issues and milestones matching the charter.

- [ ] **Step 1: Re-read and compare live state**

Fetch all target issues with `state`, `body`, `labels`, `milestone`, `blockedBy`, and `blocking`. Stop if a maintainer or automation changed an issue incompatibly after the Task 0 baseline. Additive comments are not conflicts; changed goals, state, or milestone are.

- [ ] **Step 2: Create idempotent labels and milestones**

Create `status:superseded` only if absent:

```console
gh label create status:superseded --repo PSyron/polis \
  --description "Replaced by an accepted product or architecture decision" \
  --color BFDADC
```

Create these milestones only if exact-title lookup returns no result:

```text
Runtime 0.x Hardening
Research — Optional Local Model Qualification
```

Use `gh api --method POST repos/PSyron/polis/milestones` with the exact descriptions from the manifest and no due date.

- [ ] **Step 3: Move and clarify product issues**

- #120: replace `type:chore` with `type:decision`, replace `area:packaging`
  with `area:core`, keep `priority:P0`, assign `Runtime 0.x Hardening`, and
  update its checklist/body to reference PR #121 as Phase 1 and the merged
  charter as the final migration. The body must carry the #84 P0 / #95 P1
  distinction and state that shared milestone membership and roadmap sequencing
  do not make #95 a current runtime-release blocker.
- #84: assign `Runtime 0.x Hardening`, remove `status:blocked`, and perform a
  complete heading-delimited body section replacement for the legacy dependency
  section. Remove body claims that #84 depends on #76, blocks #64, or blocks
  final release authorization.
- #95: assign `Runtime 0.x Hardening` and perform a complete heading-delimited
  body section replacement for legacy M5 publication or non-publication wording.
  The live body must state that #95 is P1 hardening after #84 and does not block
  the current runtime release by shared milestone membership or roadmap
  sequencing alone.
- #100: keep M6, remove #95 from the child checklist, and perform a complete
  heading-delimited body section replacement for any legacy #93/current-M5
  release-authority section. Record #95 as an external product-hardening
  prerequisite, not an M6 child.

Complete body edits must preserve unrelated body content while replacing only
the heading-delimited sections named below. For #95 and #100, use the exact
old-to-new anchor substitutions recorded below instead of heading fallback. The
mutation must abort if any old anchor is missing, appears more than once, or
differs from the recorded live text. Do not append these templates as a fallback
for #95 or #100.

#84: replace the complete heading-delimited dependency section with the exact
`## Runtime-first product-safety dependency` template:

```markdown
## Runtime-first product-safety dependency

Classification: P0 product-safety work under ADR-0020 and #120.

This issue is independent from #76 and optional model research. Automatic
correction privileges are versioned product behavior and fail closed for every
unknown or changed source, category, operation, behavior, or policy version.

New automatic privileges still require direct source-behavior evidence before
they can enter the supported runtime policy. Shared milestone membership and
roadmap sequencing do not make #95 a current runtime-release blocker.
```

#90: replace the complete heading-delimited dependency section with the exact
`## Runtime-first optional-research dependency` template:

```markdown
## Runtime-first optional-research dependency

Classification: optional research under ADR-0020 and #120.

This issue preserves installed-package majority-coverage research evidence. Its
outcome does not block a Polis runtime release and cannot qualify an unverified
model as supported product behavior.

Retained dependencies: #76, #85, #86, #88, and #89.
```

#95: replace the complete heading-delimited M5 publication section with the
exact `## Runtime-first product-hardening disposition` template. #95 old anchor
appears exactly once in the live body as the complete current
`## Dependencies and ordering` section:

```markdown
## Dependencies and ordering

- CI integration depends on #80.
- Work may begin in parallel with later M5 qualification once #80 is green.
- The completed invariant guardrail should precede broad migration to a shared analyzed-document representation.
- This umbrella does not block #76, #90, #92, or publication of M5.
```

Replace that exact old anchor with this exact new section:

```markdown
## Runtime-first product-hardening disposition

Classification: P1 hardening after #84 under ADR-0020 and #120.

#84 is the P0 product-safety gate for version-bound automatic privileges. #95
hardens generative and review-only invariants after that gate.

Shared `Runtime 0.x Hardening` milestone membership and the `#120 -> #84 -> #95`
roadmap sequence alone do not make #95 a blocker for the current runtime
release. A future accepted issue may explicitly make #95 a release blocker.

## Dependencies and ordering

- CI integration depends on #80.
- Work may begin in parallel with optional model qualification once #80 is green.
- The completed invariant guardrail should precede broad migration to a shared analyzed-document representation.
- This umbrella remains independent from #76, #90, and #92.
```

#100: replace the complete heading-delimited release-authority section with the
exact `## Runtime-first M6 architecture disposition` template. #100 old anchors
each appear exactly once in the live body and must be replaced independently so
unrelated content is preserved.

First #100 old anchor in `## Scope and sequencing policy`:

```markdown
The current M5 tracker #93 remains authoritative for the next release. M6 work must not become an implicit dependency of #76, #90, #66, or #92. A defect discovered by M6 can block a release only through a separately triaged issue with explicit evidence.
```

Replace it with:

```markdown
## Runtime-first M6 architecture disposition

Classification: future product architecture under ADR-0020 and #120.

Runtime release sequencing follows the runtime-first product lane and optional
research lane adopted by ADR-0020.

M6 work must not become an implicit dependency of #76, #90, #66, #92, #93, or a
runtime release. A defect discovered by M6 can block a release only through a
separately triaged issue with explicit evidence.
```

Second #100 old anchor in `## Dependency order`:

```markdown
#80 -> #95 generative invariant hardening

#83 + #87 evidence + #88 + #90
    -> #96 shared analyzed-document substrate

#83 + #84 + current M5 publication
    -> #97 rule catalog and per-source configuration

generative invariants + analyzed document + rule catalog + #87/#88 evidence
    -> #98 minimal token-pattern primitives

analyzed document + rule catalog
    -> #99 adapter-owned suppression fingerprint
```

Replace it with:

```markdown
#95 product-hardening evidence is an external prerequisite, not an M6 child.

#83 + #87 evidence + #88 + #90
    -> #96 shared analyzed-document substrate

#83 + #84 runtime product-safety evidence
    -> #97 rule catalog and per-source configuration

generative invariants + analyzed document + rule catalog + #87/#88 evidence
    -> #98 minimal token-pattern primitives

analyzed document + rule catalog
    -> #99 adapter-owned suppression fingerprint
```

Third #100 old anchor in `## Tracking checklist`:

```markdown
- [ ] #95 — Generative Unicode, offset, and correction invariant hardening.
- [ ] #96 — Shared request-scoped analyzed-document substrate.
- [ ] #97 — Rule catalog and exact per-source configuration.
- [ ] #98 — Minimal token-pattern primitives for deterministic Polish rules.
- [ ] #99 — Location-independent suggestion fingerprints for adapter-owned suppression.
```

Replace it with:

```markdown
External prerequisite:

- [ ] #95 — P1 runtime product-hardening evidence before broad M6 implementation.

M6 children:

- [ ] #96 — Shared request-scoped analyzed-document substrate.
- [ ] #97 — Rule catalog and exact per-source configuration.
- [ ] #98 — Minimal token-pattern primitives for deterministic Polish rules.
- [ ] #99 — Location-independent suggestion fingerprints for adapter-owned suppression.
```

Fourth #100 old anchor in `## Out of scope`:

```markdown
- Expanding the current M5 release claims or lowering any gate.
```

Replace it with:

```markdown
- Expanding superseded release claims, optional-research claims, or lowering any gate.
```

Fifth #100 old anchor in `## Dependencies`:

```markdown
None for tracking. Implementation order is controlled by the graph above. M6 is non-blocking for #93 and the current M5 publication.
```

Replace it with:

```markdown
None for tracking. Implementation order is controlled by the graph above. M6 is non-blocking for the runtime release path. #95 is an external product-hardening prerequisite, not an M6 child.
```

After writing the complete body files, fetch each edited issue again and remove
or reconcile every prohibited native `blockedBy` and `blocking` edge. The target
graph prohibits `blockedBy` edges #76 -> #84, #84 -> #43, #43 -> #90, and
#84 -> #90, and prohibits `blocking` edges #84 -> #43, #84 -> #64, and
#90 -> #64. If GitHub exposes a native edge but the available API cannot remove
it, stop before closing any issue or milestone and report the specific edge as
blocked rather than relying on body prose.

Write every complete updated body to a file and use `gh issue edit --body-file`.
Do not use inline bodies containing Markdown formatting.

- [ ] **Step 4: Move optional research issues**

Assign #76, #85, #86, #87, #88, #89, #90, and #119 to `Research — Optional Local Model Qualification`.

Append the exact standard section:

```markdown
## Runtime-first charter disposition (2026-08-01)

Classification: optional research under ADR-0020 and #120.

This issue preserves its research evidence and internal research dependencies.
Its outcome does not block a Polis runtime release and cannot qualify an
unverified model as supported product behavior.
```

For #76, additionally name #119 as the current independent requalification dependency. Retain `status:blocked` on #76 and #85–#90 only while their internal research dependencies remain unresolved. #119 remains unblocked.

For #90, replace the complete heading-delimited dependency section with the
exact #90 template from Step 3 before appending the standard research section.
Verify its body and native edge set retain only the internal optional-research
dependencies #76, #85, #86, #88, and #89.

- [ ] **Step 5: Close superseded issues accurately**

For #43, #64, #66, #92, and #93:

1. add `status:superseded`;
2. remove `status:blocked` if present;
3. remove the M5 milestone;
4. add an issue-specific comment beginning:

```markdown
Superseded by the runtime-first product charter adopted in ADR-0020 and tracked
through #120. The acceptance criteria were not completed.
```

The comment must state the surviving destination:

- #43: optional provider/ranker research survives in #88 and #89;
- #64: paragraph integration is outside the current Polis runtime product;
- #66: product verification is now owned by runtime release gates;
- #92: runtime publication no longer depends on the combined M5 artifact graph;
- #93: active sequencing is replaced by the product and optional research lanes.

Close each with:

```console
gh issue close ISSUE --repo PSyron/polis --reason "not planned"
```

- [ ] **Step 6: Close the historical M5 milestone**

Query M5 and require `open_issues == 0`. Then close milestone number 6 with the GitHub API. Do not close it if any unclassified open issue remains.

- [ ] **Step 7: Verify the complete live state**

Require:

- #84, #95, and #120 are open in `Runtime 0.x Hardening`;
- #84 has no `status:blocked` label and no #76 dependency in its body;
- #84 body contains `P0 product-safety work`;
- #84 body contains no #64 blocking claim and no final-release authorization
  blocker claim;
- #90 has only internal optional-research dependencies #76, #85, #86, #88, and
  #89 in body prose and native edges;
- #90 has no body or native dependency edge involving #43, #84, or #64;
- #95 body contains `P1 hardening after #84`;
- #95 body contains no legacy M5 non-publication wording;
- #95 body states that shared milestone membership and roadmap sequencing alone
  do not make #95 a blocker for the current runtime release and that a future
  accepted issue may explicitly make #95 a release blocker;
- #95 body contains no generic claim that #95 does not block a runtime release;
- #100 body contains no #93/current-M5 release-authority wording;
- #100 body contains no `current M5 publication` wording in any section;
- #120 body carries the #84 P0 / #95 P1 distinction and says #95 is not a
  current runtime-release blocker by shared milestone or roadmap sequencing
  alone;
- native `blockedBy` excludes #76 -> #84, #84 -> #43, #43 -> #90, and
  #84 -> #90;
- native `blocking` excludes #84 -> #43, #84 -> #64, and #90 -> #64;
- #76, #85–#90, and #119 are open in the research milestone;
- #43, #64, #66, #92, and #93 are closed with `status:superseded` and `stateReason == NOT_PLANNED`;
- #96–#100 remain open in M6;
- M5 is closed with zero open issues;
- every disposition comment links #120 and ADR-0020;
- no issue claims that a model is production-qualified.

If any assertion fails, repair only the mismatched target and rerun the complete inventory. Do not close #120 yet.

## Task 7: Close #120 and hand off the new product lane

**Files:**
- No tracked files modified.

**Interfaces:**
- Consumes: merged repository charter and verified live portfolio.
- Produces: completed #120 migration and a clear next product issue.

- [ ] **Step 1: Add the final #120 verification comment**

The comment must include:

- PR #121 as the artifact/CI boundary phase;
- the charter PR and merge commit;
- ADR-0020;
- product and research milestone links;
- exact issue dispositions;
- local and remote verification results;
- confirmation that no holdout was rerun and no model was qualified.

- [ ] **Step 2: Close #120 as completed**

```console
gh issue close 120 --repo PSyron/polis --reason completed
```

- [ ] **Step 3: Synchronize the local checkout**

Switch to local `main`, fast-forward from `origin/main`, and verify a clean worktree. Delete the local feature branch only after confirming its commit is contained in `main`.

- [ ] **Step 4: Final handoff**

Report:

- #120 acceptance and closure status;
- charter PR and merge commit;
- repository files changed;
- product/static/artifact/offline/research-collection results;
- milestone and issue mutations;
- known limitation that no model is production-qualified;
- next permitted action: plan and implement #84, with #95 following as product invariant hardening.

## Acceptance mapping

| Charter requirement | Plan task |
| --- | --- |
| Runtime complete without a model | Task 1 |
| Optional, review-only model policy | Tasks 1 and 2 |
| Product release independent from research | Task 2 |
| Historical evidence preserved | Tasks 2, 3, and 6 |
| Exact portfolio disposition | Tasks 3 and 6 |
| #84 independent from #76 implementation | Tasks 2, 3, and 6 |
| Product/research milestones | Task 6 |
| Superseded issues closed accurately | Task 6 |
| M5 retired with no open issues | Task 6 |
| #120 finite and closed last | Task 7 |
| No runtime behavior change | Tasks 1–5 verification |
| No consumed holdout rerun | Global constraints and Tasks 4, 6, and 7 |
