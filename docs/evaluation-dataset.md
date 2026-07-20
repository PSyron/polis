# Polish Evaluation Dataset

`src/polis/evaluation/datasets/v1/cases.json` is the initial small, versioned
quality dataset for Polis. It is a reviewable gold set, not a corpus and not a
claim about production coverage. The validator in `polis.evaluation.dataset`
accepts only schema version 1 and rejects unknown fields so changes to the
contract require an explicit schema version.

## Schema and interpretation

The dataset object has `schema_version`, a stable `id`, dataset `provenance`,
and `cases`. Each case has a lowercase snake-case `id`, an `outcome`, source
`text`, its own `provenance`, and `expected_findings`. The closed finding shape
is:

```json
{
  "category": "spelling",
  "start": 8,
  "end": 15,
  "original": "napewno",
  "suggestion": "na pewno",
  "rationale": "The standard Polish expression is written as two words."
}
```

Offsets are Python Unicode code-point indices over the unmodified input, using
the half-open interval `[start, end)`. The validator requires that
`text[start:end]` equal `original`. A non-empty suggestion is an insertion when
`start == end`; an empty suggestion is a deletion only when `original` is
non-empty. Every correction must differ exactly from its original fragment.

Expected findings must be deterministic when applied from right to left against
the original offsets. Non-empty replacement ranges cannot overlap. Two
insertions at the same offset are rejected because their order is ambiguous.
An insertion is also rejected at the start of or strictly inside a non-empty
replacement range. An insertion exactly at that range's end is allowed: it is
applied first and remains after the replacement. Insertions outside replacement
ranges are allowed.

`outcome: "incorrect"` requires one or more expected findings. `outcome:
"correct"` is an explicit hard negative and must contain exactly
`"expected_findings": []`; it does not mean that arbitrary style preferences
are errors. Categories are exactly the public `Category` values: `inflection`,
`agreement`, `syntax`, `spelling`, `punctuation`, and `style`.

## Provenance, licensing, and review

Every dataset and case provenance object records its source, `CC0-1.0` license,
creation date, review status, and notes. The committed cases are
project-authored synthetic Polish examples and are marked `human-reviewed`.
CC0-1.0 lets downstream evaluators reuse the examples while the provenance
still makes their origin and review boundary auditable.

Never add private, confidential, user-supplied, scraped, copied, or
corpus-derived text unless its provenance and redistribution terms have been
reviewed in a dedicated change. Remove direct identifiers and quasi-identifiers
through anonymization before proposing any real-world material, but prefer new
synthetic examples whenever possible. Do not include model-generated text as
gold data: it cannot establish an independent quality target. A maintainer must
perform human review of grammar, category, exact Unicode offsets, fragment,
minimal correction, and hard-negative status before changing this dataset.

Contributions must preserve the strict schema and add adversarial validator
tests whenever a new invalid state becomes possible. Add difficult no-finding
examples alongside nearby error cases to guard against false positives. Keep
each case small enough for linguistic and licensing review.

## Boundary with the dependency experiment

`experiments/nlp_dependencies/cases.json` remains a separate, CC0 diagnostic
dependency benchmark. Its tokenization and morphology probes measure candidate
tool capabilities; they are not copied here and must not be treated as
evaluation gold labels or release thresholds. This dataset supplies the later
quality work with independently reviewed expected findings without conflating
that experiment with analyzer accuracy.

## Validation

Run the fast integrity checks with:

```console
uv run --locked --extra dev pytest tests/test_evaluation_dataset.py -v
```

The standard-library validator is also available to callers as
`polis.evaluation.validate_dataset(raw)` and `polis.evaluation.load_dataset()`.
It validates untrusted candidate JSON before it is accepted as a project asset.
