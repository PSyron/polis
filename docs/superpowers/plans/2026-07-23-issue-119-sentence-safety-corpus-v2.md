# Issue #119 Sentence Safety Corpus v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver and freeze an independent 240-case sentence safety corpus v2 without scoring a holdout or changing analyzer behavior.

**Architecture:** Parameterize the existing safety-corpus validator with an immutable corpus policy while preserving v1 defaults. Keep v2 linguistic specifications in a separate generator, validate them mechanically against all reserved assets, and bind the frozen result to a separate owner-approval manifest.

**Tech Stack:** Python 3.12+, standard-library JSON/XML/hashlib/dataclasses, pytest, Ruff, mypy, uv, Hatchling.

## Global Constraints

- Work only on GitHub issue #119 and produce one focused commit referencing `#119`.
- Treat issue #119 as the authoritative specification.
- Preserve offline-only privacy and do not change analyzer, rule, source-policy, evaluator, or quality-threshold behavior.
- Do not open, score, rerun, or tune against corpus-v3 or safety-corpus-v1 holdouts.
- Keep all v1 corpora, approval data, markers, reports, results, and digests byte-for-byte unchanged.
- Use project-authored CC0-1.0 Polish and half-open Unicode offsets `[start, end)`.
- Under the accepted issue #119 clarification, only the `Polis architecture owner` role may record `human-reviewed`; the role record is not personal attribution.
- Produce no development or holdout quality score.

---

### Task 1: Route shared validation through immutable corpus policies

**Files:**
- Modify: `src/polis/evaluation/safety_corpus.py`
- Modify: `src/polis/evaluation/__init__.py`
- Create: `tests/test_safety_corpus_v2.py`

**Interfaces:**
- Consumes: existing v1 validator behavior and schema-v3 correction-corpus primitives.
- Produces: `SAFETY_CORPUS_V2_ID`, `SAFETY_REVIEW_CHECKLIST_V2_VERSION`, v2-aware `validate_safety_corpus()`, `select_safety_cases_for_purpose()`, and `safety_entity_catalog_ids(corpus_id=...)`.

- [x] Write tests that import the v2 constants, mutate a minimal v1 raw corpus to the v2 identity/policy, and expect v2 policy selection while preserving v1 validation.
- [x] Run `uv run --locked --extra dev pytest tests/test_safety_corpus_v2.py -q` and confirm RED because the v2 constants and policy do not exist.
- [x] Add a frozen `_SafetyCorpusPolicy` with corpus ID, checklist version, controlled surfaces, and overrides; choose it only from a closed ID map.
- [x] Pass the selected policy into review, entity-span, entity-ID, and isolation validation without changing v1 defaults or public return types.
- [x] Add purpose-selection and unknown-ID tests, then run both `tests/test_safety_corpus.py` and `tests/test_safety_corpus_v2.py` to GREEN.

### Task 2: Author deterministic v2 candidates

