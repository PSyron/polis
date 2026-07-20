# Compatibility policy and semantic versioning

This document publishes the M4 compatibility baseline and deprecation policy.

## Supported configurations

`polis` is verified on the same matrix as fast CI:

- CPython 3.12, 3.13, 3.14 on Linux x86_64,
- CPython 3.12, 3.14 on macOS arm64,
- CPython 3.12, 3.14 on Windows x86_64.

No optional model runtime is required for core deterministic checks.

### Evidence and deprecation policy enforcement

- Compatibility assertions are checked in `.github/workflows/fast-ci.yml` (Linux x86_64,
  macOS arm64, Windows x86_64) on each push and PR.
- For each release block, we verify the compatibility fixture and quality gates by
  running `uv run --locked --extra dev python scripts/verify_prerelease_candidate.py`.
- Any required API/schema change must update `tests/fixtures/public_api_snapshot.json`
  and include migration notes before release.

## Public API compatibility policy

- **Patch**: fixes, documentation-only updates, test additions, and bug fixes with no behavior-breaking effect on stable public symbols.
- **Minor**: additive public symbols, additive enum values, safer validation messages, and new optional features.
- **Major**: changes that break existing code using documented symbols (`polis.__all__` / `public API snapshots`) or serialized schema versions.

## Serialized data compatibility

- Public analysis JSON is currently `schema_version = 1`.
- Any change to wire shape or identifier semantics is a **major** change and must be paired with migration guidance.

## How we track compatibility

- `scripts/verify_prerelease_candidate.py` executes the quality gates.
- `tests/fixtures/public_api_snapshot.json` records stable exports and schema versions.
- `tests/test_api_compatibility.py` fails when runtime exports or schema contracts drift without snapshot updates.
- Any snapshot update requires explicit issue-level review and release-note notes.
