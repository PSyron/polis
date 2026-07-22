# ADR-0015: Qualify deterministic contextual inflection routing

- Status: Accepted
- Date: 2026-07-22
- Owner: Paweł Cyroń
- Issue: #71

## Context

ADR-0010 established complete finite-candidate recall for LanguageTool Polish
synthesis but did not identify targets or select forms in context. ADR-0013
therefore measured zero contextual inflection edits. Issue #71 adds a
sentence-only detector for closed government and adjacent-name agreement, then
selects only a unique finite form satisfying complete morphological tags.

The existing candidate contract merges features across analyses of the same
surface. That loses correlations such as case and gender. A separate
`synthesize_context` operation now preserves complete tags while leaving the
existing `synthesize` response and identifiers unchanged. Routing still uses
only source text, token spans, and local morphology. Gold remains scorer-only.

On 69 development sentences the frozen route produced 13 exact edits and no
false positive, changed no protected negative, and reached supported recall
0.619. Warm p95 was 3.84 ms and peak RSS was about 340 MB. On the one permitted
142-sentence holdout it produced 10 exact edits and no false positive, changed
no protected negative, and reached supported recall 0.667. Warm p95 was 4.19
ms and peak RSS was about 327 MB.

Surname agreement was the strongest holdout slice at recall 0.714. First-name
selection correctly abstained on ambiguity. Overall holdout target detection
was only 0.333 because most government and agreement patterns remain outside
the closed detector.

## Decision

Qualify the frozen contextual router as a local, sentence-only suggestion
source. Preserve its exact four evidence kinds, tag-correlated selection,
finite-candidate provenance, and abstention rules. Do not enable it in the
analyzer or automatic source policy in #71.

Create a focused integration issue for the suggestion path. Automatic
correction requires a separate policy decision even though the measured edits
met precision 1.00, because name inflection is sensitive and target coverage is
narrow.

After deterministic punctuation (#72) and contextual inflection are integrated,
a narrowly scoped residual syntax run with the smallest previously credible
MLX model is justified. A broad model matrix is not: #69 already established
Qwen3 1.7B MLX as the only compact candidate with exact syntax true positives.

## Consequences

- #43 gains a qualified deterministic inflection source but remains fail-closed
  until integration and residual syntax evidence are complete.
- The new context synthesis operation remains experimental and local.
- First names, unsupported agreement, most government relations, and all
  paragraph behavior continue to abstain.

## Alternatives considered

- **Use merged features for selection.** Rejected after development showed that
  feature unions lose grammatical correlations and can hide a needed edit.
- **Accept two dative forms for a first name.** Rejected because ambiguity must
  abstain.
- **Broaden lexical government after holdout.** Rejected because the one-shot
  holdout cannot tune the frozen route.
