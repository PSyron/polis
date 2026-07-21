# Inflection Candidate Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate a real, finite LanguageTool Polish inflection candidate generator and define its auditable record for later prompt selection.

**Architecture:** Extend the pinned LanguageTool stdio bridge with a backward-compatible synthesis operation, then drive it from a focused Python experiment. Java owns real morphology and stable candidate production; Python owns corpus selection, validation, metrics, and evidence reporting.

**Tech Stack:** Java 17, LanguageTool 6.8 Polish tagger/synthesizer, Jackson, Python 3.13, pytest, JSON.

## Global Constraints

- Keep analyzed text on-device and use only the separate local stdio process.
- Do not add Morfeusz or another production dependency in this issue.
- Do not derive candidates, lemmas, or tags from corpus gold suggestions.
- Use half-open original-text ranges `[start, end)` and preserve capitalization.
- Prefer an unchanged candidate or no alternative over an unjustified form.
- Paweł Cyroń is the sole credited author.

---

### Task 1: Candidate contract and authored fixtures

**Files:**
- Create: `experiments/inflection_candidates/__init__.py`
- Create: `experiments/inflection_candidates/benchmark.py`
- Create: `experiments/inflection_candidates/cases.json`
- Create: `tests/test_inflection_candidate_benchmark.py`

**Interfaces:**
- Produces: `InflectionCandidate`, `CandidateSpanResult`, `load_authored_cases()`, and `validate_response()`.
- Consumes: newline-delimited JSON response objects from the local bridge.

- [ ] Write failing tests that validate stable IDs, exact offsets, optional
  lemmas, non-empty forms, sorted features, duplicate rejection, unchanged
  coverage, and authored fixture categories.
- [ ] Run `uv run pytest tests/test_inflection_candidate_benchmark.py -q` and
  verify imports or assertions fail because the experiment does not exist.
- [ ] Implement immutable candidate/result records and strict response parsing.
- [ ] Add authored fixtures for ordinary nouns/adjectives, first names,
  surnames, uppercase and title case, diacritics, an indeclinable name, an
  unknown token, an already-inflected form, and duplicate-form behavior.
- [ ] Re-run the focused tests and make them pass.

### Task 2: Real LanguageTool synthesis operation

**Files:**
- Modify: `third_party/languagetool-pl/src/main/java/org/polis/languagetool/PolisStdioServer.java`
- Modify: `third_party/languagetool-pl/scripts/verify.sh`
- Test: `tests/test_languagetool_vendor_artifacts.py`

**Interfaces:**
- Consumes: `{"operation":"synthesize","language":"pl-PL","text":str,"spans":[{"start":int,"end":int}]}`.
- Produces: one candidate result per input span with stable IDs, source ranges,
  lemma, form, features, and optional unsupported reason.

- [ ] Add failing source-policy tests requiring `PolishTagger`,
  `PolishSynthesizer`, explicit span validation, and no corpus-derived map.
- [ ] Run the focused source-policy test and verify it fails on missing markers.
- [ ] Implement strict request dispatch while preserving the existing check
  request shape.
- [ ] Enumerate upstream tag entries for supported `subst` and `adj` analyses,
  synthesize forms, preserve capitalization, merge duplicates, and create
  content-derived stable IDs.
- [ ] Always include the original surface. Return `no-analysis`,
  `unsupported-pos`, or `no-alternatives` explicitly when applicable.
- [ ] Extend offline verification with a real synthesis request and assert the
  expected form, original candidate, offsets, lemma, and features.
- [ ] Run `POLIS_LT_OFFLINE=1 ./third_party/languagetool-pl/scripts/build.sh`
  and `./third_party/languagetool-pl/scripts/verify.sh`.

### Task 3: Corpus benchmark and runtime evidence

**Files:**
- Modify: `experiments/inflection_candidates/benchmark.py`
- Create: `experiments/inflection_candidates/run_benchmark.py`
- Modify: `tests/test_inflection_candidate_benchmark.py`

**Interfaces:**
- Produces: a JSON report with per-class recall, ambiguity, unsupported count,
  unchanged coverage, latency, RSS, disk size, revision, and license.
- Consumes: frozen corpus-v3 single-token inflection edits and authored cases.

- [ ] Add failing tests for class assignment (`ordinary`, `first_name`,
  `surname`), single-token eligibility, gold isolation in outbound requests,
  recall, ambiguity, unsupported handling, latency percentiles, and report
  serialization without source text.
- [ ] Run the focused tests and verify the intended failures.
- [ ] Implement a warm subprocess client, corpus-case selection, metric
  aggregation, runtime evidence collection, and deterministic JSON output.
- [ ] Add a slow integration test gated by `POLIS_LT_VENDOR_INTEGRATION=1`.
- [ ] Run the authored and frozen development/holdout measurements once the
  implementation is fixed; save only aggregate, non-private evidence.

### Task 4: Decision and documentation

**Files:**
- Create: `experiments/inflection_candidates/README.md`
- Create: `docs/architecture/decisions/0010-inflection-candidate-generation.md`
- Modify: `docs/architecture/README.md`
- Modify: `third_party/languagetool-pl/README.md`
- Modify: `third_party/languagetool-pl/BENCHMARK.md`

**Interfaces:**
- Consumes: the real report from Task 3.
- Produces: the reproducible method, exact commands, resource footprint,
  licenses, supported classes, gaps, and LanguageTool/Morfeusz decision.

- [ ] Document the request/response contract and make clear that candidates do
  not claim contextual correctness.
- [ ] Record class-separated metrics and authored edge-case outcomes.
- [ ] Record upstream LGPL-2.1-or-later and dictionary provenance plus optional
  separate-process packaging consequences.
- [ ] Accept LanguageTool only if required candidate classes have useful recall
  and unchanged coverage; otherwise justify a time-boxed Morfeusz follow-up or
  reject deterministic generation.

### Task 5: Completion verification and delivery

**Files:** all files changed by Tasks 1-4.

- [ ] Run `uv run pytest` and confirm all fast tests pass with only documented
  integration skips.
- [ ] Run `uv run ruff check .`, `uv run ruff format --check .`, and
  `uv run mypy .`.
- [ ] Run the pinned Java offline build, verifier, and slow integration test.
- [ ] Run `git diff --check` and inspect the complete issue-scoped diff.
- [ ] Commit once with `research: evaluate inflection candidate generation (#58)`.
- [ ] Push `main`, close #58 only after every acceptance criterion is evidenced,
  and identify the next unblocked M5 issue.
