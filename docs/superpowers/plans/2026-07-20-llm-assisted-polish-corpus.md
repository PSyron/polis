# LLM-Assisted Polish E2E Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the small demonstration E2E fixture with a versioned Polish correction corpus that separates current deterministic behavior from LLM-backed quality targets.

**Architecture:** JSON is the review-friendly source fixture and XML is an equivalent interchange representation. Every case declares `rules`, `llm_planned` or `negative`; the suite exercises only current behavior and prevents planned targets from losing GitHub tracking.

**Tech Stack:** Python 3.11+, pytest, standard-library JSON/XML parsing, existing `polis.Analyzer` API.

## Global Constraints

- All examples are project-authored Polish sentences.
- Do not add model runtime, network call, model download or dependency.
- Bielik 4.5B v3.0 Instruct is a benchmark candidate, not a selected dependency.
- Planned LLM cases must reference #42 or #43.

### Task 1: Version the fixture and add gold examples

**Files:** modify `tests/fixtures/e2e/polish_correction_corpus.json`, `tests/fixtures/e2e/polish_correction_corpus.xml`, and `tests/test_e2e_polish_corrections.py`.

- [ ] Write a failing test requiring the three verification modes and issue references for `llm_planned` cases.
- [ ] Run `uv run --locked --extra dev pytest -q tests/test_e2e_polish_corrections.py` and verify the v1 fixture fails.
- [ ] Add v2 examples for deterministic corrections, planned flexion/syntax/contextual punctuation and safe negatives.
- [ ] Extend both loaders and JSON/XML equivalence assertions with the new fields.
- [ ] Re-run the focused test and commit `test: expand Polish LLM evaluation corpus`.

### Task 2: Make E2E checks mode-aware

**Files:** modify and test `tests/test_e2e_polish_corrections.py`.

- [ ] Write failing tests: `rules` applies to exact expected output; `negative` returns no findings; `llm_planned` has a changed gold output, semantic category tag and issue #42 or #43.
- [ ] Run the focused test and confirm the expected failure.
- [ ] Implement the smallest mode-aware parametrization and loaders.
- [ ] Re-run the focused test and commit `test: distinguish supported and planned E2E corrections`.

### Task 3: State the production LLM boundary

**Files:** modify `docs/limitations.md`; test `tests/test_e2e_polish_corrections.py`.

- [ ] Write a failing test requiring #42 and #43 in the limitations documentation.
- [ ] Add a concise statement that the current backend is mock-only and real-model selection plus adapter work are tracked separately.
- [ ] Run `uv run --locked --extra dev pytest -q`, Ruff check/format, and mypy.
- [ ] Commit `docs: track real local LLM quality work`.
