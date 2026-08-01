# ADR-0020: Adopt a runtime-first product charter

**Status: Accepted**
**Date:** 2026-08-01
**Issue:** #120

## Context

Polis has a supported offline runtime that can be built, installed, verified,
and used without a local language model. The repository's governance documents
still contain an older mandatory-model critical path that can be read as if a
qualified local model were required before the runtime may be released. That
contradiction leaves two incompatible release authorities.

ADR-0008 already separates deterministic automatic correction from
review-oriented model output. The runtime-first charter needs to make that
boundary authoritative for product release sequencing while preserving the
existing research evidence, historical evaluation work, and optional-extension
architecture.

## Decision

Polis is a complete product without a local language model. The release
authority for the product is the offline runtime: public API contracts,
deterministic analysis, conservative correction, serialization, CLI behavior,
artifact verification, and the documented privacy boundary.

Local-model work remains part of the repository, but only as an optional
extension and research track until a separate accepted issue and accepted ADR
promote an exact supported configuration. Model-derived or model-selected
edits are always review-only and do not gain automatic-correction privileges
from this charter.

## Product release authority

The runtime release path is authoritative for Polis product releases. Product
delivery depends on the default offline dependency set, deterministic
analyzers, regression tests, static checks, packaging verification, and other
runtime safety gates that run without a local language model, a model server,
a Java process, network access, a research corpus, or a consumed holdout.

Runtime release evidence is therefore sufficient to ship the supported product.
Optional research outcomes may inform later decisions, but they never define
current product completion on their own.

## Optional model extension

The `llm` module remains an optional protocol, prompt, and validation layer for
local extensions. A local model may be researched, benchmarked, and integrated
behind that boundary, but it stays disabled by default unless a future accepted
issue and ADR qualify an exact backend, model artifact, and operating mode.

Every model-derived or model-selected edit remains always review-only,
regardless of confidence or downstream validation. Failed, incomplete, or
negative model research is a valid outcome and never blocks a runtime release.

## Portfolio consequences

The runtime-first charter changes authority and sequencing, not repository
history. Historical reports, benchmarks, and evaluation work remain valid for
the exact experiments they recorded. LanguageTool also remains optional and
subject to its own bounded evidence and safety rules.

Consumed holdouts remain immutable: consumed holdouts are preserved as
evidence, are not rerun for this charter migration, and are not reused for
tuning. Runtime and research work may therefore advance on separate timelines
without rewriting prior evidence.

## Compatibility and safety

This charter preserves ADR-0008's automatic-versus-reviewable safety rules.
Deterministic sources may qualify separately for automatic correction under
explicit source-policy evidence, while model-backed output remains review-only
until a future accepted decision says otherwise.

The privacy boundary is unchanged: analyzed text stays on device, runtime code
does not couple `core` to a concrete model server, and optional extensions must
continue to fail closed when unavailable or invalid.

## Consequences

- Runtime governance becomes consistent with the supported product that already
  ships without a local model.
- Product release can proceed without waiting for optional model qualification.
- Model research, historical evaluation requirements, and optional local
  adapters remain documented and auditable.
- Future model promotion requires a new explicit authority change instead of an
  implicit dependency on old roadmap wording.

## Superseded authority

This ADR supersedes only the mandatory-model critical path in earlier product
governance text. It does not erase historical ADRs, reports, or evaluation
artifacts, and it does not relax existing safety rules for automatic
corrections.

Issue #120 records this finite migration from the old combined product-and-model
release path to the runtime-first charter.
