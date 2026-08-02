# Issue #129 Correction Property Design

## Decision and scope

Issue #129 adds a bounded, deterministic, test-only structural guardrail for
the accepted correction-selection contract. It consumes only the synthetic
Unicode cases and privacy-safe replay API introduced by #123. It does not
alter `polis.correction`, `AnalysisResult`, automatic-correction policy,
evaluation assets, linguistic behavior, or dependencies.

ADR-0003 is the oracle. Two non-empty findings conflict exactly when their
half-open ranges overlap. Two insertions conflict exactly when their offsets
match. An insertion conflicts with a non-empty replacement at its start, at
every strictly internal offset, and at its end. Touching non-empty ranges are
compatible. A valid selection applies edits from greatest original `start` to
least, and validation completes before any output is returned.

## Considered approaches

1. Add Hypothesis strategies and shrinking. This would add a development
   dependency and a broader counterexample contract without a present consumer.
2. Use a mutable `random.Random` sequence in the test module. This loses the
   independently indexed replay contract established by #123.
3. Derive bounded edit descriptors directly from each #123 case, then build
   real `Finding` and `AnalysisResult` values. This preserves deterministic
   replay, covers the declared Unicode families, needs no dependency, and
   exercises the public correction contract. This is selected.

## Test design

`tests/test_correction_properties.py` owns only test helpers and generated
properties. Descriptor construction derives a SHA-256 digest from each #123
replay identity, then uses it to select distinct replacement and deletion
spans plus a valid interior insertion whenever the source allows one. Each
generated assertion routes through `assert_structural_invariant`, so a failure
reports a stable invariant plus generator version, seed, and case index—not
synthetic source text, fragments, suggestions, or corrected output.

The suite has three properties:

- conflict pairs prove symmetry and compare real `findings_conflict` output to
  an independently written ADR oracle for overlap, both replacement
  boundaries, interior insertion, duplicate insertions, and non-conflicts;
- deterministic compatible edit sets prove normalization is invariant for
  every non-empty selected subset and every selected-ID permutation,
  application is selection-order independent, and the result matches an
  independently implemented right-to-left reconstruction from the original
  string;
- invalid selections prove conflict, stale source span, unknown ID, duplicate
  ID, and absent suggestion each raise their controlled selection error before
  returning output. The immutable result state is then checked to prove no
  partial change was applied.

For every non-empty generated source, compatible descriptors use disjoint
non-empty spans and insertions strictly outside replacements. The digest
changes their positions across replay cases instead of pinning them to fixed
offsets. The generated set includes a replacement, deletion, and insertion
when its source is long enough; short and empty source cases receive only valid
shapes. This keeps the run within #123's fixed 64-case budget while exercising
combining marks and non-BMP Unicode as Python-code-point `[start, end)`
offsets.

## Documentation and limits

`docs/development/generative-invariants.md` will name the correction
properties, oracle, replay behavior, and structural-only evidence boundary.
The suite is not linguistic-quality evidence and does not run corpora,
holdouts, models, or evaluation. If an existing production contract fails a
property, the issue stops with replay metadata for a separate regression-first
bug issue; no repair belongs in #129.

## Design self-review

There are no open choices: #129 and ADR-0003 specify the generator boundary,
the conflict predicate, application ordering, and fail-closed policy. The
approach changes only test support, test documentation, and issue-planning
records. Expectations are independently derived rather than reusing
correction helpers, and every planned failure path is privacy-safe.
