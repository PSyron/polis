# Conservative v1 Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the full pre-cleanup repository state, retire work that does not serve v1, and reduce the supported package to conservative Polish form correction with synchronized rules, documentation, tests, CI, and distribution metadata.

**Architecture:** The cleanup is a sequence of independently reviewed issues. A verified remote archive and a superseding ADR are hard gates. The active runtime composition root is narrowed once; orphaned LLM and LanguageTool implementations are then removed in parallel, while immutable evidence remains on `main` as a non-executable evidence shell and the full executable state remains on `feature/v2-research-archive`.

**Tech Stack:** Python 3.12–3.14, pytest, Ruff, mypy, Hatchling, GitHub Issues and pull requests, Git worktrees.

## Global Constraints

- The supported v1 categories are inflection, government, agreement, spelling, orthography, basic orthotypography, safe punctuation, and a small number of local deterministic syntax rules.
- Never correct tense/aspect compatibility, logic, facts, semantics, style, discourse, or any case that requires guessing intent.
- The safety invariant is: change form, never meaning; if uncertain, emit no suggestion.
- Keep all analyzed text offline. The default runtime must not require a model, Java, network access, research corpora, or consumed holdouts.
- Never rerun, regenerate, tune against, or rewrite accepted ADRs, release evidence, consumed holdouts, frozen reports, manifests, or historical Superpowers documents.
- Keep `polis.evaluation` import-compatible through the 0.x line until a dedicated compatibility decision supersedes ADR-0019.
- Preserve `SourceKind.LLM` for reading historical schema-v1 findings unless a separate serialization migration explicitly removes it.
- Do not edit directly on `main`. Every repository-changing child issue uses a branch beginning with `feature/` or `bug/`, followed by its concrete issue slug, plus one focused commit, one PR, independent review, and green CI.
- Every behavior removal starts with a failing boundary or artifact test and ends with updated maintained documentation.
- Every issue runs `ruff check .`, `ruff format --check .`, `mypy .`, and its relevant pytest set before commit.
- Paweł Cyroń remains the sole named author. Do not add co-author or automation attribution.

---

## File ownership map

Only one active task may own a row at a time.

| Unit | Exclusive files |
| --- | --- |
| Product decision | `PROMPT.md`, `docs/project/ROADMAP.md`, `docs/architecture/decisions/0022-conservative-v1-product-scope.md` |
| Evidence policy | `docs/project/documentation-migration-inventory.json`, `docs/project/DOCUMENTATION-ROADMAP.md`, `tests/test_documentation_migration_inventory.py` |
| Composition root | `src/polis/analyzer.py`, `src/polis/analysis/pipeline.py`, `src/polis/correction/policy.py`, public API snapshots and stubs |
| LLM removal | `src/polis/llm/**`, `src/polis/analysis/hybrid.py`, LLM protocol and unit tests |
| LanguageTool removal | `src/polis/rules/languagetool.py`, `src/polis/rules/languagetool_stdio.py`, `src/polis/rules/contextual_inflection.py`, their unit tests |
| Catalog removal | `src/polis/rules/catalog.py`, `tests/test_rule_catalog.py`, catalog exports |
| Research shell | `experiments/**`, research generator scripts, research-only tests |
| Vendor shell | `third_party/languagetool-pl/**`, vendor-only tests |
| V1 corpus | `tests/fixtures/v1/conservative_corrections.json`, `tests/test_v1_conservative_corpus.py` |
| CI and tooling | `.github/workflows/fast-ci.yml`, `pyproject.toml`, `scripts/validate_fast_ci_workflow.py`, `tests/test_fast_ci_workflow.py` |
| Maintained docs | `README.md`, `docs/*.md` except protected historical records, `examples/polis.toml` |
| Distribution | `pyproject.toml`, distribution verification scripts and tests |

## Execution graph

```text
#185 decision PR
  -> archive branch and manifest
      -> superseding ADR and evidence policy
          -> backlog retirement
          -> research runner cleanup ----+
          -> LanguageTool vendor cleanup -+-> CI/tooling convergence
          -> conservative v1 corpus ------+
          -> composition-root restriction
               -> LLM removal ------------+
               -> LanguageTool removal ---+-> catalog removal
                                            -> maintained docs
                                            -> distribution verification
                                            -> evaluation compatibility decision
```

With two instances, use only the pairings explicitly marked parallel below.

## Rollback policy

Each merged child remains independently revertible. If a deletion PR breaks a
supported v1 rule, public compatibility guarantee, evidence hash, offline
installation or package assertion, revert only that child PR and leave later
dependent tasks blocked. Do not copy files ad hoc from the archive branch into
`main`; restoration requires a reviewed revert or a focused recovery issue so
the archive SHA and evidence trail remain auditable.

---

### Task 1: Publish and merge the #185 product-direction decision

**Files:**

