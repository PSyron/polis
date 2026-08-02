# Independent Canonical JSON Property Design

## Context

Issue #124 established generated `AnalysisResult` JSON fidelity, but its canonical-determinism assertion serializes the same object twice. Issue #143 closes that test-quality gap without changing production behavior.

## Design

For every bounded synthetic Unicode case, the property constructs two separate `AnalysisResult` values. Each construction calls `_generated_findings(case.text)` independently, producing equivalent findings without sharing result or finding identities. The property verifies structural equality, distinct construction identities, byte-identical canonical JSON, and lossless round trips for both encodings.

The existing replay-safe assertion helper remains the only generated failure path. No generated text is included in invariant names or diagnostics.

## Alternatives

- Re-serializing the first result remains too weak because object-local caching or state could go undetected.
- Building the second value by decoding the first JSON is also too weak because it makes the first serialization the source of truth.
- A new shared result factory is unnecessary: the existing `_generated_findings` helper is the current consumer and already provides deterministic independent construction.

## Verification

The focused test must fail when the second result is deliberately constructed with divergent issues, then pass when it is constructed independently but equivalently. The full fast suite and static checks remain required. No production files or dependencies change.
