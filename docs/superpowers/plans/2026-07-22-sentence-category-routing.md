# Sentence Category Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and evaluate a gold-independent, sentence-only rules-first pipeline that uses a compact local model exclusively for residual Polish syntax.

**Architecture:** A new experiment package composes the existing LanguageTool stdio client, corpus-v3 loader, syntax prompt contracts, and strict scoring helpers. Routing accepts only sentence source evidence and deterministic findings; scoring receives gold separately. Model proposals are bounded to one evidence window, protected-span checked, verified with at most one additional call, and never automatically applied.

**Tech Stack:** Python 3.12+, pytest, existing Polis core/evaluation/LLM modules, vendored LanguageTool 6.8 stdio bridge, local MLX/Ollama runtimes.

## Global Constraints

- Process one Polish sentence only; paragraph correction is out of scope.
- Remain offline and fail closed; do not download artifacts implicitly.
- Do not commit source text responses, model weights, caches, or machine work files.
- Routing must not consume corpus focus, tags, expected output, or gold edits.
- Permit at most two model calls for an eligible sentence.
- Keep every model-derived edit suggestion-only.
- Require 100% valid outcomes, zero protected-negative suggestions, precision >= 0.90, supported-focus recall >= 0.25, p95 <= 2,000 ms, model memory <= 4 GiB, and swap growth <= 64 MiB.

---

### Task 1: Freeze experiment configuration and data boundaries

**Files:**
- Create: `experiments/sentence_category_routing/__init__.py`
- Create: `experiments/sentence_category_routing/config.json`
- Create: `experiments/sentence_category_routing/experiment.py`
- Test: `tests/test_sentence_category_routing.py`

**Interfaces:**
- Consumes: `load_correction_corpus_json()` and `select_cases_for_purpose()`.
- Produces: `ExperimentConfig`, `RoutingCase`, `load_config(path)`, and `load_cases(path, split)` with gold stored separately from `RoutingInput`.

- [x] **Step 1: Write failing configuration and leakage tests** that require exactly three predeclared model configurations, the frozen corpus hash, the sentence-only flag, all numeric gates, and a `RoutingInput` type without labels or expected text.
- [x] **Step 2: Run `uv run --locked --extra dev pytest tests/test_sentence_category_routing.py -k 'config or leakage' -v`** and verify the imports or assertions fail because the experiment package does not exist.
- [x] **Step 3: Implement immutable configuration/data types and strict JSON loading** with rejected unknown keys, finite positive numeric gates, exact corpus SHA-256 validation, and separate evaluation records.
- [x] **Step 4: Rerun the focused tests** and require all selected tests to pass.

### Task 2: Implement deterministic sentence routing

**Files:**
- Create: `experiments/sentence_category_routing/routing.py`
- Modify: `tests/test_sentence_category_routing.py`

**Interfaces:**
- Consumes: `RoutingInput(source: str, deterministic_findings: tuple[Finding, ...])`.
- Produces: `route_sentence(input) -> RoutingDecision`, where `RoutingDecision` contains sentence eligibility, deterministic channel records, optional one `SyntaxEvidenceWindow`, and protected spans.

- [x] **Step 1: Add failing tests** for multi-sentence rejection, identical routing after evaluation-label mutation, LanguageTool punctuation classification, protected URLs/numbers/quotes/entities, one exact syntax evidence window, and no task for unsupported evidence.
- [x] **Step 2: Run `uv run --locked --extra dev pytest tests/test_sentence_category_routing.py -k routing -v`** and verify failures are caused by missing routing behavior.
- [x] **Step 3: Implement the smallest deterministic router** using sentence segmentation, normalized deterministic findings, explicit allowlisted evidence kinds, half-open offsets, and merged protected spans.
- [x] **Step 4: Rerun routing tests** and require them to pass without consulting corpus gold fields.

### Task 3: Add syntax-only requests and application validation

**Files:**
- Create: `experiments/sentence_category_routing/protocol.py`
- Modify: `tests/test_sentence_category_routing.py`

