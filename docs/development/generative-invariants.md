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

## Fast CI contract and safe replay

Every supported Fast CI matrix job supplies the complete generated-invariant
configuration on the existing `Run pytest suite` step:

```yaml
env:
  POLIS_GENERATIVE_GENERATOR_VERSION: unicode-structural-v1
  POLIS_GENERATIVE_SEED: 95001
  POLIS_GENERATIVE_CASES: 64
```

That step retains its single filtered pytest command, so research, slow, and
model tests remain excluded. The test-only no-argument generator consumes these
values: with no configuration it uses its existing defaults; when any value is
present it fails closed unless all three values are present, the version is
exact, the seed is an unsigned 64-bit integer, and the budget is from 1 through
256. The Fast CI workflow policy further pins the accepted version, seed, and
64-case budget, rejects missing, duplicate, misplaced, invalid, or excessive
metadata, and retains the existing 10-minute job timeout on every supported
matrix job.

To replay a structural failure, retain only the safe metadata in its failure
message (`generator`, `seed`, and `case`) and run the affected property module
with the same complete configuration. For example, a failure reported as
`generator=unicode-structural-v1 seed=95001 case=7` in segmentation can be
replayed without putting text into the command or output:

```console
POLIS_GENERATIVE_GENERATOR_VERSION=unicode-structural-v1 POLIS_GENERATIVE_SEED=95001 POLIS_GENERATIVE_CASES=64 uv run --locked --extra dev pytest tests/test_segmentation_properties.py -v
```

The 64-case budget is intentional: it includes the reported case while also
retaining coverage of every declared family. Do not reduce it to a case index
or copy generated text, source fragments, prompts, or analyzed documents into
a command, CI log, issue, or report.

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

## Completed structural invariants and residual risks

The completed #95 child suites use the same synthetic 64-case source for:

- paragraph and sentence segmentation bounds, contiguity, slices, coverage,
  and exact reconstruction;
- public finding/result bounds, original slices, normalization, stable IDs, and
  canonical JSON fidelity;
- correction conflict symmetry, deterministic normalization, right-to-left
  application, and fail-closed invalid selections;
- rule-registry ordering, duplicate handling, and synchronous/asynchronous
  registration parity; and
- synchronous/asynchronous analysis-pipeline result, offset translation, and
  controlled-failure parity.

Together these checks provide structural evidence over all eight catalogued
families: `ascii`, `polish_diacritics`, `non_bmp`, `combining_marks`, `lf`,
`crlf`, `punctuation`, and `quotes`. They do not establish exhaustive Unicode
coverage, Polish grammar, spelling, style, recall, precision, or corpus
performance. Authored regressions and versioned corpus gates remain the
authoritative linguistic evidence. The bounded generator has no shrinking,
does not use live models or holdouts, and can miss interactions beyond its
synthetic catalog; any discovered defect requires a separate regression-first
issue.

## Correction properties

Issue #129 applies the same 64-case synthetic source to correction conflict
and application properties. Its independent ADR-0003 oracle checks symmetric
conflicts for overlapping replacements, duplicate insertions, and an insertion
at every closed boundary of a replacement. A digest derived from each replay
identity varies compatible replacement, deletion, and insertion positions
while retaining insertions strictly outside replacements. Every non-empty
selected subset must normalize deterministically, apply independently of every
selected-ID order, and equal a separately derived right-to-left reconstruction.

The property also submits conflicting, stale, unknown, duplicate, and
uncorrectable selections. Each must fail before output, leave the immutable
result unchanged, and report a failing property through only its invariant and
the #123 replay metadata. This is bounded structural contract coverage, not a
claim about correction quality, corpus performance, models, or evaluation.
