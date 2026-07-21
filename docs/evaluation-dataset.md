# Polish Evaluation Dataset

Fine-tuning data is maintained separately under
`data/finetuning/bielik_1_5b_v1`. Corpus v3 remains evaluation-only and its
records, normalized templates, entities, and expected outputs are prohibited
from training. See `docs/architecture/finetuning-dataset.md` for the isolation
contract.

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

## E2E LLM correction corpus

`tests/fixtures/e2e/polish_correction_corpus.json` and its XML counterpart are
also project-authored, synthetic Polish examples released as CC0-1.0. The
LLM-planned records cover exact minimal corrections; the negative records are
hard safety checks for correct names, surnames, punctuation, and grammatical
marked word order. JSON is the source used by the local-model benchmark, while
the XML fixture is kept equivalent for interchange and regression testing.

## Polish correction corpus v3 candidates

`tests/fixtures/evaluation/polish_correction_corpus_v3.json` is the canonical
schema-v3 candidate set. Its XML counterpart is an equivalent interchange
representation. It is physically separate from the rule-only E2E fixture and
from every future training asset.

The corpus declares four strata with 60 cases each: inflection, syntax,
punctuation, and protected hard negatives. Each stratum has 20 development and
40 holdout cases. After all 240 cases completed owner review, the top-level
`holdout_state` was set to `frozen` before the first quality-gate run. Pending
candidates are not evaluation gold, cannot enter a benchmark or quality gate,
and cannot be used for training.
Before that transition, any `pending-human-review` case required the corpus to
remain `unfrozen-candidates`; this state is still enforced for future corpus
versions under review.

Every case records CC0-1.0 provenance, a review object, exact proper-name
entity spans, canonical entity identifiers, a derived normalized sentence
template, exact Unicode edits, and either a positive expected output or one
named protected phenomenon. A template is deterministically rebuilt from the
input by replacing spans from the controlled entity-surface catalog with
`<entity>`, applying Unicode NFC case folding and whitespace normalization, and
replacing URLs and numbers with fixed markers. Every detectable catalog surface
must be spanned. Declension variants of one person map to one canonical
identifier; arbitrary capitalized words, template markers, identifiers, and
omitted spans are rejected.

The validator rejects duplicate input, cross-split entity or
normalized-template leakage,
duplicate or near-identical template families in either split, including short
siblings separated by one token edit, invalid offsets, overlaps, reconstruction
errors, and JSON/XML drift.

Training isolation uses a closed record contract rather than the finite corpus
surface catalog. Each record must provide exact, ordered spans for every
deterministically detected name-shaped token group. Detection recognizes
title-case and all-capital forms and joins adjacent name-shaped tokens. Known
evaluation aliases are derived from each corpus entity surface and from
corrections inside that surface; they are recognized case-insensitively at
every sentence position, including a single initial token. Entity comparison
applies deterministic Unicode normalization and conservative Polish
case-ending normalization, so casing, erroneous corpus forms, and their
expected corrected forms retain one isolation identity. Templates are rebuilt
from the supplied, verified spans, which makes an unseen name in a reserved
sentence topology a collision. The evaluation corpus itself remains prohibited
as training data.

One deterministic ambiguity remains: a single sentence-initial capitalized
token that is not a known corpus alias is treated as ordinary sentence casing.
It may therefore be an unknown one-word proper name. Callers must provide a
span when they know that semantic fact, but the offline shape detector cannot
infer it from capitalization alone. Adjacent capitalized tokens and
unambiguous name-shaped tokens elsewhere are still mandatory.

Human review follows
[`evaluation-corpus-v3-review-checklist.md`](evaluation-corpus-v3-review-checklist.md).
Only Paweł Cyroń may change a case to `human-reviewed`. Development cases may
become available for benchmark experiments individually after approval.
Benchmark selection never exposes the intended holdout. Holdout cases remain
available only through the explicit quality-gate path after all cases are
approved and the holdout is frozen.

### Leakage and change control

Prompt examples and fine-tuning records must not reuse an evaluation input,
entity combination, or normalized template. Run the training-isolation
validator against closed-contract records before accepting any such asset. A
record with missing, extra, overlapping, out-of-order, or text-mismatched entity
spans is invalid. Do not copy candidates from v3 into a training directory,
even after review.

Before the first holdout run, approve every case, regenerate XML, set the state
to `frozen`, record the canonical JSON digest, and run all integrity checks.
After a frozen holdout has been scored, corrections require a new schema or
corpus version. This change control prevents benchmark-driven repair and keeps
reported evidence reproducible.

## Validation

Run the fast integrity checks with:

```console
uv run --locked --extra dev pytest tests/test_evaluation_dataset.py -v
```

Corpus-v3 candidate integrity is checked separately with:

```console
uv run --locked --extra dev pytest tests/test_correction_corpus_v3.py -v
```

The standard-library validator is also available to callers as
`polis.evaluation.validate_dataset(raw)` and `polis.evaluation.load_dataset()`.
It validates untrusted candidate JSON before it is accepted as a project asset.
