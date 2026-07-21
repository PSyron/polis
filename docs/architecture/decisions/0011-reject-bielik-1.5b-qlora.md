# ADR-0011: Reject Bielik 1.5B QLoRA for the production backend

- Status: Accepted
- Date: 2026-07-21
- Owner: Paweł Cyroń
- Issue: #63

## Context

Issue #63 trained a narrow QLoRA adapter against the independent CC0 dataset
from #62. The exact Bielik 1.5B MLX 8-bit revision, MLX-LM runtime, prompt
contracts, seed, data hashes, and selection rule were fixed before the final
holdout. Model weights and raw responses stayed local.

The adapter fit comfortably on the 16 GB Apple M4 target. Training took 206.3
seconds, peaked at 2.617 GB of MLX memory and 1,971,175,424 bytes RSS, and caused
zero swap growth. Validation loss fell from 1.440 to 0.002. The 10.56 MB local
adapter reached perfect exact quality on the 240 synthetic validation records,
including under a minimal-prompt ablation.

The frozen 160-case corpus-v3 holdout did not confirm safety. The adapted arm
returned 152 valid responses, changed seven of forty protected hard negatives,
and achieved edit precision 0.833, recall 0.588, F1 0.690, and 108 exact complete
outputs. The predeclared gates require 160/160 valid responses, zero changed
protected negatives, and precision at least 0.90.

The holdout comparison used the corrected-text specialist for all focuses.
Issue #63 did not provide a gold-independent detector capable of generating the
finite inflection candidates required by the production protocol. The result
therefore rejects this configuration but does not qualify the finite-candidate
inflection path.

## Decision

Reject this Bielik 1.5B QLoRA adapter and reject the Bielik 1.5B prompt-only
configuration as candidates for the #43 production local-model backend.

Do not publish or bundle the adapter weights. The excellent synthetic
validation result is treated as task-shape fit, not production-quality evidence,
because the prompt ablation was equally perfect and the independent holdout
failed validity, safety, and precision gates.

## Consequences

- #43 cannot select Bielik 1.5B from this experiment and must remain fail-closed
  unless another already-evidenced configuration passes the same gates.
- The deterministic pipeline and suggestion-only model policy remain unchanged.
- A future training attempt requires a new issue, new independent data design,
  and a new frozen evaluation; tuning against the observed holdout is prohibited.
- The small adapter is practical in memory and latency, so model size is not the
  blocking problem. Generalization and protected-negative safety are.
