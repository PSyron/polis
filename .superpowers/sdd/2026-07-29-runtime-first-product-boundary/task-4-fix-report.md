# Task 4 review fix report

- Status: completed
- Issue: #120
- Finding: root-level `target/`, `.m2/`, and `repository/` artifact members were not rejected.

## Changed files

- `tests/test_distribution_artifacts.py`
- `scripts/verify_distribution_artifacts.py`
- `pyproject.toml`

## Fix

- Added a regression test covering root-level `target/`, `.m2/`, and
  `repository/` members.
- Made the test and distribution verifier reject those directory markers at any
  path depth, including after sdist-root normalization.
- Added matching Hatch sdist exclusions for root-level `.m2`, `repository`, and
  `target` directories. Wheel packaging remains restricted to `src/polis`.

## Commands run

- `uv run --locked --extra dev pytest tests/test_distribution_artifacts.py::test_prohibited_vendor_markers_reject_root_level_directories -q` — passed (`3 passed`)
- `uv run --locked --extra dev pytest tests/test_distribution_artifacts.py tests/test_offline_verification.py -v` — passed (`8 passed`)
- `uv run --locked --extra dev pytest tests/test_offline_verification.py tests/test_languagetool_vendor_artifacts.py tests/test_languagetool_vendor_runtime.py tests/test_distribution_artifacts.py -v` — passed (`18 passed, 28 skipped`)
- `uv run --locked --extra dev python -m build --no-isolation --outdir /tmp/polis-product-boundary-task-4-fix` — passed
- `uv run --locked --extra dev python scripts/verify_distribution_artifacts.py --dist /tmp/polis-product-boundary-task-4-fix` — passed

## Known limitations

- Vendored LanguageTool runtime tests remain skipped unless
  `POLIS_LT_VENDOR_INTEGRATION=1` is set after building the module; this is the
  existing integration boundary and is unrelated to the review finding.

## Next permitted action

- Commit this focused review fix with an issue-referencing message.
