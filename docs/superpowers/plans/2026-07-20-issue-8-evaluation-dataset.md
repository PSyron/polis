# Licensed Polish Evaluation Dataset Implementation Plan

**Goal:** Ship a small, versioned, project-authored Polish evaluation dataset with a strict offline validator.

**Architecture:** Store the closed-schema JSON asset beside the `polis.evaluation` package so it can be reviewed as versioned project data. Keep validation in one standard-library module, whose public `validate_dataset()` function returns validated immutable records or raises a descriptive `ValueError`; tests exercise the committed asset and adversarial in-memory copies.

**Tech Stack:** Python 3.12+, JSON, dataclasses, `importlib.resources`, pytest, Ruff, mypy.

## Global Constraints

- Use schema version `1` and Python Unicode-code-point half-open offsets `[start, end)`.
- Use only project-authored CC0-1.0 text; never include private, copied, scraped, or model-generated text.
- Reuse the public `Category` values exactly; do not implement analyzers, score thresholds, or correction application.
- Every correction must be a justified non-no-op replacement, insertion, or deletion.
- Each correct case must explicitly contain an empty expected-finding list.

### Task 1: Describe the data contract and write failing validation tests

**Files:**

- Create: `tests/test_evaluation_dataset.py`
- Create: `docs/evaluation-dataset.md`

- [x] Add tests that load the committed dataset, require every public category,
  assert exact Unicode fragments, and apply each finding to verify the complete
  intended grammatical sentence.
- [x] Add parameterized adversarial tests for duplicate IDs, missing case provenance, an unlicensed case, unknown keys/categories, invalid spans, mismatched fragments, no-op corrections, and malformed correct cases.
- [x] Reject overlapping replacements, insertions at replacement starts or
  interiors, and duplicate insertions while allowing deterministic end-boundary
  and separated insertions.
- [x] Run `uv run --locked --extra dev pytest tests/test_evaluation_dataset.py -v` before implementation and confirm collection fails because `polis.evaluation.dataset` does not exist.

### Task 2: Implement the closed-schema validator and asset

**Files:**

- Create: `src/polis/evaluation/dataset.py`
- Create: `src/polis/evaluation/datasets/v1/cases.json`
- Modify: `src/polis/evaluation/__init__.py`

- [x] Implement strict JSON-object and field checks using only the standard library and the public `Category` enum.
- [x] Validate stable IDs, CC0 provenance, outcome shape, exact original fragments, non-overlapping half-open spans, and non-no-op corrections.
- [x] Add a reviewable collection of authored Polish findings across inflection, agreement, syntax, spelling, punctuation, and style, plus difficult explicit no-finding negatives.
- [x] Re-run the focused suite and confirm all cases validate.

### Task 3: Document stewardship and run repository gates

**Files:**

- Modify: `README.md`
- Modify: `docs/evaluation-dataset.md`
- Test: `tests/test_evaluation_dataset.py`

- [x] Document the schema, category semantics, provenance and CC0 rules, human-review requirement, anonymization, and exclusions for private and model-generated text.
- [x] Explain that dependency-spike cases remain diagnostic evidence and are not copied into this quality gold set.
- [x] Run the focused tests, fast pytest selection, Ruff lint/format checks, strict mypy, unittest discovery, build and distribution-artifact verification.
- [x] Review each issue acceptance criterion, scan for prohibited attribution, and commit the focused change once.
