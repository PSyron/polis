# Generated Rule Registry Properties Design

## Context

Issue #128 is the rule-registry child of tracker #95. The existing authored
registry tests remain the authority for individual registration and validation
examples. This issue adds a bounded, deterministic structural guardrail over
the test-only Unicode/replay harness delivered by #123. It must leave the
public `RuleRegistry` protocol, `DeterministicRuleRegistry`, and all production
rule behaviour unchanged.

## Settled design

One test module consumes the 64 default synthetic cases from
`tests.generative.generate_unicode_text_cases()`. It derives a finite registry
shape from each case's replay metadata, never from its text: every shape has a
small ordered set of fake `Rule` implementations, one declared category per
rule, and one or more synthetic findings per rule. Source identifiers, category
subsets, and registration orders are safe structural values. The fake rules
are exercised through the real `DeterministicRuleRegistry` methods.

For every generated shape, the test independently derives the expected source
and finding sequences from its local registration data. It checks:

1. `rules()` returns each configured registration order exactly and repeatedly;
2. `selected_rules()` returns a requested category subset containing at least
   two rules while excluding at least one registration, in relative configured
   order and repeatedly;
3. `find()` returns the selected rules' findings in that same relative order,
   preserving each rule's own deterministic emission order, and repeatedly;
4. several deterministic permutations of the same registrations produce the
   corresponding configured order, rather than a source-sorted or hash/set
   order; and
5. the generated run still declares every #123 Unicode family.

The expected values are created from the test-local specifications and literal
category catalogue, not by registry helpers, `rules()`, `selected_rules()`, or
`find()`. Selected-rule order, execution order, cross-rule finding-source order,
and within-rule finding-ID order are asserted independently. This makes a
reordering mutation observable. The test uses small ordered sequences and
stable tie-breakers rather than depending on set or dict iteration.

The same module makes each generated failure mode fail closed through the real
registry: duplicate registered sources raise `DuplicateRuleSourceError`, a
rule emitting the same finding twice raises `DuplicateFindingError`, and
incompatible emitted source or category raises `IncompatibleRuleOutputError`.
Each negative property records only a stable `registry.<property>.<invariant>`
identifier and its #123 replay metadata. Missing errors, wrong registry-error
types, and unexpected exceptions are converted to this common structural
failure without rendering exception text. The test passes synthetic case text
to `find()` only to exercise the real signature, then separately asserts that
every accepted error message omits that text. Finding sources, categories, and
opaque finding identifiers are structural diagnostic data; text, fragments,
and suggestions are not accepted diagnostic content.

## Alternatives considered

Adding more authored order examples would not cover bounded combinations of
category selection and registration permutation. Adding a property-testing
dependency would duplicate #123's rejected dependency and broader failure
surface. Changing the registry to expose replay configuration would expand a
public or production surface without a current consumer. The selected
test-local generator is the smallest direct consumer of the approved #123
harness.

## Scope and non-goals

No registry API, production implementation, category semantics, duplicate
policy, corpus, holdout, model evaluation, dependency, or linguistic rule may
change. The tests use synthetic offline rules and findings only. They provide
structural evidence rather than linguistic-quality evidence and do not replace
the authored registry/protocol tests. If a property reveals a production
registry defect, this issue stops with its safe replay metadata for a separate
regression-first bug issue; it does not repair the registry here.

## Test design and privacy

The RED test introduces calls to the absent generated-property helpers, so it
fails before any helper exists. The protected mutations include sorting entries
by source, using an unordered collection for selection or accumulation,
executing in a different order, returning the wrong subset order, permitting a
duplicate, and accepting an incompatible finding. The privacy regression uses
a generated case as the input sentinel and proves that every generated error
path contains the invariant identifier and replay metadata but not that input.

## Self-review

- The design maps every #128 acceptance criterion to a bounded test property.
- Expected order is derived outside the registry and every executed rule is a
  real `Rule` protocol implementation.
- All diagnostics are replay-safe structural metadata; no generated text is
  interpolated into an assertion failure.
- The scope is one test module plus this design and its implementation plan;
  no production behaviour can be changed by the planned work.
