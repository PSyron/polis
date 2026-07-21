# Local LanguageTool Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce reproducible local LanguageTool 6.8 quality, safety, latency,
and memory evidence for the complete Polish E2E corpus.

**Architecture:** An experiment-only module owns loopback transport, strict
response normalization, UTF-16 offset conversion, deterministic edit scoring,
and privacy-safe report serialization. The production package remains
dependency-free and unchanged.

**Tech Stack:** Python 3.12+, standard library HTTP/JSON, pytest, local
LanguageTool 6.8 with OpenJDK 17.

## Global Constraints

- Analyzed text never leaves the device.
- Do not add LanguageTool or Java as a production dependency.
- Preserve original-text half-open Python code-point offsets.
- Prefer no automatic correction over an unjustified correction.
- Keep one focused commit referencing #52 and sole-author attribution.

---

### Task 1: Explicit corpus gold edits

**Files:**
- Modify: `tests/fixtures/e2e/polish_correction_corpus.json`
- Modify: `tests/fixtures/e2e/polish_correction_corpus.xml`
- Modify: `tests/test_e2e_polish_corrections.py`

**Interfaces:**
- Produces: every positive case has `expected_findings` that reconstruct the
  expected output; every negative case has an empty list.

- [ ] Add a failing parity/reconstruction test for all verification modes.
- [ ] Run the targeted E2E test and confirm the missing rule gold edits fail.
- [ ] Add exact category, span, original, and suggestion values to both corpus
  formats.
- [ ] Run the E2E tests and confirm they pass.

### Task 2: Strict response normalization

**Files:**
- Create: `experiments/languagetool_spike/benchmark.py`
- Create: `tests/test_languagetool_benchmark.py`
- Create: `tests/fixtures/languagetool/pl_response.json`

**Interfaces:**
- Produces: `utf16_offset_to_codepoint(text, offset) -> int`,
  `parse_response(text, payload) -> tuple[LanguageToolMatch, ...]`, and explicit
  category mapping.

- [ ] Write failing tests for surrogate-pair conversion, malformed payloads,
  alternatives, unknown categories, and verified source spans.
- [ ] Run the focused tests and confirm they fail for missing interfaces.
- [ ] Implement the smallest strict parser and immutable match model.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Deterministic scoring and private report

**Files:**
- Modify: `experiments/languagetool_spike/benchmark.py`
- Modify: `tests/test_languagetool_benchmark.py`

**Interfaces:**
- Produces: `score_case`, `summarize`, and `report_as_json` with exact
  TP/FP/FN, top-output, gold-reachability, negative-safety, p50/p95, and no raw
  text fields.

- [ ] Write failing tests for second-choice gold replacements, duplicates,
  wrong replacements, overlaps, negatives, latency percentiles, and stable
  serialization.
- [ ] Run the focused tests and confirm each fails for missing behavior.
- [ ] Implement deterministic matching, output application, aggregation, and
  serialization.
- [ ] Run the focused tests and confirm they pass.

### Task 4: Local client and live runner

**Files:**
- Create: `experiments/languagetool_spike/run_benchmark.py`
- Create: `experiments/languagetool_spike/README.md`
- Modify: `tests/test_languagetool_benchmark.py`

**Interfaces:**
- Produces: `LanguageToolClient.check(text)`, CLI arguments for endpoint,
  corpus, tool version, startup time, RSS, and output path.

- [ ] Write failing tests for non-loopback rejection, POST form fields,
  timeout, report path, and slow-test marking.
- [ ] Run the focused tests and confirm they fail.
- [ ] Implement the standard-library client and CLI without production
  dependencies.
- [ ] Run focused tests, Ruff, formatting, and mypy.

### Task 5: Run LanguageTool 6.8 and record the decision

**Files:**
- Create: `docs/architecture/decisions/0006-local-languagetool-benchmark.md`
- Modify: `docs/development/dependency-licenses.md`

**Interfaces:**
- Consumes: the pinned local server and benchmark CLI.
- Produces: measured report and the accept/reject/follow-up decision.

- [ ] Install or fetch the pinned 6.8 distribution and record artifact
  provenance without committing binaries.
- [ ] Start it on loopback, warm it up, run all corpus cases, and measure
  startup time and RSS.
- [ ] Run the benchmark again with networking unavailable or otherwise verify
  that analysis uses only loopback after installation.
- [ ] Record exact results, limitations, license consequences, and the next
  permitted issue in ADR-0006.
- [ ] Run the full fast suite, Ruff, formatting, mypy, and diff checks.
- [ ] Commit, push, close #52 only if every acceptance criterion is satisfied.
