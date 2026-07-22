# Independent Sentence Safety Corpus Design

## Goal

Create the independent, owner-reviewed sentence corpus required by issue #114
without reopening or learning from the consumed corpus-v3 holdout. The result is
a schema-versioned CC0-1.0 evaluation asset containing 240 Polish sentences,
with a frozen 160-case holdout that is inaccessible to development workflows.

## Scope and constraints

The corpus contains exactly four strata: `inflection`, `syntax`, `punctuation`,
and `hard_negative`. Each stratum contains 20 development cases and 40 holdout
cases. All sentences are newly project-authored synthetic examples. Corpus-v3
records, results, and digests remain unchanged, and no holdout score is produced
by this issue.

Every case uses exact Python Unicode code-point offsets and half-open
`[start, end)` spans. Positive cases reconstruct one exact minimal correction;
hard negatives remain unchanged and name one protected phenomenon. Every case
records CC0-1.0 provenance and review metadata.

Only Paweł Cyroń may change a candidate from `pending-human-review` to
`human-reviewed`. Automated generation or validation must never impersonate
that review. The holdout can be frozen only after all 240 cases have passed the
documented case-by-case checklist.

## Architecture

The canonical JSON fixture is the source of truth. An equivalent XML fixture is
generated from it and checked for semantic equality. A focused
`polis.evaluation.safety_corpus` module reuses the stable schema-v3 value models
and low-level invariants from `correction_corpus` while enforcing the new corpus
identity, sentence-only unit policy, review checklist, controlled entity
catalog, digest, and access restrictions.

The safety entity catalog has new canonical identifiers and surfaces disjoint
from corpus v3. Cross-corpus validation converts external assets into a closed
`IsolationRecord` representation and rejects collisions by normalized input,
normalized template, canonical entity combination, or near-duplicate template
family. Checked sources include corpus v3, all fine-tuning JSONL records, prompt
examples embedded in project code and documentation, and both E2E fixtures.

Development selection exposes only individually approved development records.
Training selection is always prohibited. Quality-gate selection requires the
frozen state and returns only the 160 approved holdout records. No ordinary
development API loads holdout gold.

## Authoring and review flow

Cases are authored as explicit data, not created at test runtime. Small helper
code may perform mechanical offset, template, XML, and digest generation, but
the committed Polish inputs, outputs, rationales, tags, and protected
phenomena remain directly reviewable.

The first implementation phase prepares candidates as
`unfrozen-candidates`/`pending-human-review` only after all automatic integrity
and leakage tests pass. Paweł Cyroń then reviews every case against the safety
checklist. Rejected cases are corrected or replaced without moving another
case across splits. After all cases are approved, the second phase changes the
state to `frozen`, regenerates XML, records the canonical JSON SHA-256 digest,
and reruns the complete verification suite before the single issue commit.
Owner attribution is supplied by a separate approval manifest bound to the
candidate digest; candidate generation never synthesizes reviewer metadata.

## Validation and errors

Validation is fail-closed and rejects unknown fields, wrong corpus identity,
invalid balance, missing provenance, invalid or overlapping edits, incorrect
reconstruction, incomplete entity spans, duplicate identifiers, catalog
collisions, cross-split leakage, cross-asset leakage, duplicate families,
missing owner approval, premature freezing, training use, and premature
quality-gate access. Errors identify the violated invariant and record but do
not expose unrelated analyzed text.

The canonical digest hashes sorted-key, compact, UTF-8 JSON. Formatting-only
changes retain the digest, while any evaluated content or provenance change
changes it.

## Testing

Tests follow red-green TDD and cover the exact 240-case balance, complete review
and provenance metadata, JSON/XML equivalence, offset and reconstruction
adversaries, duplicate and near-duplicate families, cross-split entity and
template isolation, entity-catalog disjointness, cross-corpus and training /
prompt / E2E leakage, digest sensitivity, forbidden training use, development
holdout hiding, frozen-state enforcement, and the absence of a holdout score.

Final verification runs the focused safety-corpus tests, the full fast pytest
suite, Ruff lint and formatting checks, and strict mypy. Documentation records
the corpus identity, provenance, review procedure, frozen digest, relationship
to corpus v3 and #85, and the fact that #114 performs no gate run.

## Deliverables

- safety-corpus validator and public evaluation exports;
- canonical 240-case JSON and equivalent XML fixtures;
- adversarial integrity and leakage tests;
- owner-review checklist;
- evaluation, quality-gate, provenance, and limitations documentation updates;
- frozen canonical digest after owner approval;
- no analyzer, rule, evaluator, source-policy, or scoring behavior changes.
