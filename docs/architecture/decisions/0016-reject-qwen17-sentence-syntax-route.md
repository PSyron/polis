# ADR-0016: Reject the Qwen3 1.7B sentence syntax route

- Status: Accepted
- Date: 2026-07-22
- Owner: Paweł Cyroń
- Issue: #74

## Context

ADR-0013 rejected a three-model sentence matrix but identified Qwen3 1.7B MLX
4-bit as the only compact candidate with exact residual syntax edits. Issues
#72 and #73 subsequently added qualified deterministic punctuation and
contextual inflection paths. Issue #74 therefore tested one narrow model and
three materially different operations on individual sentences: the #69
baseline, an evidence-specific proposal plus verifier, and a separate diagnosis
followed by correction.

The frozen development set contained 69 corpus-v3 sentences. Routing and prompt
construction saw only source evidence; gold remained scorer-only. The exact
artifact was `mlx-community/Qwen3-1.7B-4bit` revision
`3b1b1768f8f8cf8351c712464f906e86c2b8269e`, served by MLX-LM 0.31.3 and
MLX 0.32.0 with thinking disabled on the M4 Mac mini. Configuration SHA-256 was
`9858f54577af201f9f4c134fc49e4498f32158dd0b1b2ca724a94957f6dca1f8`.

The baseline produced 4 TP, 3 FP, and 21 FN syntax edits: precision 0.571 and
recall 0.160. The evidence checklist produced 1 TP, 0 FP, and 24 FN: precision
1.000 but recall 0.040, with only 67/69 valid responses. Diagnosis followed by
correction produced 2 TP, 1 FP, and 23 FN: precision 0.667 and recall 0.080.
All variants changed zero protected negatives, used at most two calls, added no
swap, used about 1.327 GB RSS, and stayed below 1.1 seconds warm p95.

## Decision

Reject all three exact Qwen3 1.7B configurations for production suggestions.
No variant passed response rate 1.00, syntax precision 0.90, and syntax recall
0.25 together. Do not freeze a winner and do not open corpus-v3 holdout.

Keep #43 blocked. Do not spend another run on general prompt decomposition for
this model without a materially narrower output space. The next permitted
sentence work is deterministic high-precision syntax coverage or finite,
source-derived candidate selection. A larger model remains a separate decision
only if those smaller paths cannot cover the required sentence behavior.

## Consequences

- Multiple prompts do not by themselves make the 1.7B model dependable.
- Evidence-specific prompting can improve precision by abstaining, but its
  measured recall is not useful enough for the product.
- Sentence latency and memory are acceptable; quality, not model size or MLX
  performance, is the blocker.
- Paragraph behavior remains unevaluated and unsupported by this decision.

## Alternatives considered

- **Lower precision or recall gates.** Rejected because it would authorize
  known false suggestions or nearly universal abstention.
- **Open holdout for the precision-1.00 checklist.** Rejected because its
  development recall and response validity fail predeclared gates.
- **Try more unrestricted prompts.** Rejected because three operations now show
  the same quality ceiling and #69 already tested the broader matrix.
