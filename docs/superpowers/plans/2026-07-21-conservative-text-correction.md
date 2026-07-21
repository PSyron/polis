# Conservative Text Correction Implementation Plan

**Goal:** Return an original sentence or paragraph together with a safely corrected version.

**Architecture:** Add an immutable public result wrapper around `AnalysisResult`.
`Analyzer.correct()` will reuse `analyze()`, select only correctable findings from
deterministic rule sources at or above a conservative confidence threshold, and
apply them through the existing conflict-safe `AnalysisResult.apply()` method.

### Task 1: Public correction result and Analyzer entry point

**Files:** modify `src/polis/analyzer.py`, `src/polis/__init__.py`; add
`tests/test_conservative_correction.py`.

1. Write tests for one sentence, a multi-sentence paragraph, an unchanged
   correct sentence, a name-containing input, and conflicting candidates.
2. Confirm the new tests fail because `Analyzer.correct` is absent.
3. Add `CorrectionResult` with `original_text`, `corrected_text`,
   `applied_findings`, and `skipped_findings`; add `Analyzer.correct(text)`.
4. Apply only findings with a suggestion, confidence at least `0.9`, a
   `rule` source, and no conflict; report every other finding as skipped.
5. Run focused tests, full fast suite, Ruff, formatting, and mypy.

### Task 2: Public documentation

**Files:** modify `README.md`, `docs/public-api.md`.

1. Add a sentence and paragraph example using `Analyzer.correct`.
2. State that correction is conservative and local; low-confidence, conflicting,
   name-sensitive, and non-rule suggestions remain unapplied.
3. Re-run API contract and type-check tests.
