# ADR-0009: Do not qualify a specialist prompt protocol

- Status: Accepted
- Date: 2026-07-21
- Owner: Paweł Cyroń
- Issue: #57

## Context

ADR-0008 permits local-model output only as reviewable suggestions and requires
specialist prompt experiments before any production adapter. The experiment
compared exact findings, corrected text, category-specialist corrected text,
and proposal verification. Finite candidate selection remains unsupported
until #58 supplies candidates independently of evaluation labels. Source text
remained delimited user data, while Polish instructions and schemas used
separate chat roles. The request budget was one call for unchanged text and at
most two calls for a proposed change.

Development contained 80 independently reviewed cases. Qwen3 1.7B and Bielik
1.5B Q8_0 ran the corrected-text matrix through Ollama 0.20.7. Bielik 4.5B
Q8_0 ran the selected specialist protocol as a larger quality control. Exact
artifacts, commands, prompt contracts, and metrics are documented in the
experiment README.

## Decision

No specialist prompt protocol qualifies for hybrid suggestions or automatic
correction.

Qwen3 1.7B specialist punctuation was the only development slice satisfying
the suggestion gates, with edit precision 1.000, recall 0.706, 100% valid
responses, and no false changes in that slice. It was therefore selected for a
single unchanged-prompt holdout run. The corpus was frozen first at SHA-256
`bd2c186bb22e32f948ed6592c24bc2267c6a2a77b185bd9424310068e680a1f2`.

On 160 holdout cases the selected protocol returned 160/160 valid responses,
but changed nine protected negatives. Punctuation precision was 0.889 with two
false positives, below the required 0.90; overall edit precision was 0.727.
Inflection produced no exact edits, while syntax precision was 0.667. The
holdout result is final for these prompt versions and did not trigger prompt
tuning.

## Consequences

- #59 may preserve the versioned contracts as experimental interfaces, but
  their output remains unqualified and suggestion-only.
- #60 must keep deterministic findings independent from optional model failure
  and must not treat verifier acceptance as permission to apply an edit.
- #62 may use the selected narrow corrected-text shapes for licensed training
  records without copying evaluation cases, entities, or templates.
- #63 must compare a fine-tuned adapter against this frozen prompt-only
  baseline and the unchanged holdout gate.
- #43 remains blocked from adding a production model backend until a later
  candidate passes validity, precision, and protected-negative requirements.
