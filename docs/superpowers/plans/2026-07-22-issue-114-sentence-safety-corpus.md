# Issue #114 Independent Sentence Safety Corpus Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a validated, independent 240-case Polish sentence safety corpus and freeze it only after Paweł Cyroń completes the required owner review.

**Architecture:** Keep canonical case content in JSON with a mechanically equivalent XML representation. Reuse schema-v3 models and primitive invariants, but enforce safety-corpus identity, entity catalog, access policy, and cross-asset isolation in a focused module. Author candidates reproducibly from explicit Polish case specifications, then separate automatic validation from the human-review/freeze transition.

**Tech Stack:** Python 3.12+, standard library JSON/XML/hashlib, pytest, Ruff, mypy, uv.

## Global Constraints

- Work only on GitHub issue #114 and produce one focused commit referencing `#114`.
- Preserve the offline-only privacy boundary and do not change analyzer, rule, evaluator, source-policy, or scoring behavior.
- Do not read, rerun, repair, or tune against the corpus-v3 holdout.
- Keep corpus-v3 files, results, and digests byte-for-byte unchanged.
- Use project-authored synthetic Polish under CC0-1.0 and half-open Unicode offsets `[start, end)`.
- Only Paweł Cyroń may record `human-reviewed`; automated work must retain `pending-human-review` until that review occurs.
- Produce no holdout score.

---

### Task 1: Lock the safety-corpus validator contract

**Files:**
- Modify: `src/polis/evaluation/safety_corpus.py`
- Modify: `src/polis/evaluation/__init__.py`
- Create: `tests/test_safety_corpus.py`

**Interfaces:**
- Consumes: schema-v3 value models and primitive validators from `polis.evaluation.correction_corpus`.
- Produces: `load_safety_corpus_json`, `load_safety_corpus_xml`, `validate_safety_corpus`, `select_safety_cases_for_purpose`, `assert_no_cross_corpus_leakage`, `safety_corpus_digest`, and `safety_entity_catalog_ids`.

- [ ] **Step 1: Write failing public-contract tests**

```python
def test_safety_corpus_api_is_public() -> None:
    from polis.evaluation import load_safety_corpus_json

    assert callable(load_safety_corpus_json)


def test_quality_gate_rejects_unfrozen_candidates(raw_corpus: dict[str, Any]) -> None:
    corpus = validate_safety_corpus(raw_corpus)

    with pytest.raises(CorpusUsageError, match="frozen"):
        select_safety_cases_for_purpose(corpus, purpose="quality_gate")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `uv run --locked --extra dev pytest tests/test_safety_corpus.py -q`

Expected: failure because the safety API is not exported and/or required policy behavior is incomplete.

- [ ] **Step 3: Complete the minimal validator and exports**

Keep exact-field, review, edit, reconstruction, entity-span, balance, isolation,
digest, and purpose-selection validation in `safety_corpus.py`. Export only the
documented public functions from `polis.evaluation`; do not expose private
schema-v3 helpers.

- [ ] **Step 4: Add focused adversarial tests**

Parameterize mutations for unknown fields, invalid sentence unit, incorrect
offsets, overlapping edits, reconstruction mismatch, missing controlled entity
span, duplicate input/template, near-duplicate family, cross-split entity
reuse, missing review metadata, premature freeze, training selection, and
digest content sensitivity.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `uv run --locked --extra dev pytest tests/test_safety_corpus.py -q`

Expected: all focused validator tests pass.

### Task 2: Author and validate the 240 candidates

**Files:**
- Create: `scripts/generate_safety_corpus_candidates.py`
- Create: `tests/fixtures/evaluation/polish_correction_safety_corpus_v1.json`
- Create: `tests/fixtures/evaluation/polish_correction_safety_corpus_v1.xml`
- Modify: `tests/test_safety_corpus.py`

**Interfaces:**
- Consumes: explicit case specifications containing input, corrected output or protected phenomenon, stratum, tags, description, entity surfaces, and split.
- Produces: deterministic schema-v3 JSON and equivalent XML; the generator never changes review state or freezes the holdout.

- [ ] **Step 1: Write the missing-fixture integrity test**

```python
def test_candidate_corpus_has_exact_balance() -> None:
    corpus = load_safety_corpus_json(JSON_CORPUS)

    assert len(corpus.cases) == 240
    for stratum in ("inflection", "syntax", "punctuation", "hard_negative"):
        cases = [case for case in corpus.cases if case.stratum == stratum]
        assert len(cases) == 60
        assert sum(case.split == "development" for case in cases) == 20
        assert sum(case.split == "holdout" for case in cases) == 40
