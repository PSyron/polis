# ADR-0014: Qualify four broader Polish LanguageTool sentence rules

- Status: Accepted
- Date: 2026-07-22
- Owner: Paweł Cyroń
- Issue: #70

## Context

ADR-0013 found that the existing two-rule LanguageTool subset produced one
exact punctuation edit at precision 1.00 but recall 0.038. The best compact
model route added syntax true positives but failed the precision and recall
gates. Issue #70 therefore inspected the full upstream Polish LanguageTool 6.8
rule output without changing the production `check` operation.

Inspection received only source sentences. Gold edits remained scorer-only,
all offered replacements counted, UTF-16 offsets were converted to Unicode
code-point half-open ranges, and combined candidates were rejected on edit
conflicts, invalid application, any false positive, or any protected-negative
change.

On 69 development sentences, four rule IDs produced 4 true-positive and 0
false-positive edits with no conflicts or protected changes. The allowlist,
configuration, corpus, and Java bridge were frozen before the one permitted
holdout run. On 142 holdout sentences it produced 5 true-positive and 0
false-positive edits, changed no protected negative, and retained precision
1.00. Holdout recall was 0.038. Warm p95 was 5.9 ms, peak RSS was about 355 MB,
and built runtime size was about 54 MB.

## Decision

Qualify these deterministic sentence rule IDs as candidates for a separate
production source-policy update:

- `BRAK_PRZECINKA_KTORY`
- `BRAK_PRZECINKA_SPOJNIK_PROSTY`
- `BRAK_PRZECINKA_ZE`
- `WOLACZ_BEZ_PRZECINKA`

Keep the production allowlist unchanged in #70. Enabling the rules requires a
focused implementation issue with regression tests and explicit source-policy
versioning. Do not generalize qualification to LanguageTool categories or to
other rules.

## Consequences

- Deterministic punctuation can gain safe but narrow sentence coverage.
- The result does not qualify a compact model and does not solve syntax or
  contextual inflection.
- #43 remains fail-closed until the qualified rules are integrated and the
  residual sentence path meets its gates.
- #71 remains the next independent deterministic investigation for contextual
  inflection.
- Paragraph behavior is not evidenced by this decision.

## Alternatives considered

- **Enable every punctuation-category rule.** Rejected because qualification is
  per rule ID, not per upstream category.
- **Accept `BRAK_PRZECINKA_CZY` or `ZWROTNE_BEZ_SIE`.** Rejected because each
  had development precision 0.50.
- **Skip holdout due to low recall.** Rejected because the non-empty development
  selection met every frozen safety gate and required independent validation.
