# Sentence safety corpus v2 role-review checklist

This checklist governs all 240 records in
`polis_polish_correction_safety_corpus_v2`. Candidate generation and automatic
validation cannot grant approval. Under the accepted clarification in issue
#119, the `Polis architecture owner` role may approve the complete candidate
digest and change records from `pending-human-review` to `human-reviewed`.
The role record is an authorization boundary, not personal attribution.

Review the canonical JSON file. For every record, confirm each item below
before recording all-case approval.

## Correctness

- The input is a plausible Polish sentence and contains the declared problem,
  or is wholly correct when the stratum is `hard_negative`.
- The expected output is grammatical and preserves the original meaning,
  register, capitalization, and unaffected formatting.

## Category

- The declared stratum is the primary phenomenon exercised by the case.
- Positive cases belong to exactly one of `inflection`, `syntax`, or
  `punctuation`; protected cases belong to `hard_negative`.

## Minimality

- Every positive expected output changes only the smallest justified fragment.
- The suggestion does not rewrite correct surrounding text.
- Every hard negative has no edit and keeps the input unchanged.

## Offsets

- Every edit uses a half-open Unicode `[start, end)` range in the original
  input.
- `input[start:end]` exactly equals the recorded original fragment.
- Entity spans cover exactly the recorded controlled surface.

## Reconstruction

- Applying the declared edit to the original input reconstructs the expected
  output exactly.
- Edits do not overlap and do not depend on a previously modified string.

## Proper-name behavior

- Personal and place names retain intentional spelling, capitalization, and
  inflection.
- Every controlled name surface has a complete entity span and canonical
  identifier.
- No ordinary capitalized sentence-initial word is mislabeled as an entity.

## Syntax and word order

- Subject–predicate agreement, government, negation, and quantification are
  evaluated in the full sentence context.
- Marked but grammatical word order is not normalized merely for style.

## Provenance

- The sentence is project-authored synthetic Polish created for issue #119.
- It was not copied, paraphrased, or derived from corpus v3, safety corpus v1,
  prompt examples, fine-tuning assets, E2E fixtures, or private text.

## Licensing

- The case may be released under CC0-1.0.
- No third-party quotation, dataset record, or restricted text is embedded.

## Isolation

- The development/holdout assignment remains unchanged during review.
- The case introduces no reused input, normalized template, entity
  combination, canonical entity identifier, or near-duplicate linguistic
  family from a reserved asset.
- Case-level safety-corpus-v1 holdout content or outcomes did not inform the
  candidate.

## Approval and freeze

Approval is all-or-nothing and must name:

- corpus ID `polis_polish_correction_safety_corpus_v2`;
- all 240 cases;
- candidate canonical JSON SHA-256;
- reviewer role `Polis architecture owner`;
- ISO-8601 review date;
- checklist version `safety-corpus-review-v2`.

Do not create the approval manifest, set `holdout_state` to `frozen`, add
`human-reviewed` metadata, or record a frozen digest until every case passes
this checklist. This review produces no development or holdout quality score
and does not authorize holdout access.

## Recorded approval

The `Polis architecture owner` completed the exhaustive all-case review on
2026-08-02 using checklist version `safety-corpus-review-v2`. Approval binds
candidate canonical JSON SHA-256
`c64f009f14f0cde8390a46acc24660305534576bc897f70e281ffebbbbca6f53`
to frozen canonical JSON SHA-256
`53cfce6b9cbe3f188290a064b34527912ea8f2a85c9ed29a67984c5ef5caaa29`.
The approval covers all 240 cases and produces no development or holdout
quality score.
