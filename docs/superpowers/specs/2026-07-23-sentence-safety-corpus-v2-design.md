# Sentence Safety Corpus v2 Design

## Authority and goal

GitHub issue #119 is the authoritative specification. This design records the
implementation boundary for a second independent, owner-reviewed sentence
safety corpus used to re-qualify #76 after the valid but non-qualifying #115
one-shot run.

The deliverable is `polis_polish_correction_safety_corpus_v2`: 240
project-authored CC0-1.0 Polish sentences divided equally across inflection,
syntax, punctuation, and protected hard-negative strata. Each stratum contains
20 development and 40 holdout cases. The issue creates and freezes the corpus;
it does not analyze, score, or tune against either split.

## Architecture

`polis.evaluation.safety_corpus` remains the shared validator. Its current v1
public constants and default behavior stay compatible. An internal immutable
policy selected from the corpus identifier supplies the checklist version,
controlled entity surfaces, and canonical entity overrides for v1 or v2.
Schema, offset, edit, reconstruction, review, balance, isolation, digest, and
purpose-selection logic stays shared.

The v2 generator is separate from the v1 generator. It contains only v2
project-authored case specifications and mechanical transformation code. It
may reuse the shared validator and serialization conventions, but it must not
import v1 linguistic specifications. Before writing fixtures it mechanically
checks v2 against corpus v3, safety corpus v1, fine-tuning assets, prompt
examples, and E2E fixtures using closed `IsolationRecord` values.

Canonical JSON is the source of truth. XML is generated and tested for semantic
equivalence. A separate approval manifest binds the candidate digest to the
all-case review performed by the authorized `Polis architecture owner` role.
The role record is not personal attribution. Until that approval exists,
generation produces only `unfrozen-candidates` with `pending-human-review`
metadata and quality-gate selection remains unavailable.

## Independence and immutability

V2 inputs, normalized templates, canonical entity identifiers, entity
combinations, and near-duplicate linguistic families must be isolated both
across its own splits and from every reserved asset. Cross-asset comparison is
automatic; authoring does not inspect or reuse case-level v1 holdout content or
outcomes.

Tests pin the existing v1 JSON, XML, approval manifest, frozen gate marker, gate
configuration, and retained report bytes by SHA-256. V2 work cannot change
those artifacts. The package build continues to exclude evaluation JSON/XML
fixtures from source distributions.

## Review and freeze flow

The candidate generator first produces all 240 pending cases and validates
their exact balance, offsets, reconstruction, provenance, controlled entities,
JSON/XML equivalence, and reserved-asset isolation. The v2 review checklist
then guides the `Polis architecture owner` through every case.

Only explicit owner approval may create the approval manifest. The generator
verifies the candidate digest, reviewer, review date, checklist version, case
count, and final frozen digest before applying `human-reviewed` metadata and
`holdout_state = "frozen"`. No command in this issue opens a holdout or emits a
quality score.

## Verification

Red-green tests cover corpus identity, policy routing, v1 compatibility,
catalog disjointness, exact balance, access restrictions, digest sensitivity,
JSON/XML equivalence, cross-asset leakage, artifact immutability, review
binding, documentation, and packaging exclusions. Completion additionally
requires the full fast pytest suite, Ruff lint and format checks, strict mypy,
package build, distribution-content tests, and a clean diff.
