# Issue #5 Public Analysis Models Implementation Plan

**Goal:** Define a small, immutable public model layer for analysis findings and deterministic schema-versioned JSON exchange.

**Architecture:** Keep validated value objects and result models in `polis.core.models`, and keep JSON encoding and strict decoding in `polis.core.serialization`. The package root intentionally re-exports the stable user-facing types and serialization helpers. The implementation uses only the Python standard library.

**Tech Stack:** Python 3.12+, immutable dataclasses, string enums, `json`, `hashlib`, pytest, Ruff, mypy.

## Global Constraints

- Represent all finding fields required by `PROMPT.md`: identifier, category, severity, message, explanation, original fragment, optional minimal suggestion, half-open start/end offsets, confidence, and source.
- Interpret offsets as Python string indices over Unicode code points in the original input, never as byte or grapheme-cluster positions; allow zero-width insertions and whitespace-only deletions while requiring `end - start == len(original)`.
- Keep identifiers deterministic over verbatim, non-normalized identity fields and reject duplicate or colliding identifiers in one result.
- Use JSON schema version `1`; reject unknown versions, fields, enum values, duplicate object keys, invalid numeric values, and malformed source or identifier values.
- Preserve the input text, options, issue order, optional suggestions, and typed values across JSON round trips.
- Reject non-`None` no-op suggestions; use `None` when a finding has no justified replacement.
- Add no runtime dependency and implement no orchestration, rule, segmentation, or correction-application behavior.

---

### Task 1: Specify value objects and finding invariants

**Files:**
- Create: `tests/test_public_models.py`
- Create: `src/polis/core/models.py`

**Interfaces:**
- Produces: `Category`, `Severity`, `SourceKind`, `Source`, `Confidence`, and `Finding`

- [x] Write failing tests for enum coverage, source parsing, confidence bounds and finiteness, half-open ranges, required text, and deterministic identifiers.
- [x] Run `uv run --locked --extra dev pytest tests/test_public_models.py -v` and confirm failure because the public models do not exist.
- [x] Implement immutable enums and value objects with strict boolean rejection and useful `TypeError` or `ValueError` failures.
- [x] Implement `Finding.create(...)` so its identifier is a versioned digest of category, source, offsets, original fragment, and optional suggestion.
- [x] Run the focused tests and confirm the value-object cases pass.

### Task 2: Specify options, result context, and JSON behavior

**Files:**
- Modify: `tests/test_public_models.py`
- Modify: `src/polis/core/models.py`
- Create: `src/polis/core/serialization.py`

**Interfaces:**
- Consumes: the value objects from Task 1
- Produces: `AnalysisOptions`, `AnalysisResult`, `analysis_result_to_json`, and `analysis_result_from_json`

- [x] Add failing tests for category filtering options, source-text boundary checks, exact original-fragment matching, duplicate identifiers, Unicode slicing, canonical JSON, lossless round trips, and strict decoder rejection.
- [x] Run the focused tests and confirm failures are caused by the missing result and serialization behavior.
- [x] Implement normalized immutable options, contextual result validation, canonical UTF-8 JSON text, and strict schema-version-1 decoding.
- [x] Run the focused tests and confirm all model and serialization cases pass.

### Task 3: Publish and document the contract

**Files:**
- Modify: `src/polis/core/__init__.py`
- Modify: `src/polis/__init__.py`
- Create: `docs/public-api.md`
- Modify: `README.md`
- Modify: `tests/test_package_smoke.py`

**Interfaces:**
- Consumes: the models and serialization helpers from Tasks 1 and 2
- Produces: intentional imports from `polis` and documented schema compatibility expectations

- [x] Add failing smoke tests for the intended public exports.
- [x] Re-export only the supported model contract from `polis.core` and `polis`.
- [x] Document construction, validation failures, field semantics, Unicode half-open offsets, stable identifier boundaries, exact schema-version-1 JSON, and additive-versus-breaking compatibility rules.
- [x] Run focused and full tests, Ruff lint and format checks, strict mypy, unittest discovery, package build, and a clean-wheel import/round-trip smoke test.
- [x] Review every issue acceptance criterion and commit the complete focused change once.
