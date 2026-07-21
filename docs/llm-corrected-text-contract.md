# Specialist correction contracts

This document defines the versioned specialist-model correction contracts from
issue #59. ADR-0009 did not qualify any tested model, so these interfaces remain
experimental and suggestion-only. They do not authorize automatic application.

## Shared constraints

- Input text and candidate data are serialized as one canonical JSON object
  inside `<INPUT_JSON_START>` and `</INPUT_JSON_END>`, not concatenated as
  instructions. Literal angle brackets in data are Unicode-escaped so user text
  cannot terminate the envelope.
- Prompts use separate system and user messages.
- Prompt requests include explicit operational limits:
  - maximum input text size: `8192` characters,
  - corrected-text raw response: `16384` characters,
  - candidate-selection raw response: `512` characters,
  - verifier raw response: `128` characters,
  - corrected or proposed text value: `8192` characters.
- Response schemas are versioned and strictly validated.
- No model output that is not valid JSON for the requested schema is accepted.
- Private text is kept out of exception diagnostics.
- A runtime applies its model's official chat template to `messages`; the
  contract does not flatten roles or name a runtime or model.

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
- Raw or corrected-text length overflow.
- A rewrite overlapping caller-supplied protected source spans.
- A word change in punctuation focus or a non-word change in inflection focus.

`validate_corrected_text_response(raw, source_text=..., focus=...)` requires the
same explicit focus; callers cannot validate a response under an unspecified
specialist category.

## Inflection candidate-selection operation (`specialist-candidate-selection`)

`build_inflection_candidate_prompt_request(text, candidates)` expects either:

- `{"unchanged": true}`
- `{"candidate_id": "..."}`

where `candidate_id` must be supplied by the caller and must belong to the
provided candidate list.

All supplied candidates must describe the same positive source span. IDs and
forms are unique, lemma and feature values are typed and non-empty when present,
features are unique, offsets refer to the original Python string, and the
original surface form is included. Forms and morphology remain data only; their
presence does not claim contextual correctness.

Failure modes:

- Duplicate/missing candidate IDs.
- Duplicate forms or features, mixed spans, invalid offsets, or no unchanged
  surface candidate.
- Candidate IDs not in the provided set.
- Invalid payload shape.

## Proposal-verifier operation (`specialist-proposal-verifier`)

`build_proposal_verifier_prompt_request(source_text, proposal_text)` accepts only:

- `{"decision": "accept"}`
- `{"decision": "reject"}`

Failure modes:

- Invalid decision value.
- Extra fields in response.
- Any attempt to return replacement content.

## Derived edits

`derive_text_edits(source_text, corrected_text)` converts model output into
deterministic non-overlapping half-open Python Unicode code-point spans against
the original text. It rejects excessive rewrites, edits touching optionally
protected name-like tokens, and edits overlapping explicit caller-supplied
protected spans.

## Failure surface for extensions

Specialist prompt builders and validators are intentionally conservative. Raw
JSON and source data are never included in validation messages. A backend
adapter maps these privacy-safe contract failures to
`InvalidBackendResponseError` with its own safe backend identifier and operation
context before callers can consume a suggestion.

The older general finding contract remains readable without reinterpretation.
New specialist orchestration uses only the operations above and must preserve
their role separation, versions, schemas, limits, and suggestion-only status.
