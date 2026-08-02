# Generated Public Finding and Result Fidelity Design

## Context

Issue #124 is the finding/result child of tracker #95. The completed #123
harness already provides bounded, deterministic, synthetic Unicode strings and
privacy-safe replay metadata. The public `Finding`, `AnalysisResult`,
normalization, and schema-version-1 JSON contracts already have authored
examples. This issue adds generated structural evidence at those existing
public boundaries; it does not change a public contract or production behavior.

The issue is limited to synthetic text and test-only support. It is independent
of #119 and excludes correction application/conflicts, segmentation
reconstruction, registry output, linguistic assertions, corpora, holdouts,
models, dependencies, and Fast-CI wiring.

## Considered approaches

### Extend the production result API

Adding a public generator or result-validation API would make testing support a
runtime responsibility and expand the stable surface without a product use.
That conflicts with the issue boundary and is rejected.

### Add a second random or third-party property framework

This would duplicate #123's accepted hash-indexed replay design and either add
a dependency or create an unbounded/non-canonical source of generated data. It
is rejected.

### Consume the #123 harness from a focused public-boundary test module

The selected design adds one test module that derives a small, hand-specified
set of valid findings per generated string. It invokes the existing public
constructors, `normalize_findings`, and canonical JSON methods. Every failed
invariant is reported through `assert_structural_invariant`, which carries only
the safe invariant identifier and the #123 replay metadata.

## Generated fixtures and invariants

For every #123 case, the test constructs an insertion at offset zero. Non-empty
text also receives a replacement over `[0, 1)` and, when its length exceeds
one, a deletion over `[len(text) - 1, len(text))`. These spans are deliberate:
they cover empty spans, insertions, replacements, deletions, end offsets,
combining code points, and non-BMP code points using Python's code-point
indexing. The hand-authored construction order is already canonical by
`(start, end)`, so deterministic permutations can be normalized against it
without deriving expectations through the normalization code.

The properties verify:

- every valid public result has bounds `0 <= start <= end <= len(text)` and an
  exact `text[start:end] == finding.original` slice;
- repeated construction retains stable finding IDs and the public result keeps
  the same validated structural identity;
- normalization of generated permutations returns the hand-derived canonical
  tuple;
- canonical JSON encoding is deterministic and decoding then re-encoding
  preserves the complete validated result exactly;
- a same-length wrong original slice and an out-of-bounds empty insertion each
  fail at the `AnalysisResult` public boundary, before a result is returned;
- those negative-path exception messages do not contain the generated text.

Each checked condition uses an invariant name scoped to finding/result
fidelity, such as `finding.bounds` or `result.invalid_slice_rejected`. The
failure message is consequently replayable with generator version, seed, and
case index, but never includes analyzed text.

## Error handling and stop rule

The test exercises existing validation rather than catching and altering it.
If a generated case demonstrates a production defect, this issue stops without
changing `src/`; the case's replay metadata and a separate authored
regression-first bug child are required before any fix. Expected invalid public
results are accepted only when `AnalysisResult` raises `TypeError` or
`ValueError` and its diagnostic excludes text.

## Testing and boundaries

The property budget remains #123's fixed default: generator version
`unicode-structural-v1`, seed `95001`, and 64 cases. Tests do not read
environment state, use a network, introduce data files, or run linguistic
evaluation. The new module is part of the normal fast pytest selection but
does not alter CI configuration. Public JSON/API contracts, Unicode half-open
code-point offsets, offline privacy, and the #123 harness remain unchanged.

## Consequences and limitations

This adds deterministic breadth around current public result fidelity. It does
not prove raw registry output validity, correction behavior, segmentation
reconstruction, or Polish linguistic quality. Authored regressions and corpus
gates remain authoritative for those concerns.
