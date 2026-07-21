# Specialist correction contracts

This document defines evaluation-only contracts used by specialist-model correction
flows. These contracts are intentionally narrow and do not authorize automatic
text application.

## Shared constraints

- Input text and candidate data are always treated as data inside explicit
  delimiters, not as free prompt instructions.
- Prompts use separate system and user messages.
- Response schemas are versioned and strictly validated.
- No model output that is not valid JSON for the requested schema is accepted.
- Private text is kept out of exception diagnostics.

## Corrected-text operation (`specialist-corrected-text`)

`build_specialist_corrected_text_prompt_request(text, focus)` builds a prompt with:

- protocol id: `specialist-corrected-text`
- protocol version: `1.0`
- system focus: exactly one of `inflection`, `syntax`, `punctuation`
- response schema version: `1`
- response schema:

```json
{"required":["corrected_text"],"type":"object","properties":{"corrected_text":{"type":"string"}},"additionalProperties":false}
```

Failure modes:

- Missing/extra top-level fields.
- Too many rewrite spans.
- No token overlap with source text.
- Response type mismatch.

## Inflection candidate-selection operation (`specialist-candidate-selection`)

`build_inflection_candidate_prompt_request(text, candidates)` expects either:

- `{"unchanged": true}`
- `{"candidate_id": "..."}`

where `candidate_id` must be supplied by the caller and must belong to the
provided candidate list.

Failure modes:

- Duplicate/missing candidate IDs.
- Candidate IDs not in the provided set.
- Invalid payload shape.

## Proposal-verifier operation (`specialist-proposal-verifier`)

`build_proposal_verifier_prompt_request(source_text, proposal_text)` accepts only:

- `{"decision": "accept"}`
- `{"decision": "reject"}`

Failure modes:

- Invalid decision value.
- Extra fields in response.

## Derived edits

`derive_text_edits(source_text, corrected_text)` converts model output into
deterministic non-overlapping byte/Unicode spans. It rejects overlapping,
excessive rewrite spans, and edits touching protected name-like tokens.

These operations remain separate from the general LLM backend contract and are used
only by the specialist path.
