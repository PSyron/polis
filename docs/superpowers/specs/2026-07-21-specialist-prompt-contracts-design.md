# Specialist Prompt Contracts Design

## Status and scope

This design completes GitHub issue #59. It hardens the existing experimental
specialist contracts without selecting a model, runtime, or automatic
correction policy. ADR-0009 remains binding: every result is unqualified and
suggestion-only.

## Selected approach

Keep the three operations in `polis.llm.corrected_text` and strengthen their
shared request and validation helpers. This avoids a production dependency on
a JSON Schema implementation and avoids a broad module split before the
contracts have a production caller. Replacing the module or adding a schema
library would increase packaging and review cost without improving the closed
wire shapes required by this issue.

## Request contracts

Every operation has a stable ID, semantic protocol version, response-schema
version, closed JSON Schema, separate system and user messages, deterministic
generation settings, and explicit input and output limits. The system message
contains policy only. The user message contains one canonical JSON object
between `INPUT_JSON` markers. Less-than and greater-than characters inside data
strings are Unicode-escaped, so analyzed text cannot terminate the delimiter.

The operations are:

- `specialist-corrected-text/1.0`: one bounded source string and one focus;
- `specialist-candidate-selection/1.0`: one source string and finite forms for
  one original span;
- `specialist-proposal-verifier/1.0`: one source and the exact existing
  proposal, with an accept-or-reject result only.

Candidate records must have unique non-empty IDs and forms, identical positive
source spans, valid offsets, typed optional lemmas, and unique non-empty
morphological features. The original surface form must be among the candidates.
The model can return only `unchanged` or one supplied ID.

## Response and edit validation

Raw responses are size-limited before parsing. JSON decode failures and every
schema or safety failure use privacy-safe messages that contain neither source
text nor raw model output. Corrected text is converted locally with
`SequenceMatcher` into ordered, non-overlapping edits against Python Unicode
code-point offsets. Broad rewrites and edits overlapping caller-supplied
protected spans are rejected. A verifier can return only `accept` or `reject`
and cannot return replacement content.

The legacy finding contract remains unchanged and readable. The specialist
module stays model- and transport-independent; a runtime adapter is responsible
for applying its native chat template to the two messages and for mapping a
privacy-safe contract failure to the public backend error with runtime context.

## Verification

Regression tests cover delimiter injection, closed schemas, operation-specific
limits, malformed JSON privacy, candidate IDs and spans, unchanged candidates,
Unicode edits, duplicate and broad edits, protected names, and verifier
replacement attempts. The full fast suite, Ruff, formatting, and mypy are
required before closing #59.
