# Privacy and dependency audit for release preparation

This document records the M4-02 release-gate evidence for `main`.

## Scope

- Runtime dependencies and licenses.
- Network behavior and offline guarantees.
- Diagnostic redaction guarantees.
- Release artifact content checks.
- Secret and model-file scanning for tracked repository inputs and built distributions.

## Findings

- There are **no runtime Python dependencies** in `project.dependencies`.
- All build-time and dev dependencies are documented in
  [dependency license review](development/dependency-licenses.md), and all are
  matched by `tests/test_dependency_licenses.py`.
- Offline behavior is enforced by tests that run with blocked TCP socket creation in
  `tests/test_offline_verification.py` and
  `tests/test_privacy_dependency_audit.py::test_analyzer_without_model_backends_does_not_attempt_network`.
- Diagnostic redaction is validated by checking that selected failures do not
  include user text in message or context:
  `tests/test_privacy_dependency_audit.py::test_analysis_diagnostics_do_not_leak_user_text_by_default`.
- Release artifact packaging is validated by
  `tests/test_distribution_artifacts.py` and
  `tests/test_privacy_dependency_audit.py::test_built_release_artifacts_do_not_include_model_files`.
- No secrets matching repository-level secret patterns were found in tracked files,
  and no known model/binary artifact extensions were found in built wheel/sdist
  (`tests/test_privacy_dependency_audit.py::test_no_secret_literals_in_versioned_files`).

## Evidence commands

- `uv run --locked --extra dev pytest -q tests/test_offline_verification.py tests/test_dependency_licenses.py tests/test_distribution_artifacts.py tests/test_privacy_dependency_audit.py`
- `uv run --locked --extra dev pytest -q tests/test_fast_ci_workflow.py`
- `uv run --locked --extra dev ruff check .`
- `uv run --locked --extra dev ruff format --check .`
- `uv run --locked --extra dev mypy .`

## Residual risk

- Repository maintainers can add new dependency or model files by editing `pyproject.toml`,
  dependency policy decisions, or tracked files; such changes require a new audit
  and issue-level review.
- The CLI prints structured error details; if callers log full exception objects,
  operational context keys remain non-sensitive by contract, but logs can still
  include exception tracebacks depending on environment settings.
