# Generated Segmentation Reconstruction Properties Design

## Context

Issue #125 is the segmentation child of tracker #95. Existing authored
regressions remain the authority for linguistic sentence-boundary behaviour.
This issue adds only a bounded, deterministic structural guardrail over the
shared test-only Unicode generator delivered by #123.

## Settled design

One test module obtains the 64 default synthetic cases from
`tests.generative.generate_unicode_text_cases()`. It runs the unchanged
`segment_paragraphs` and `segment_sentences` functions separately for every
case, including the explicit empty-string case. A shared test-local assertion
routine checks each segment in implementation order:

1. its Unicode code-point half-open span is bounded by the source string;
2. its start equals the preceding segment's end;
3. its stored text is exactly `source[start:end]`; and
4. the concatenated segment text exactly reconstructs the source string.

The property also asserts that the generated run's declared family union is
exactly `UNICODE_FAMILIES`. This verifies coverage of ASCII, Polish
diacritics, non-BMP characters, combining marks, LF, CRLF, punctuation, and
quotes through the #123 contract rather than by duplicating synthetic fixtures.

Every property failure uses `assert_structural_invariant` with a stable
`segmentation.<kind>.<invariant>` identifier and the failing case's `Replay`.
The shared helper emits only that identifier and generator/seed/case metadata,
never the generated source text. The generated cases and their repr already
keep text private.

## Alternatives considered

Writing more hand-authored segmentation examples would improve representative
linguistic coverage but would not exercise reproducible combinations across
all #123 Unicode and line-ending families. Adding a property-testing dependency
would duplicate #123's rejected dependency and broader reporting surface. The
selected direct consumer of the shared deterministic harness is the smallest
scope that satisfies #125.

## Scope and non-goals

No segmentation heuristic, public API, production module, dependency, corpus,
holdout, model evaluation, registry, finding, correction, or pipeline changes
are permitted. The properties make no linguistic-quality claim and do not
replace authored regressions. A production segmentation defect found while
adding the guardrail stops this issue for a separate regression-first bug
issue; it is not fixed here.

## Test design

The RED test names the missing safeguard: the generated structural assertion
routine is absent, so neither segmentation function is covered by the #123
cases. It exercises the real segmenters and uses hand-defined invariant
relationships, not mocks or expected values derived from the segmenter. The
routine would fail for realistic mutations such as an omitted tail, an
out-of-order segment, an incorrect offset, or stale segment text.

## Documentation

`docs/segmentation.md` will describe the generated reconstruction properties
as a structural, non-linguistic guardrail and point readers to the #123 replay
contract. It will retain the current API and heuristic documentation unchanged.

## Self-review

- No requirement is left undecided or represented by a placeholder.
- The design consumes only the already accepted #123 test-support API.
- Exact source reconstruction, Unicode code-point offsets, family coverage,
  replay-safe diagnostics, empty input, and non-linguistic scope each map to
  the implementation plan.
- The design introduces no production behaviour change, so discovering a
  failure in the existing segmenters is an explicit stop condition.
