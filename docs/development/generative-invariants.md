# Deterministic structural invariants

Issue #123 provides the shared, test-only generator required before the
structural-property children of issue #95. It uses a repository-owned,
versioned SHA-256 index rather than a mutable random stream: every synthetic
case follows from its generator version, seed, and case index, so it can be
replayed independently on every supported platform.

## Bounded generator contract

The current generator is `unicode-structural-v1`. Its default seed is `95001`,
its default budget is 64 cases, and its hard maximum is 256 cases. The
supported Unicode families are:

- `ascii`
- `polish_diacritics`
- `non_bmp`
- `combining_marks`
- `lf`
- `crlf`
- `punctuation`
- `quotes`

For example, a property failure that reports
`generator=unicode-structural-v1 seed=95001 case=7` identifies the case to
select from `generate_unicode_text_cases(seed=95001, count=8)[7]`. The replay
metadata deliberately identifies the case without printing its text.

## Rejected alternatives

Hypothesis was not selected because it would add and govern a development
dependency before this repository has a consumer for shrinking or persisted
examples. Its counterexample reporting is also broader than this helper's
seed-only failure contract.

`random.Random` was not selected because a mutable pseudo-random stream would
require pinning the full call sequence to make drift explicit. It does not give
the independently indexed replay contract supplied by the SHA-256 derivation.

## Safe failures and scope boundary

Every generated structural property must call
`assert_structural_invariant(condition, invariant=..., replay=...)` with a
safe invariant identifier. A false condition reports only that identifier and
replay metadata; generated text must not appear in object representations or
failure messages.

These generated structural invariants provide bounded structural breadth only.
They do not replace authored regression tests or corpus gates, and they make no
claim about Polish linguistic quality. The harness must not receive private
text, run model or holdout evaluation, or become unbounded CI fuzzing.