```

- [ ] **Step 2: Run the fixture test and verify RED**

Run: `uv run --locked --extra dev pytest tests/test_safety_corpus.py::test_candidate_corpus_has_exact_balance -q`

Expected: fail because the canonical fixture does not exist.

- [ ] **Step 3: Add explicit candidate specifications**

Author 60 distinct linguistic families per stratum. Use only safety-catalog
entities, keep entity combinations split-disjoint, and avoid corpus-v3,
fine-tuning, prompt, and E2E sentence topologies. Every positive specification
must define one objective minimal edit; every hard negative must define one
protected phenomenon and no edit.

- [ ] **Step 4: Implement mechanical generation**

The generator must derive edit offsets by comparing the declared original and
replacement fragments, derive entity spans and normalized templates through
the production validator, serialize stable UTF-8 JSON, and emit XML with all
closed-schema fields. It writes `unfrozen-candidates` and this review record:

```python
{
    "status": "pending-human-review",
    "reviewer": None,
    "reviewed_at": None,
    "checklist_version": "safety-corpus-review-v1",
}
```

- [ ] **Step 5: Generate fixtures and run integrity tests**

Run: `uv run scripts/generate_safety_corpus_candidates.py`

Run: `uv run --locked --extra dev pytest tests/test_safety_corpus.py -q`

Expected: 240 candidates validate with exact balance and JSON/XML equivalence.

### Task 3: Prove independence from all reserved assets

**Files:**
- Modify: `src/polis/evaluation/safety_corpus.py`
- Modify: `tests/test_safety_corpus.py`
- Modify: `scripts/generate_safety_corpus_candidates.py`

**Interfaces:**
- Consumes: closed `IsolationRecord` values built from corpus v3, fine-tuning JSONL, prompt examples, and E2E JSON/XML.
- Produces: deterministic failures on input, template, canonical entity-combination, or near-family leakage.

- [ ] **Step 1: Write adversarial leakage tests**

```python
@pytest.mark.parametrize("collision", ["input", "template", "entities", "family"])
def test_cross_asset_leakage_is_rejected(
    safety_corpus: CorrectionCorpus, collision: str
) -> None:
    record = isolation_collision(safety_corpus, collision)

    with pytest.raises(CorpusUsageError, match="leakage|family"):
        assert_no_cross_corpus_leakage(safety_corpus, [record], source="adversary")
