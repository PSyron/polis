# Public API and Exception Contract Implementation Plan

**Goal:** Freeze the first public analyzer entry points, correction selection
semantics, and controlled failure contract without implementing orchestration.

**Architecture:** Record the accepted design in ADR-0003 and make the proposed
surface mechanically checkable with a typing-only declaration. Strictly typed
examples exercise each public operation and error category while leaving the
runtime package unchanged.

**Tech Stack:** Python 3.12+, standard-library typing declarations, pytest,
mypy, Ruff, and the existing package build checks.

## Global Constraints

- Preserve offline-only analysis and never include analyzed text in error context.
- Reuse the immutable `AnalysisOptions`, `Finding`, and schema-versioned result
  invariants already approved for public models.
- Do not implement Analyzer orchestration, local model backends, or correction
  application in this decision issue.
- Keep the change in one focused commit credited only to Paweł Cyroń.

### Task 1: Define an executable, typing-only contract

**Files:**
- Create: `tests/typecheck/stubs/polis/__init__.pyi`
- Create: `tests/typecheck/stubs/polis/core/__init__.pyi`
- Create: `tests/typecheck/stubs/polis/core/models.pyi`
- Create: `tests/typecheck/api_contract_examples.py`
- Create: `tests/test_api_contract.py`
- Create: `scripts/typecheck_api_contract.py`

- [x] Write tests that require the ADR, architecture index, public documentation,
  typing-only declaration, and strict example type check.
- [x] Run `uv run --locked --extra dev pytest tests/test_api_contract.py -v` and
  confirm failure because the contract artifacts do not exist.
- [x] Declare the approved future public types without a corresponding Python
  implementation file, using one core result declaration and direct re-exports.
- [x] Type-check one success example and one example for every controlled public
  failure category.
- [x] Run the focused test again and confirm it passes.

### Task 2: Record the stable API decision

**Files:**
- Create: `docs/architecture/decisions/0003-public-api-and-exception-contract.md`
- Modify: `docs/architecture/README.md`
- Modify: `docs/public-api.md`

- [x] Specify typed constructors and synchronous/asynchronous analysis calls.
- [x] Specify filter forwarding, atomic correction selection, conflict boundaries,
  ordering, and no-partial-result behavior.
- [x] Specify the exception hierarchy, error codes, retryability, and safe context
  fields without analyzed text.
- [x] Add concise success and controlled-failure examples to the public API guide.
- [x] Run the focused contract test and inspect every acceptance criterion.

### Task 3: Verify the focused decision change

**Files:**
- Modify: `tests/test_api_contract.py`

- [x] Run the fast pytest suite, Ruff lint and format checks, strict mypy, Python
  unittest discovery, build, distribution metadata inspection, and clean wheel
  smoke test.
- [x] Confirm the working tree contains only this issue's documentation, typing,
  and verification artifacts.
- [x] Commit once with `docs: approve public API and exception contract (#6)`.
