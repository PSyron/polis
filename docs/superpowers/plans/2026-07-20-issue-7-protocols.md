# Analyzer and Local Backend Protocols Implementation Plan

**Goal:** Define narrow runtime protocols that let future analysis orchestration
depend on deterministic analyzers, rules, and local text generation without
depending on their implementations.

**Architecture:** Keep protocol declarations in `polis.core.protocols` because
they describe core boundaries and reuse the approved public result models.
Deterministic analyzers and rules stay synchronous; a local generation backend
is asynchronous because cancellation and an analysis deadline must be owned by
the future orchestration boundary rather than by a backend implementation.

**Tech Stack:** Python 3.12+, standard-library `typing.Protocol`, immutable
public models, pytest, mypy, and Ruff.

## Global Constraints

- Preserve offline-only behavior; this change imports no NLP package, model
  server client, network library, or concrete implementation.
- Reuse `AnalysisOptions`, `AnalysisResult`, `Finding`, and `Source`; do not
  introduce a parallel analysis result or finding model.
- A future public analysis call is atomic under ADR-0003: it returns one fully
  validated `AnalysisResult` or raises a controlled operational error.
- Deterministic checks and rule entries are synchronous. Local generation is
  asynchronous, while deadline, cancellation, and retry ownership remains with
  future orchestration.
- Do not define a retry policy yet: no retry behavior exists to parameterize and
  a policy would pre-commit error classification before the exception runtime
  is implemented.
- Keep the change in one focused commit credited only to Paweł Cyroń.

### Task 1: Specify protocol conformance tests

**Files:**
- Create: `tests/test_protocols.py`
- Create: `tests/typecheck/protocol_examples.py`
- Create: `scripts/typecheck_protocols.py`

**Interfaces:**
- Produces: failing imports and strict fake implementations for
  `DeterministicAnalyzer`, `Rule`, `RuleRegistry`, `LocalGenerationBackend`,
  `MonotonicClock`, and `AnalysisOrchestrator`.

- [x] Write failing tests that import the protocols, check runtime structural
  conformance for strict fakes, and reject imports of concrete NLP or model
  server modules from the protocol module.
- [x] Run `uv run --locked --extra dev pytest tests/test_protocols.py -v` and
  confirm it fails because `polis.core.protocols` does not exist.
- [x] Write strict type-check examples that assign each fake to its protocol.
- [x] Run `uv run --locked --extra dev python scripts/typecheck_protocols.py`
  and confirm it fails before declarations exist.

### Task 2: Define narrow runtime boundaries

**Files:**
- Create: `src/polis/core/protocols.py`
- Modify: `src/polis/core/__init__.py`

**Interfaces:**
- Consumes: `AnalysisOptions`, `AnalysisResult`, `Finding`, and `Source`.
- Produces: synchronous deterministic/rule interfaces, an asynchronous local
  generation interface, an injectable monotonic clock, and synchronous and
  asynchronous orchestration entry-point interfaces.

- [x] Implement the minimum `@runtime_checkable` protocols required by the
  conformance tests, with full public type annotations and no implementation
  logic.
- [x] Re-export the protocol names from `polis.core` only; do not expose a
  future `Analyzer` implementation from the package root.
- [x] Run focused runtime and strict type-check tests and confirm they pass.

### Task 3: Document ownership and verify the boundary

**Files:**
- Create: `docs/architecture/protocols.md`
- Modify: `docs/architecture/README.md`
- Modify: `README.md`
- Modify: `tests/test_protocols.py`

**Interfaces:**
- Consumes: the protocol declarations from Task 2.
- Produces: a documented contract for responsibilities, lifecycle, allowed
  controlled failures, ordering, deadline/cancellation ownership, and the
  intentionally deferred retry policy.

- [x] Document each protocol and ensure no concrete backend, rule, NLP, or
  network behavior is claimed.
- [x] Run the focused tests, full fast pytest selection, Ruff lint and format
  checks, strict mypy, unittest discovery, API-contract and protocol type
  checks, workflow validation, NLP assembly validation, build/artifact checks,
  clean-wheel smoke test, and evaluation dataset validation.
- [x] Review all issue acceptance criteria and commit once with
  `feat: define analyzer and backend protocols (#7)`.