**Interfaces:**
- Consumes: `RoutingDecision` and existing `build_proposal_verifier_prompt_request()`.
- Produces: `build_syntax_request(decision) -> PromptRequest`, `validate_syntax_response(raw, decision) -> SyntaxProposal | None`, and `validate_verified_proposal(...) -> tuple[Finding, ...]`.

- [x] **Step 1: Add failing protocol tests** for the closed schema, category-specific instruction, delimited source data, exact evidence bounds, protected spans, unchanged response, one in-window minimal edit, and rejection of broad/out-of-window/protected changes.
- [x] **Step 2: Run `uv run --locked --extra dev pytest tests/test_sentence_category_routing.py -k protocol -v`** and confirm the new contract is absent.
- [x] **Step 3: Implement the syntax-only request and validators** by reusing existing diff/protected-span utilities and returning a suggestion source that is not correction-policy eligible.
- [x] **Step 4: Rerun protocol tests** and require complete success.

### Task 4: Build the privacy-safe benchmark runner and selector

**Files:**
- Create: `experiments/sentence_category_routing/run_benchmark.py`
- Create: `experiments/sentence_category_routing/assemble_report.py`
- Modify: `tests/test_sentence_category_routing.py`

**Interfaces:**
- Consumes: frozen config, development `RoutingCase` records, LanguageTool stdio, and injected local runtime clients.
- Produces: identifier-only run artifacts, `select_development_winner(runs)`, `freeze_selection(...)`, and `reserve_holdout_once(...)`.

- [x] **Step 1: Add failing tests** for two-call enforcement, deterministic/model channel separation, exact-edit scoring, gate ordering, unavailable configurations, report privacy, configuration hashing, winner freezing, and atomic one-shot holdout reservation.
- [x] **Step 2: Run `uv run --locked --extra dev pytest tests/test_sentence_category_routing.py -k 'runner or scoring or selection or privacy or holdout' -v`** and confirm expected failures.
- [x] **Step 3: Implement injected runtime orchestration and scoring** without raw text persistence; reuse the loopback-only clients and memory/swap samplers already established by earlier experiments.
- [x] **Step 4: Rerun the focused runner tests** and require all to pass.

### Task 5: Execute development, decide, and document evidence

**Files:**
- Create: `experiments/sentence_category_routing/README.md`
- Create: `experiments/sentence_category_routing/report.json`
- Create: `docs/architecture/decisions/0013-qualify-or-reject-sentence-category-routing.md`
- Modify: `docs/project/ROADMAP.md`
- Modify: `docs/limitations.md`

**Interfaces:**
- Consumes: completed benchmark runner and frozen local configurations.
- Produces: reproducible aggregate evidence and the decision whether issue #43 may be unblocked.

- [x] **Step 1: Run all fast experiment tests** with `uv run --locked --extra dev pytest tests/test_sentence_category_routing.py -v`.
- [x] **Step 2: Verify the vendored engine** with `POLIS_LT_OFFLINE=1 third_party/languagetool-pl/scripts/build.sh` and its opt-in integration tests.
- [x] **Step 3: Execute the three development configurations sequentially** so memory and swap measurements are attributable, keeping raw work artifacts in an ignored temporary directory.
- [x] **Step 4: Assemble `report.json` and freeze a winner only if every development gate passes; otherwise do not access holdout.**
- [x] **Step 5: If eligible, reserve and execute the holdout exactly once; otherwise record `holdout_not_run`.**
- [x] **Step 6: Record ADR-0013, update roadmap/limitations, and state explicitly whether #43 is unblocked.**
- [x] **Step 7: Run `uv run --locked --extra dev ruff check .`, `uv run --locked --extra dev ruff format --check .`, `uv run --locked --extra dev mypy .`, the full `pytest` suite, distribution checks, and vendored LanguageTool integration.**
- [x] **Step 8: Create one focused issue commit** with `git commit -m "research: benchmark sentence category routing (#69)"`, push it, and close #69 only when every acceptance criterion is evidenced.
