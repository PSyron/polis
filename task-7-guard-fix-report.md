# Task 7 Guard Fix Report

Issue: #120

## Acceptance status

Accepted for the final-review-2.md Medium finding. The product collection guard
now rejects plain `import experiments.some_module` imports and direct
file-loading calls that resolve to `tests/fixtures/evaluation/...` paths. No
runtime source, research corpus, holdout marker, or research data was changed.
No issue was closed.

## Changed files

- `tests/conftest.py` — tightened the collection-time research boundary guard
  with AST import-prefix detection and narrow static path/load-call detection.
- `tests/test_product_collection_guard.py` — added adversarial regression tests
  for a plain experiment import, direct JSON/XML/text fixture reads, and an
  accepted policy/provenance-style path mention that does not load the fixture.

## Verification

- `uv run --locked --extra dev pytest tests/test_product_collection_guard.py -v`
  — 3 passed.
- `uv run --locked --extra dev pytest -m "not research and not slow and not model"`
  — 446 passed, 404 deselected.
- `uv run --locked --extra dev pytest --collect-only -q -m research`
  — 375 collected, 475 deselected.
- `uv run --locked --extra dev pytest --collect-only -q -m "not research and not slow and not model"`
  — 446 collected, 404 deselected.
- `uv run --locked --extra dev ruff check .` — passed.
- `uv run --locked --extra dev ruff format --check .` — passed.
- `uv run --locked --extra dev mypy .` — passed.

## Known limitations and risks

- The guard is intentionally static and narrow. It detects literal and
  statically composed `Path`/string targets used in import or file-loading AST
  patterns; it is not a general-purpose taint analyzer for dynamically computed
  paths.
- Research tests were collected only. They were not executed, and no consumed
  one-shot holdout was rerun or used for tuning.

## Next permitted action

Request one more whole-branch review for #120. Do not close #120 until that
review and every acceptance criterion are accepted.
