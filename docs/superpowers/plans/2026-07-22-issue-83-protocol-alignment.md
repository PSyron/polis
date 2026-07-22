# Runtime Protocol Alignment Implementation Plan

**Goal:** Make the public runtime protocols match the analyzer pipeline's
actual dependencies without exposing a private pipeline-only protocol.

**Architecture:** `RuleRegistry` is the executable deterministic boundary, so
it exposes `find(text, *, options)` rather than only the registry inventory.
`LocalGenerationBackend` remains the raw prompt boundary. A separate public
`LocalFindingBackend` expresses the existing normalized-finding operation used
by the pipeline. Both remain model- and server-independent. The pipeline may
depend only on public core protocols.

**Tech Stack:** Python 3.12+, `typing.Protocol`, pytest, mypy, and Ruff.

## Constraints

- Preserve offline-only execution and the ADR-0003 atomic failure contract.
- Do not alter finding normalization, filtering, order, or original half-open
  offsets.
- Keep raw generation and normalized finding generation distinct; no adapter
  implementation is introduced in this issue.
- Keep the implementation to one focused commit for #83.

### Task 1: Write public-boundary regression tests

**Files:**
- Modify: `tests/test_protocols.py`
- Modify: `tests/typecheck/protocol_examples.py`
- Modify: `scripts/typecheck_protocols.py`

1. Define strict fake registry and finding backend implementations using the
   desired public methods and verify runtime structural conformance.
2. Add static assignments proving the concrete registry and mock backend meet
   the public protocols.
3. Add an AST regression test that rejects pipeline-local `Protocol` classes.
4. Run the focused protocol tests and type-check script; confirm failure occurs
   because the new protocol and registry method are not yet public.

### Task 2: Publish the minimal protocols and consume them

**Files:**
- Modify: `src/polis/core/protocols.py`
- Modify: `src/polis/core/__init__.py`
- Modify: `src/polis/analysis/pipeline.py`

1. Add `RuleRegistry.find(text, *, options)` to its public contract.
2. Add `LocalFindingBackend.generate_findings(...)` with the exact existing
   pipeline dependency surface, including injectable clock and sleep inputs.
3. Re-export the new protocol from `polis.core`.
4. Replace the pipeline's private `_LLMBackend` with `LocalFindingBackend` and
   remove its private export, without changing error or offset behavior.
5. Re-run focused tests until green.

### Task 3: Document and verify the compatibility boundary

**Files:**
- Modify: `docs/architecture/protocols.md`
- Modify: `docs/customization.md`

1. Document the separate raw and normalized local backend contracts and
   ownership of timeout, cancellation, and response validation.
2. Document that a registry executes its configured deterministic rules in
   fixed order.
3. Run protocol and pipeline tests, strict protocol type checks, `ruff check`,
   `ruff format --check`, `mypy .`, and the fast pytest suite.
4. Review #83 acceptance criteria, then create one commit referencing #83.