**Files:**
- Create: `scripts/generate_safety_corpus_v2_candidates.py`
- Create: `tests/fixtures/evaluation/polish_correction_safety_corpus_v2.json`
- Create: `tests/fixtures/evaluation/polish_correction_safety_corpus_v2.xml`
- Modify: `tests/test_safety_corpus_v2.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Consumes: explicit v2-only `CaseSpec` values and shared safety-corpus validation.
- Produces: `build_candidate_corpus() -> dict[str, Any]`, deterministic pending JSON/XML, and exactly 60 cases per stratum.

- [x] Add a fixture test requiring corpus ID `polis_polish_correction_safety_corpus_v2`, 240 cases, four 60-case strata, and 20/40 development/holdout balance; verify RED because fixtures are absent.
- [x] Author 60 objective minimal corrections for each positive stratum and 60 unchanged protected negatives without copying v1 linguistic content.
- [x] Derive edits, offsets, templates, entity spans, case IDs, provenance, and pending review metadata mechanically.
- [x] Generate candidate JSON/XML, validate semantic equivalence, and add explicit sdist exclusions for both v2 representations.
- [x] Run the focused balance, offset, reconstruction, provenance, XML, and package-exclusion tests to GREEN.

### Task 3: Prove isolation and retained-evidence immutability

**Files:**
- Modify: `scripts/generate_safety_corpus_v2_candidates.py`
- Modify: `tests/test_safety_corpus_v2.py`

**Interfaces:**
- Consumes: corpus v3, safety corpus v1, fine-tuning records, prompt examples, E2E fixtures, and pinned evidence paths.
- Produces: `validate_reserved_asset_isolation(raw)` and deterministic SHA-256 immutability assertions.

- [x] Add adversarial tests for normalized input, template, entity combination, canonical entity identifier, and near-family collisions; verify RED for v1 comparison and v2 catalog routing.
- [x] Convert reserved assets to `IsolationRecord` values and validate them without exposing gold data to runtime policy.
- [x] Assert v2 catalog IDs are disjoint from v1 and corpus-v3 IDs.
- [x] Pin and assert SHA-256 values for v1 JSON/XML/approval and #115 frozen configuration, marker, report, and evaluated-source evidence.
- [x] Run all isolation and immutability tests to GREEN.

### Task 4: Document the candidate review boundary

**Files:**
- Create: `docs/evaluation-safety-corpus-v2-review-checklist.md`
- Modify: `docs/evaluation-dataset.md`
- Modify: `docs/llm-quality-gates.md`
- Modify: `docs/limitations.md`
- Modify: `docs/project/ROADMAP.md`
- Modify: `tests/test_safety_corpus_v2.py`

**Interfaces:**
- Produces: an auditable per-case owner-review process and documentation of identity, provenance, independence, access restrictions, no-score status, and #76/#85/#90 boundaries.

- [x] Add documentation assertions for correctness, category, minimality, offsets, reconstruction, names, syntax, provenance, licensing, isolation, owner authority, and no-score language; verify RED.
- [x] Write the checklist and update each declared document without claiming qualification or changing thresholds.
- [x] Run documentation and focused corpus tests to GREEN.

### Task 5: Bind explicit owner approval and freeze

**Files:**
- Create after approval: `tests/fixtures/evaluation/polish_correction_safety_corpus_v2.approval.json`
- Modify after approval: `tests/fixtures/evaluation/polish_correction_safety_corpus_v2.json`
- Modify after approval: `tests/fixtures/evaluation/polish_correction_safety_corpus_v2.xml`
- Modify after approval: `scripts/generate_safety_corpus_v2_candidates.py`
- Modify after approval: documentation files from Task 4
- Modify after approval: `tests/test_safety_corpus_v2.py`

**Interfaces:**
- Consumes: the `Polis architecture owner` role's explicit all-case approval, review date, and candidate digest.
- Produces: a frozen 240-case corpus, equivalent XML, bound approval manifest, and documented canonical frozen digest.

- [x] Stop after candidate verification and present the canonical JSON plus checklist for exhaustive role review.
- [x] After explicit approval, add a failing test requiring frozen state, 240 owner-reviewed records, approval-manifest binding, and documented digest.
- [x] Apply review metadata only after verifying corpus ID, case count, candidate digest, reviewer, date, and checklist version from the manifest.
- [x] Regenerate JSON/XML and verify the frozen digest against the approval manifest and documentation.
- [x] Confirm no command loads quality-gate cases or produces a score.

### Task 6: Verify, review, and publish the focused change

**Files:**
- Review: every file changed by Tasks 1-5.
- Delete: `docs/superpowers/plans/2026-08-02-session-2-issue-119.md`

**Interfaces:**
- Produces: one reviewed commit and draft PR for #119.

- [x] Run `uv run --locked --extra dev pytest tests/test_safety_corpus.py tests/test_safety_corpus_v2.py -q`.
- [x] Run `uv run --locked --extra dev pytest -m "not slow and not model" -q`.
- [x] Run `uv run --locked --extra dev ruff check .`.
- [x] Run `uv run --locked --extra dev ruff format --check .`.
- [x] Run `uv run --locked --extra dev mypy .`.
- [x] Run `uv run --locked --extra dev python -m build --no-isolation` and the distribution-content tests.
- [ ] Run `git diff --check`, verify pinned retained-evidence hashes, inspect the full diff, and obtain independent code review.
- [x] Delete only the #119 session prompt named above; preserve `docs/superpowers/plans/2026-08-02-session-1-issue-95.md` for the parallel session.
- [x] Create exactly one commit: `test: add independent sentence safety corpus v2 (#119)`.
- [ ] Push `codex/issue-119-safety-corpus-v2` and open a PR against `main` that links #119 without claiming #76 qualification.
- [ ] Wait for every required GitHub Actions check to pass; inspect and fix any failure before merging.
- [ ] Merge the PR, verify #119 is closed only after every acceptance criterion passes, update local `main`, and prove the #119 session prompt is absent from integrated `main`.

## Acceptance-criterion traceability

- Exact identity, schema, 240 total cases, four 60-case strata, and 20/40 splits: Tasks 1, 2, and 5.
- CC0-1.0 provenance, exact original-text spans, expected output or protected phenomenon, and owner-review metadata: Tasks 2 and 5.
- Cross-split and cross-asset independence for inputs, templates, entity IDs/combinations, and near-duplicate families: Task 3.
- Reuse of #114 validation/access infrastructure without reuse of linguistic content: Tasks 1-3, including the v2-only generator dependency regression.
- Canonical digest sensitivity plus candidate-to-frozen digest binding and documentation: Tasks 1, 4, and 5.
- Development holdout-gold denial and frozen, reviewed, digest-matching gate admission: Tasks 1, 3, and 5.
- Byte-for-byte preservation of corpus v3, safety corpus v1, approval data, markers, reports, results, and digests: Task 3.
- No development/holdout scoring, analyzer tuning, threshold change, or qualification claim: Tasks 3-6.
- Required adversarial coverage for offsets, reconstruction, duplicates, leakage, near families, entity reuse, review, digest drift, access, and JSON/XML equivalence: Tasks 1-3 and 5.
- Full fast pytest, focused validation, Ruff lint/format, mypy, build/distribution inspection, independent review, one focused commit, PR/CI/merge/closure, and session-prompt removal: Task 6.
