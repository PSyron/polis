# ADR-0018: Align runtime composition protocols with executed operations

- Status: Accepted
- Date: 2026-07-22
- Owner: Paweł Cyroń
- Issue: #83

## Context

The exported `RuleRegistry` protocol previously declared `rules()` while the
analysis pipeline accepted that protocol and invoked `find()`. The pipeline
also declared a private structural protocol for validated local findings even
though the documented public backend protocol only covered raw prompt
generation. An extension author could therefore implement the documented
protocols and still fail to compose with the supported runtime path.

## Decision

`RuleRegistry` is the executable deterministic composition contract. It
declares `find(text, *, options) -> tuple[Finding, ...]`; `rules()` is no
longer part of that public protocol. Concrete registries may retain an
introspection method independently, but consumers that require inventory must
introduce a separate protocol in a future issue.

`LocalGenerationBackend` remains the raw local prompt-to-response contract.
`LocalFindingBackend` is a separate public contract for adapters that construct
prompts and return validated, fragment-local findings. The analysis pipeline
uses only `LocalFindingBackend` and owns fragment iteration, original-text
offset translation, and canonical error context.

This is an intentional source-compatibility change for type-only users of
`RuleRegistry`: custom registries must expose `find()` to satisfy the supported
composition role. No concrete registry, raw backend, model name, server
dependency, finding schema, filtering behavior, ordering, offset convention,
or async failure ownership changes.

## Consequences

- Public type annotations now describe every runtime operation they consume.
- Raw generation and validated finding production have distinct documented
  owners, so an extension can implement the narrow boundary it needs.
- Existing `rules()`-only custom structural implementations need migration to
  `find()` before being supplied to the analysis pipeline.
- A future public inventory contract must be introduced separately rather than
  expanding the execution protocol without a consumer.

## Alternatives considered

- **Keep both `rules()` and `find()` in `RuleRegistry`.** Rejected because the
  extra inventory requirement would exclude otherwise valid executable
  registries and has no current pipeline consumer.
- **Keep the pipeline-private finding protocol.** Rejected because it leaves
  the supported extension path undocumented and unusable through public types.
- **Make `LocalFindingBackend` inherit raw generation.** Rejected because a
  finding-producing adapter need not expose raw prompt generation, and the two
  responsibilities have different callers.
