# Generated Pipeline Parity Properties Design

## Context

Issue #130 is the pipeline-parity child of tracker #95. The accepted #123
test-only harness supplies a fixed, bounded, synthetic Unicode domain and
privacy-safe replay metadata. Issues #124 and #125 already validate public
finding fidelity and segmentation reconstruction independently. This issue
adds evidence at the existing analysis-pipeline boundary only; it must not
change production behavior, contracts, retry policy, or error semantics.

## Settled design

One test module will consume the default 64 cases from
`tests.generative.generate_unicode_text_cases()`. For each generated source it
will run the real `analyze_text()` wrapper and `analyze_text_async()` coroutine
with the same deterministic test registry and local finding backend. The fake
registry emits a stable rule finding and the fake backend derives stable,
fragment-local findings directly from the fragment it receives. It never uses a
model, network, corpus, holdout, ambient randomness, clock, or retry behavior.

The successful-result property will require the two entry points to return the
same tuple in the hand-checked canonical order. It will then verify every
finding against the original generated source using Unicode code-point
half-open offsets: `0 <= start <= end <= len(source)` and
`finding.original == source[start:end]`. Backend findings carry a unique local
source name, so the property separately establishes that their translated
original offsets and slices match the containing sentence fragment rather than
only the full-source invariant.

The failure property will parameterize the fake backend with each accepted
controlled failure leaf: unavailable, timeout, and invalid response. The fake
raises its ordinary backend error with intentionally unsafe message/context
fixtures. Both pipeline entry points must raise the same accepted public error
type, code, retryability, and canonical `{operation, backend}` context. The
test will assert the canonical diagnostic does not include generated text or
the unsafe backend fixture. This exercises pipeline error translation without
depending on its private helpers.

The replay/budget property will generate the default run twice and require
identical replay metadata and generated parity signatures, exactly 64 cases,
and a supported family union equal to #123's `UNICODE_FAMILIES`. Failure output
will use only `assert_structural_invariant()` with a safe invariant name and a
case replay identifier. No assertion or test-double representation may format
the generated source text.

## Alternatives considered

Using `Analyzer` would couple the property to its configured production rules
and mock-heuristic backend, making canonical ordering and failure fixtures less
direct and potentially broadening the runtime surface. Calling the pipeline
with narrow deterministic protocol fakes exercises the public composition
boundary directly and remains offline.

Extending production code with a parity helper or exposing pipeline internals
would expand public behavior without a runtime consumer. It is rejected. A
new property-testing dependency or unbounded randomness would duplicate #123's
accepted replay contract and is also rejected.

## Test design and failure handling

The RED test deliberately references the absent `_assert_generated_success_parity`
test-local safeguard. The named regression is a sync/async divergence in
normalized results, ordering, translated offsets, or controlled failure
translation that authored examples do not cover. After the expected NameError,
the minimal test-local fakes and assertions will be added; `src/` remains
unchanged.

Expected canonical order is derived from literal spans and sources created by
the fakes, not by reusing the production sorting implementation. Fake backend
findings are returned in reverse local order so a lost normalization step is
observable. The fakes are specific to their input and failure mode, while all
assertions target returned findings or public exceptions rather than fake call
counts.

If the generated guardrail exposes a production defect, this issue stops after
recording only replay and structural metadata. A separate regression-first bug
issue is required; this issue must not repair the defect.

## Scope and non-goals

The properties preserve the public/error contracts from ADR-0003, the runtime
composition ownership from ADR-0018, offline privacy, canonical finding order,
and Unicode code-point offsets. They make no linguistic-quality claim and do
not replace authored pipeline, analyzer, or protocol regressions.

No production file, dependency, model/backend integration, retry policy,
corpus, holdout, evaluation, Fast-CI configuration, #119 work, or unrelated
refactor is allowed. The test module runs within the normal fast test suite.

## Self-review

- The design maps successful parity, canonical order, fragment-to-original
  offset translation, controlled failure parity, deterministic replay/budget,
  and offline-only execution to explicit properties.
- Generated text is used solely as pipeline input and slice-oracle data; no
  failure path renders it.
- The design relies on accepted #123/#124/#125 contracts and adds no competing
  generator, public interface, or production behavior.