- Existing: `docs/superpowers/specs/2026-08-04-issue-185-conservative-v1-cleanup-design.md`
- Existing: `docs/superpowers/plans/2026-08-04-issue-185-conservative-v1-cleanup.md`

**Interfaces:**

- Consumes: maintainer approval recorded in #185 and this conversation.
- Produces: merged decision commit on `origin/main`; #185 closed only after its acceptance criteria and checks are verified.

- [ ] **Step 1: Verify the branch contains exactly the decision artifacts**

Run:

```bash
git status --short --branch
git diff origin/main...HEAD --stat
git log --oneline origin/main..HEAD
```

Expected: one commit for #185 and only the approved spec plus this implementation plan.

- [ ] **Step 2: Run the decision-document checks**

Run:

```bash
git diff --check origin/main...HEAD
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Expected: all checks pass; environment-dependent LanguageTool/model tests may only be skipped for their already-declared reasons.

- [ ] **Step 3: Push and open the #185 PR**

Push `feature/v1-scope-cleanup-design` and open a PR titled:

```text
docs: define conservative v1 cleanup strategy (#185)
```

The PR body must link #185, list the exact checks above, state that no code or backlog was changed, and request independent review.

- [ ] **Step 4: Merge only after independent review and green CI**

After merge, fetch `origin/main`, verify the merged SHA, verify every #185 acceptance criterion, and close #185. Do not create the archive from an unmerged feature branch.

---

### Task 2: Create and verify the complete v2 archive

**Files:**

- Create: `docs/project/v2-research-archive-manifest.md`
- Test: `tests/test_v2_research_archive_manifest.py`

**Interfaces:**

- Consumes: the exact `origin/main` SHA after Task 1.
- Produces: remote branch `feature/v2-research-archive`, a recorded baseline SHA, and an executable manifest check used as a hard gate by every deletion issue.

- [ ] **Step 1: Create a dedicated GitHub issue**

Title:

```text
Create and verify the complete v2 research archive
```

Assign `type:chore`, `area:packaging`, `priority:P0`, milestone `Runtime 0.x Hardening`. Acceptance criteria: exact baseline SHA, remote ref equality, presence checks for `experiments/`, `third_party/languagetool-pl/`, `src/polis/llm/`, `src/polis/evaluation/`, frozen reports, holdout markers, manifests and accepted ADRs; no deletions.

- [ ] **Step 2: Write the failing manifest test**

The test must parse these literal fields from the manifest:

```text
repository: PSyron/polis
branch: feature/v2-research-archive
baseline_sha: a literal 40-character lowercase hexadecimal commit SHA
```

It must reject a missing or symbolic SHA and require a checklist containing `experiments/`, `data/`, `third_party/languagetool-pl/`, `src/polis/llm/`, `src/polis/evaluation/`, `docs/architecture/decisions/`, `docs/release-notes/` and `docs/superpowers/`. Run the single test and confirm failure because the manifest does not exist.

- [ ] **Step 3: Create and verify the remote archive ref**

From a clean, fetched checkout:

```bash
git fetch origin --prune
git rev-parse origin/main
git branch feature/v2-research-archive origin/main
git push origin feature/v2-research-archive:feature/v2-research-archive
git ls-remote --heads origin feature/v2-research-archive
```

The local baseline SHA and remote SHA must be identical. Record that immutable SHA in the manifest.

- [ ] **Step 4: Fill the manifest with exact presence evidence**

Record the baseline SHA and the result of `git ls-tree -r --name-only` checks for:

- `experiments/`;
- `data/`;
- `third_party/languagetool-pl/`;
- `src/polis/llm/`;
- `src/polis/evaluation/`;
- `docs/architecture/decisions/`;
- `docs/release-notes/`;
- `docs/superpowers/`;
- every `holdout.started`, `frozen_*.json`, `report.json`, `results.json`, and `manifest.json` path.

- [ ] **Step 5: Run checks, commit, PR, and verify**

Run the new manifest test and the global quality commands. Commit on `feature/v2-research-archive-manifest` with the created issue number. Merge only after review. Every later deletion issue must name this archive issue as a dependency.

---

### Task 3: Adopt the superseding v1 scope and evidence-retention ADR

**Files:**

- Create: `docs/architecture/decisions/0022-conservative-v1-product-scope.md`
- Modify: `PROMPT.md`
- Modify: `docs/project/ROADMAP.md`
- Modify: `docs/project/DOCUMENTATION-ROADMAP.md`
- Modify: `docs/project/documentation-migration-inventory.json`
- Modify: `docs/architecture/README.md`
- Test: `tests/test_architecture_policy.py`
- Test: `tests/test_documentation_migration_inventory.py`

**Interfaces:**

- Consumes: the verified remote archive from Task 2 and the invariant from #185.
- Produces: authoritative permission to remove executable research/vendor material while retaining an evidence shell; supersedes conflicting product intent without editing ADR-0004 through ADR-0021.

- [ ] **Step 1: Create the decision issue with exact scope**

The issue must require the ADR to decide all of the following:

- v1 only corrects unambiguous local form;
- LLM, full LanguageTool/Java, contextual semantic inference and M6 catalog expansion are not supported v1 runtime;
- `SourceKind.LLM` and the public exception hierarchy remain for historical schema compatibility;
- public suggestion-outcome and analyzer lifecycle members are either retained through 0.x or removed only with explicit 1.0 migration notes;
- unused runtime protocols `LocalGenerationBackend`, `LocalFindingBackend` and `MonotonicClock` are removed after the composition root no longer consumes them;
- the evidence shell stays on `main` while executable research and vendor material may be removed after archive verification;
- ADR-0019 continues to protect `polis.evaluation` during 0.x;
- ADR-0021 remains historical but its planned catalog implementation is superseded.

- [ ] **Step 2: Write failing policy tests**

Add assertions that:

- ADR-0022 exists, is indexed, names #185 and links the archive manifest;
- `PROMPT.md` explicitly excludes meaning-changing and tense/aspect correction;
- the documentation inventory distinguishes protected evidence files from removable executable prefixes instead of protecting every file under `experiments/` and `third_party/` indiscriminately;
- protected ADRs, releases, reports, holdout markers, manifests and Superpowers history keep their existing protected dispositions.

Run only the two policy test modules and confirm the new assertions fail.

- [ ] **Step 3: Write ADR-0022 and update the living sources of truth**

Use Polish prose. State which earlier decisions remain historical, which behavior is superseded, the compatibility boundary, exact evidence-shell rule, archive SHA source, and rollback rule. Update `PROMPT.md` and the active roadmap; do not rewrite historical roadmap tables.

- [ ] **Step 4: Replace broad inventory protection with ordered exact rules**

Keep inventory schema version 1 and enumerate every retained evidence file in exact `paths` entries; do not introduce wildcard semantics. Generate the candidate list with `git ls-files`, review every entry, then store the resolved paths. Required protected filename classes are:

```text
README.md
config.json
report.json
results.json
assembly.json
cases.json
frozen_*.json
holdout.started
evaluated_source.json
pre_evaluation_inputs.patch
LICENSE-LGPL-2.1.txt
NOTICE
UPSTREAM.md
BENCHMARK.md
manifest.json
patches/0001-reproducible-build-metadata.patch
```

The validator and tests must reject a protected artifact that falls through to a removable classification.

- [ ] **Step 5: Verify, commit, and merge**

Run policy tests, documentation link checks and all global quality commands. Use one decision commit and PR. This task blocks every code deletion.

---

### Task 4: Retire the out-of-scope GitHub backlog and create one v2 tracker

**Files:** None; GitHub metadata only.

**Interfaces:**

- Consumes: merged #185, verified archive branch, and merged ADR-0022.
- Produces: one non-blocking v2 tracker and truthful closure of the two obsolete issue trees.

**Parallel:** May run as Instance 1 while Instance 2 starts Task 5 after Task 3.

- [ ] **Step 1: Create one v2 tracker**

Title:

```text
Track post-v1 research into contextual and model-assisted correction
```

Use `type:research`, `area:evaluation`, `priority:P2`, milestone `Research — Optional Local Model Qualification`. Its body must state that it never blocks v1, does not authorize rerunning consumed holdouts, and links #76, #85–#90, #96–#100, #151–#155, #180 and #183 as historical candidates rather than an active dependency graph.

- [ ] **Step 2: Close research issues truthfully**

Close #76, #85, #86, #87, #88, #89, #90, #180 and #183 with reason `not planned`. Each comment must say the acceptance criteria were not completed, cite #185 and ADR-0022, link `feature/v2-research-archive`, and link the new v2 tracker.

- [ ] **Step 3: Close M6 and catalog issues truthfully**

Close #96, #97, #98, #99, #100, #151, #152, #153, #154 and #155 with the same structure. Do not describe #150 as reverted until the catalog-removal PR actually merges.

- [ ] **Step 4: Verify live GitHub state**

Query all listed issues and assert they are closed, have the intended closure reason and comment links, and that only the single v2 tracker remains open from these trees. Save no generated GitHub dump in the repository.

---

### Task 5: Remove executable research runners while retaining evidence

**Files:**

- Delete: executable `*.py` files under `experiments/`
- Delete: `scripts/generate_safety_corpus_candidates.py`
- Delete: `scripts/generate_safety_corpus_v2_candidates.py`
- Delete: `scripts/run_sentence_safety_case.py`
- Delete: `tests/test_contextual_inflection_routing.py`
- Delete: `tests/test_contextual_inflection_rule_research.py`
- Delete: `tests/test_correction_corpus_v3.py`
- Delete: `tests/test_inflection_candidate_benchmark.py`
- Delete: `tests/test_languagetool_benchmark.py`
- Delete: `tests/test_languagetool_corpus_quality.py`
- Delete: `tests/test_languagetool_rule_inventory.py`
- Delete: `tests/test_languagetool_stdio_benchmark.py`
- Delete: `tests/test_llm_benchmark.py`
- Delete: `tests/test_nlp_dependency_evaluation.py`
- Delete: `tests/test_performance_baseline.py`
- Delete: `tests/test_qlora_benchmark.py`
- Delete: `tests/test_quality_baseline.py`
- Delete: `tests/test_real_llm_benchmark.py`
- Delete: `tests/test_residual_syntax_evaluation.py`
- Delete: `tests/test_role_prompt_benchmark.py`
- Delete: `tests/test_role_prompt_experiment.py`
- Delete: `tests/test_safety_corpus.py`
- Delete: `tests/test_safety_corpus_v2.py`
- Delete: `tests/test_sentence_category_routing.py`
- Delete: `tests/test_sentence_safety_gate.py`
- Delete: `tests/test_sentence_safety_gate_v2.py`
- Delete: `tests/test_sentence_safety_installation.py`
- Delete: `tests/test_sentence_safety_runner.py`
- Delete: `tests/test_sentence_syntax_qualification.py`
- Delete: `tests/test_two_pass_qwen35_benchmark.py`
- Preserve byte-for-byte: experiment README/config/report/result/frozen/marker/manifest evidence
- Test: add or extend a product-collection guard for the evidence shell

**Interfaces:**

- Consumes: archive manifest and ADR-0022 classifications.
- Produces: non-executable experiment evidence on `main`; no importable or runnable research pipeline.

**Parallel:** Run as Instance 1 while Instance 2 performs Task 6. Neither may edit `pyproject.toml`, CI, maintained product docs or distribution tests.

- [ ] **Step 1: Create the focused research-cleanup issue**

Attach the exact `git ls-files 'experiments/**/*.py'` and matching test inventory. State every preserved evidence filename and archive dependency. Exclude runtime LLM/LanguageTool modules.

- [ ] **Step 2: Write the failing boundary test**

The test must fail while any tracked `experiments/**/*.py` remains. The evidence shell is data and prose, not an importable Python package, so remove experiment `__init__.py` files too. The test must also hash the protected evidence files before deletion and compare them after deletion.

- [ ] **Step 3: Remove runners and their direct tests**

Generate the reviewed path list with `git ls-files 'experiments/**/*.py'`, inspect it, and pass those exact paths after `--` to `git rm`. Do not use a broad recursive deletion command. Remove exactly the research tests named in this task; do not remove runtime or immutable-evidence guard tests.

- [ ] **Step 4: Prove evidence preservation and absence of imports**

Run the boundary test, `rg` for imports from `experiments`, and tests for documentation inventory and product collection. The recorded hashes for preserved evidence must be unchanged.

- [ ] **Step 5: Run global checks and merge one cleanup commit**

Do not edit tool configuration yet; temporary stale Ruff/mypy paths are resolved only in Task 12 after both research and vendor cleanup land.

---

### Task 6: Remove executable vendored LanguageTool while retaining provenance

**Files:**

- Delete: `third_party/languagetool-pl/sources/**`
- Delete: `third_party/languagetool-pl/pom.xml`
- Delete: `third_party/languagetool-pl/scripts/benchmark.py`
- Delete: `third_party/languagetool-pl/scripts/benchmark.sh`
- Delete: `third_party/languagetool-pl/scripts/bootstrap.sh`
- Delete: `third_party/languagetool-pl/scripts/build.sh`
- Delete: `third_party/languagetool-pl/scripts/run_stdio.sh`
- Delete: `third_party/languagetool-pl/scripts/verify.sh`
- Delete: `tests/test_languagetool_vendor_artifacts.py`
- Delete: `tests/test_languagetool_vendor_runtime.py`
- Delete: `tests/test_languagetool_vendor_benchmark.py`
- Preserve: vendor license, notice, README, UPSTREAM, BENCHMARK, manifest and patch

**Interfaces:**

- Consumes: archive manifest and ADR-0022.
- Produces: auditable LanguageTool provenance without bundled Java source or executable build/runtime scripts.

**Parallel:** Run as Instance 2 while Instance 1 performs Task 5.

- [ ] **Step 1: Write failing vendor-shell tests**

Assert that the seven preserved provenance files and patch exist and that `sources/`, top-level `pom.xml`, and executable scripts do not. Record and compare SHA-256 for every preserved file.

- [ ] **Step 2: Remove only the reviewed executable/vendor paths**

Use explicit `git rm --` targets. Do not remove the containing `third_party/languagetool-pl` directory.

- [ ] **Step 3: Verify provenance and removal**

Run the new shell test, documentation-inventory tests, license tests and `rg` for references to removed build scripts. The preserved file hashes must match the pre-removal values.

- [ ] **Step 4: Run global checks and merge one cleanup commit**

Keep runtime LanguageTool code unchanged; Task 9 owns that surface.

---

### Task 7: Restrict the public composition root to conservative v1

**Files:**

- Modify: `src/polis/analyzer.py`
- Modify: `src/polis/analysis/pipeline.py`
- Modify: `src/polis/correction/policy.py`
- Modify: `src/polis/__init__.py`
- Modify: `examples/polis.toml`
- Modify: `tests/fixtures/public_api_snapshot.json`
- Modify: `tests/typecheck/stubs/polis/__init__.pyi`
- Modify: `tests/test_api_compatibility.py`
- Modify: `tests/test_analysis_pipeline.py`
- Modify: `tests/test_conservative_correction.py`
- Modify: `tests/test_automatic_correction_policy.py`
- Modify: `tests/test_offline_verification.py`

**Interfaces:**

- Consumes: ADR-0022 compatibility decisions.
- Produces: `Analyzer` and `AnalyzerConfig` that compose only the ten deterministic built-in rules; legacy out-of-scope TOML sections fail with `ConfigurationError`.

**Exclusive:** No second instance may edit `src/polis/analyzer.py` during this task.

- [ ] **Step 1: Write failing configuration-boundary tests**

Parameterize `backend`, `language_tool`, `contextual_inflection` and `vendored_language_tool` TOML sections. Each must raise `ConfigurationError` containing the section name and the phrase `is not supported in Polis v1`. Add a test that `AnalyzerConfig()` uses no external transport or executable.

- [ ] **Step 2: Write the semantic-abstention regression**

Analyze:

```python
"Gdy wrócisz, zadzwoń do mnie wczoraj."
```

Assert `analysis.issues == ()` and unchanged corrected text. Run the focused test and verify the current runtime fails only if an out-of-scope route emits a finding.

- [ ] **Step 3: Remove optional composition paths**

Remove analyzer imports, config fields, TOML parsing, injected transports, owned stdio session, LLM/hybrid construction and LanguageTool policy entry. `_make_default_registry()` must return exactly the ten built-in deterministic registrations in their existing order.

Retain historical-schema types required by ADR-0022. If lifecycle members remain for 0.x compatibility, make them no-op and document that they own no process.

- [ ] **Step 4: Update public snapshots, stubs and example config**

Remove only members explicitly authorized by ADR-0022. The example TOML must contain no model, Java or LanguageTool section.

- [ ] **Step 5: Run focused and global checks, then merge**

Run API compatibility, pipeline, conservative-correction, policy, offline and installation tests before the full suite. This task is the gate for Tasks 8 and 9.

---

### Task 8: Remove orphaned LLM and hybrid implementation

**Files:**

- Delete: `src/polis/analysis/hybrid.py`
- Delete: `src/polis/llm/__init__.py`
- Delete: `src/polis/llm/adapter.py`
- Delete: `src/polis/llm/contracts.py`
- Delete: `src/polis/llm/corrected_text.py`
- Delete: `src/polis/evaluation/finetuning_dataset.py`
- Delete: `scripts/generate_finetuning_dataset.py`
- Modify: `src/polis/core/protocols.py`
- Modify: `src/polis/core/__init__.py`
- Delete: `tests/test_llm_adapter.py`
- Delete: `tests/test_llm_contract.py`
- Delete: `tests/test_corrected_text_contract.py`
- Delete: `tests/test_two_pass_prompt_contract.py`
- Delete: `tests/test_hybrid_suggestion_engine.py`
- Delete: `tests/test_suggestion_outcomes.py`
- Delete: `tests/test_finetuning_dataset.py`
- Modify: `tests/test_protocols.py`
- Modify: `tests/typecheck/protocol_examples.py`

**Interfaces:**

- Consumes: Task 7 with no runtime LLM consumer and ADR-0019 preservation of the remaining `polis.evaluation` namespace.
- Produces: no importable `polis.llm`, no hybrid engine and no finetuning generator in the supported source tree.

**Parallel:** May run as Instance 1 while Instance 2 performs Task 9.

- [ ] **Step 1: Add failing package-absence assertions**

Extend package/source boundary tests to reject `polis/llm/`, `polis/analysis/hybrid.py` and `polis/evaluation/finetuning_dataset.py`, while still importing `polis.evaluation.load_dataset` and `validate_dataset`.

- [ ] **Step 2: Remove orphaned implementation and research bridge**

Delete the listed modules and implementation tests. ADR-0022 retains historical serialized types but explicitly removes the unused runtime protocols `LocalGenerationBackend`, `LocalFindingBackend` and `MonotonicClock`; remove their exports, examples and tests after `rg` confirms Task 7 left no runtime consumer.

- [ ] **Step 3: Prove no dangling imports**

Run:

```bash
rg -n 'polis\.llm|analysis\.hybrid|finetuning_dataset|LocalGenerationBackend|LocalFindingBackend' src tests scripts docs --glob '!docs/architecture/decisions/**' --glob '!docs/superpowers/**'
```

Every remaining match must be an intentional maintained migration note or protected historical evidence.

- [ ] **Step 4: Run protocol, evaluation-compatibility, package-boundary and global checks; merge one commit**

---

### Task 9: Remove orphaned LanguageTool and contextual-inflection runtime

**Files:**

- Delete: `src/polis/rules/languagetool.py`
- Delete: `src/polis/rules/languagetool_stdio.py`
- Delete: `src/polis/rules/contextual_inflection.py`
- Delete: `tests/test_languagetool_rule.py`
- Delete: `tests/test_languagetool_stdio_session.py`
- Delete: `tests/test_contextual_inflection_rule.py`
- Delete: `tests/test_languagetool_stdio_documentation.py`
- Delete: `tests/fixtures/fake_languagetool_stdio.py`
- Modify: `src/polis/rules/__init__.py`

**Interfaces:**

- Consumes: Task 7 with no runtime registration or transport consumer.
- Produces: no Java, HTTP, stdio or contextual-inflection runtime path; ten built-in rules remain unchanged.

**Parallel:** May run as Instance 2 while Instance 1 performs Task 8.

- [ ] **Step 1: Add failing source-boundary assertions**

Reject all three source modules and the fake stdio fixture. Assert that the built-in agreement, spelling and syntax modules still import and their existing focused tests still pass.

- [ ] **Step 2: Delete orphaned modules and exports**

Do not recreate LanguageTool comma behavior. Any later in-process punctuation rule needs its own rule issue and evidence.

- [ ] **Step 3: Prove absence and preserved built-ins**

Run `rg` for removed module names outside protected history, then run agreement, spelling, syntax, residual-syntax, registry, conflict and correction-property tests.

- [ ] **Step 4: Run global checks and merge one commit**

Task 10 starts only after this PR because both tasks edit `src/polis/rules/__init__.py`.

---

### Task 10: Remove the unused #150 catalog implementation

**Files:**

- Delete: `src/polis/rules/catalog.py`
- Delete: `tests/test_rule_catalog.py`
- Delete: `tests/test_rule_catalog_inventory.py`
- Modify: `src/polis/rules/__init__.py`
- Preserve: `docs/architecture/decisions/0021-rule-catalog-ownership.md`
- Preserve: `docs/architecture/rule-catalog-inventory.md`
- Preserve: `docs/architecture/rule-catalog-inventory.json`

**Interfaces:**

- Consumes: ADR-0022 supersession and Task 9 exports.
- Produces: no unused catalog runtime abstraction; unchanged historical #148/#149 evidence.

- [ ] **Step 1: Write the failing absence and evidence test**

Assert that `polis.rules.catalog` is absent from the package/source manifest and that the three preserved evidence files retain their pre-task SHA-256 values.

- [ ] **Step 2: Delete implementation, current-invariant tests and exports**

Do not edit the accepted ADR or frozen inventory contents. The removal PR explains that #150 was completed historically but its implementation is no longer used by v1.

- [ ] **Step 3: Run rule, architecture, evidence and global checks; merge one commit**

---

### Task 11: Build the manually reviewed conservative v1 regression corpus

**Files:**

- Create: `tests/fixtures/v1/conservative_corrections.json`
- Create: `tests/test_v1_conservative_corpus.py`
- Modify: `tests/test_e2e_polish_corrections.py`
- Preserve unchanged: frozen evaluation and safety corpora under `tests/fixtures/evaluation/`

**Interfaces:**

- Consumes: the final ten built-in rules after Tasks 7–10.
- Produces: editable, non-frozen v1 fixture proving supported corrections and abstention without semantic rewriting.

**Parallel:** Case review may start after ADR-0022 while runtime work proceeds, but the final assertions land only after Tasks 7–10.

- [ ] **Step 1: Define and test the fixture schema**

Each case contains:

```json
{
  "id": "v1-001",
  "kind": "error",
  "category": "agreement",
  "input": "Te zdanie jest krótkie.",
  "expected_issues": [
    {"start": 0, "end": 2, "replacement": "To", "source": "rule:agreement"}
  ]
}
```

Allowed `kind` values are `error`, `correct`, and `abstain`. `abstain` requires `expected_issues: []` and a human-written `reason` naming semantic, tense/aspect, intent, style or insufficient-local-evidence ambiguity.

- [ ] **Step 2: Add manually reviewed coverage for every active rule**

For each active rule add one true error, one close correct negative, exact half-open offsets and minimal replacement. Add conflict/application cases where rules can overlap.

- [ ] **Step 3: Add mandatory abstention cases**

Include exactly the sentence:

```text
Gdy wrócisz, zadzwoń do mnie wczoraj.
```

Also include a correct marked word order and at least one sentence where two grammatical rewrites would express different intents. None may emit a suggestion.

- [ ] **Step 4: Remove obsolete active E2E promises**

Stop treating `llm_planned`, whole-clause `żeby...` rewrites, word-order rewrites, style and tense cases as supported positives. Do not edit frozen corpora; disconnect them from the active v1 gate instead.

- [ ] **Step 5: Run corpus schema, rule, correction and full quality checks; merge one commit**

The PR must include a documented human review of every v1 case. Mechanically paired templates cannot support a false-alarm claim.

---

### Task 12: Simplify CI and tool configuration after research removal

**Files:**

- Modify: `.github/workflows/fast-ci.yml`
- Modify: `pyproject.toml`
- Modify: `scripts/validate_fast_ci_workflow.py`
- Modify: `tests/test_fast_ci_workflow.py`

**Interfaces:**

- Consumes: merged Tasks 5 and 6.
- Produces: CI and static-analysis inputs that reference only existing runtime and test paths.

- [ ] **Step 1: Add failing workflow/tooling assertions**

Assert that Ruff and mypy contain no `experiments/` path, that CI invokes the remaining suite, and that obsolete `research`/`model` markers are absent only if `pytest --collect-only` confirms no remaining marked tests.

- [ ] **Step 2: Remove stale paths and filters**

Keep the supported Python matrix, offline dependency behavior and all runtime quality jobs. Do not edit distribution allowlists in this task.

- [ ] **Step 3: Run the workflow validator, collection check and global quality commands; merge one commit**

---

### Task 13: Synchronize all maintained v1 documentation and examples

**Files:**

- Modify: `README.md`
- Modify: `docs/project/RISKS.md`
- Modify: `docs/architecture/protocols.md`
- Modify: `docs/compatibility.md`
- Modify: `docs/customization.md`
- Modify: `docs/development/dependency-licenses.md`
- Modify: `docs/distribution-verification.md`
- Modify: `docs/limitations.md`
- Modify: `docs/offline-operation.md`
- Modify: `docs/prerelease-candidate.md`
- Modify: `docs/privacy-audit.md`
- Modify: `docs/public-api.md`
- Modify: `docs/quick-start.md`
- Modify: `docs/rules.md`
- Modify: `examples/polis.toml`
- Remove: `docs/llm-corrected-text-contract.md`
- Remove: `docs/llm-prompt-response-contract.md`
- Remove: `docs/llm-quality-gates.md`
- Remove: `docs/development/research-workflow.md`
- Remove: `docs/architecture/contextual-inflection-routing-design.md`
- Remove: `docs/architecture/finetuning-dataset.md`
- Remove: `docs/architecture/languagetool-rule-inventory-design.md`
- Remove: `docs/architecture/sentence-category-routing-design.md`
- Remove: `docs/evaluation-corpus-v3-review-checklist.md`
- Remove: `docs/evaluation-safety-corpus-v1-review-checklist.md`
- Remove: `docs/evaluation-safety-corpus-v2-review-checklist.md`
- Modify: `docs/evaluation-dataset.md` to describe only ADR-0019 compatibility and link the archive

**Interfaces:**

- Consumes: final runtime and corpus behavior from Tasks 7–11.
- Produces: Polish-first maintained documentation that promises only behavior present in v1.

**Exclusive:** One owner for all maintained documents. Do not parallelize this task.

- [ ] **Step 1: Add failing orphan-reference tests**

Search maintained documents, README and examples for active instructions referencing LLM, model servers, LanguageTool, Java, contextual inflection, research runners, removed config sections and catalog inspection. Protected ADRs, release notes and Superpowers history are excluded from this negative scan.

- [ ] **Step 2: Rewrite maintained documentation around the v1 invariant**

Every entry point must describe supported categories, explicit non-goals, abstention, offline defaults, no meaning changes and the archive location. Rule docs list exactly the active sources. Public API docs match snapshots and compatibility decisions.

- [ ] **Step 3: Replace active research guides with one archive pointer**

Do not delete or rewrite protected historical records. Remove maintained guides only after checking incoming links and replacing them with one Polish archive/navigation page if needed.

- [ ] **Step 4: Run link, documentation-inventory, API-snapshot and global checks; merge one commit**

---

### Task 14: Tighten package contents and distribution verification

**Files:**

- Modify: `pyproject.toml`
- Modify: `scripts/verify_distribution_artifacts.py`
- Modify: `scripts/verify_distribution_install.py`
- Modify: `tests/test_distribution_artifacts.py`
- Modify: `tests/test_release_distribution_installation.py`
- Modify: `tests/test_package_smoke.py`
- Modify: `tests/test_offline_verification.py`
- Modify: `tests/test_prerelease_candidate.py`

**Interfaces:**

- Consumes: Tasks 8–13.
- Produces: wheel and sdist containing only approved v1 product and protected maintained records.

**Exclusive:** One owner for `pyproject.toml` and all artifact tests.

- [ ] **Step 1: Add failing negative artifact assertions**

Reject these paths from built artifacts:

```text
polis/llm/
polis/analysis/hybrid.py
polis/rules/languagetool.py
polis/rules/languagetool_stdio.py
polis/rules/contextual_inflection.py
polis/rules/catalog.py
polis/evaluation/finetuning_dataset.py
experiments/
third_party/
docs/llm-corrected-text-contract.md
docs/llm-prompt-response-contract.md
docs/llm-quality-gates.md
```

Continue to require importability of `polis.evaluation.load_dataset` and `validate_dataset` during 0.x.

- [ ] **Step 2: Narrow sdist and wheel configuration**

Remove obsolete LLM documents from the sdist allowlist. Ensure source deletion, not an ignore-only rule, accounts for removed runtime modules. Keep release notes and accepted ADRs required by existing release policy.

- [ ] **Step 3: Build and inspect both artifacts**

Run:

```bash
uv build
uv run python scripts/verify_distribution_artifacts.py dist/*.whl dist/*.tar.gz
```

Install the wheel in an isolated offline environment and run default `AnalyzerConfig()` smoke analysis without model, Java or network.

- [ ] **Step 4: Run all distribution, offline, prerelease and global checks; merge one commit**

---

### Task 15: Decide `polis.evaluation` disposition before semantic version 1.0

**Files:**

- Create: `docs/architecture/decisions/0023-v1-evaluation-namespace.md`
- Inventory only: `src/polis/evaluation/**`
- Modify: `docs/evaluation-dataset.md`
- Modify: `docs/compatibility.md`
- Modify: evaluation import and distribution tests

**Interfaces:**

- Consumes: ADR-0019 and final v1 package inventory.
- Produces: explicit 1.0 compatibility decision and a separate implementation issue if the accepted decision changes code; no accidental namespace removal in this planning task.

- [ ] **Step 1: Inventory every supported evaluation import**

Record all imports exercised by documentation, public snapshots, package smoke tests and external examples. Separately identify `style_repeated_intensifier` in `src/polis/evaluation/datasets/v1/cases.json` as legacy, not as a supported v1 correction promise.

- [ ] **Step 2: Choose one explicit ADR outcome**

The ADR must choose exactly one:

- retain the lightweight namespace in 1.0;
- deprecate it with a named removal version and migration path;
- remove it at 1.0 with release notes and exact replacement guidance.

Do not infer this decision from cleanup convenience.

- [ ] **Step 3: Record the implementation consequences without changing runtime code**

The ADR and its follow-up issue must distinguish import compatibility from whether legacy datasets define the active v1 quality gate. The follow-up issue must name the exact modules, tests, migration notes and release version affected by the accepted outcome.

- [ ] **Step 4: Run documentation, architecture-policy and global checks; merge one decision commit**

---

## Final verification and handoff

- [ ] Confirm all child issues and PRs are linked from the #185 decision record.
- [ ] Confirm the archive remote SHA still resolves and protected evidence hashes match their manifests.
- [ ] Confirm the obsolete issue trees are closed and only one v2 tracker remains open.
- [ ] Run `ruff check .`, `ruff format --check .`, `mypy .`, full `pytest`, wheel/sdist build, artifact inspection and offline wheel smoke test.
- [ ] Compare the active rule registry, public API snapshot, example config, README, rule docs, package contents and v1 corpus; all must express the same supported boundary.
- [ ] Confirm `Gdy wrócisz, zadzwoń do mnie wczoraj.` produces no finding and no correction.
- [ ] Report issue numbers, acceptance state, changed files, commands/results, known limitations and the next allowed release action.

## Two-instance schedule

Use this order to avoid shared-file conflicts:

| Wave | Instance 1 | Instance 2 |
| --- | --- | --- |
| 0 | Task 1 | Independent review only |
| 1 | Task 2 | Wait; archive is a hard gate |
| 2 | Task 3 | Task 4 after archive verification |
| 3 | Task 5 | Task 6 |
| 4 | Task 7 | Prepare Task 11 case review without editing runtime files |
| 5 | Task 8 | Task 9 |
| 6 | Task 10 | Finish Task 11 |
| 7 | Task 12 | Independent review of Tasks 10–11 |
| 8 | Task 13 | Independent documentation/runtime consistency review |
| 9 | Task 14 | Independent artifact inspection |
| 10 | Task 15 | Independent compatibility review |