```

- [ ] **Step 2: Run adversarial tests and verify RED**

Run: `uv run --locked --extra dev pytest tests/test_safety_corpus.py -k cross_asset -q`

Expected: at least one collision class is not yet detected or asset conversion is unavailable.

- [ ] **Step 3: Complete closed-record conversion and leakage checks**

Build records without importing evaluated answers into runtime policy. Validate
entity spans before comparison. Compare the complete candidate corpus against
every reserved asset during generation and in tests. Fail with source and
record identifiers, never by silently dropping a candidate.

- [ ] **Step 4: Add entity-catalog disjointness and real-asset tests**

Assert that the safety catalog and corpus-v3 controlled catalog share no
canonical identifiers. Load every fine-tuning split, every prompt example used
by the repository, and both E2E representations. Assert the complete corpus is
independent and that corpus-v3 fixture bytes/digest are unchanged.

- [ ] **Step 5: Run leakage tests and verify GREEN**

Run: `uv run --locked --extra dev pytest tests/test_safety_corpus.py -k "leakage or catalog or reserved" -q`

Expected: all isolation tests pass without reading a holdout score.

### Task 4: Document the candidate corpus and review gate

**Files:**
- Create: `docs/evaluation-safety-corpus-v1-review-checklist.md`
- Modify: `docs/evaluation-dataset.md`
- Modify: `docs/llm-quality-gates.md`
- Modify: `docs/limitations.md`
- Modify: `tests/test_safety_corpus.py`

**Interfaces:**
- Produces: one auditable owner-review procedure and documentation of provenance, independence, relationship to corpus v3/#85, access policy, and no-score status.

- [ ] **Step 1: Write failing documentation assertions**

Assert that the checklist names all review dimensions and that documentation
contains the corpus ID, candidate state, CC0-1.0 provenance, corpus-v3 boundary,
issue #85 boundary, no-score statement, and the rule that a digest is recorded
only after the corpus is frozen.

- [ ] **Step 2: Run documentation tests and verify RED**

Run: `uv run --locked --extra dev pytest tests/test_safety_corpus.py -k documentation -q`

Expected: fail because the checklist and references do not exist.

- [ ] **Step 3: Write the checklist and documentation**

The checklist requires per-case correctness, category, minimality, offsets,
reconstruction, proper-name behavior, syntax/word order, provenance, license,
and isolation review. It explicitly reserves approval to Paweł Cyroń and
forbids freezing until all cases are approved.

- [ ] **Step 4: Run documentation and focused tests**

Run: `uv run --locked --extra dev pytest tests/test_safety_corpus.py -q`

Expected: all candidate-phase tests pass.

### Task 5: Owner review, freeze, and final verification

**Files:**
- Modify: `tests/fixtures/evaluation/polish_correction_safety_corpus_v1.json`
- Modify: `tests/fixtures/evaluation/polish_correction_safety_corpus_v1.xml`
- Modify: `docs/evaluation-dataset.md`
- Modify: `docs/llm-quality-gates.md`
- Modify: `docs/limitations.md`
- Modify: `tests/test_safety_corpus.py`

**Interfaces:**
- Consumes: Paweł Cyroń's explicit completed review of all 240 cases.
- Produces: frozen corpus, equivalent XML, recorded canonical digest, and no score.

- [x] **Step 1: Stop for owner review**

Present the canonical candidate JSON and checklist to Paweł Cyroń. Do not edit
review metadata, freeze, or record a final digest before explicit confirmation
that every case passed the checklist.

- [x] **Step 2: Add the failing frozen-state test after approval**

```python
def test_owner_reviewed_corpus_is_frozen_and_digest_is_documented() -> None:
    corpus = load_safety_corpus_json(JSON_CORPUS)

    assert corpus.holdout_state == "frozen"
    assert all(case.review.status == "human-reviewed" for case in corpus.cases)
    assert safety_corpus_digest(_raw_corpus()) in GUIDE.read_text(encoding="utf-8")
```

- [x] **Step 3: Record owner approval mechanically**

Record reviewer `Paweł Cyroń`, the supplied ISO review date, checklist
`safety-corpus-review-v1`, `all-cases` scope, and the candidate and frozen
digests in a separate approval manifest. The generator verifies the candidate
digest before it applies review metadata and `frozen`, then validates all
reserved assets before writing JSON or XML.

- [ ] **Step 4: Run focused and full verification**

Run: `uv run --locked --extra dev pytest tests/test_safety_corpus.py -q`

Run: `uv run --locked --extra dev pytest -q`

Run: `uv run --locked --extra dev ruff check .`

Run: `uv run --locked --extra dev ruff format --check .`

Run: `uv run --locked --extra dev mypy .`

Expected: all commands exit 0; no test invokes or records a holdout score.

- [ ] **Step 5: Verify scope and create the single commit**

Check `git diff --check`, confirm corpus-v3 fixtures/results/digests are
unchanged, inspect the complete diff, then create exactly one focused commit:

```console
git commit -m "test: add independent sentence safety corpus (#114)"
```
