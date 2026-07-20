# Offline operation verification

This project is designed to run analysis without external network access.

## Supported offline configuration

- Runtime uses `Analyzer` and deterministic rule registry in-process.
- Optional mock backend uses local prompt parsing and local transport (`MockHeuristicBackend`).
- Dependency installation uses locked `uv` files from the repository.

## Verification command

Run this to verify analysis when outbound network is blocked:

```console
pytest -q tests/test_offline_verification.py
```

The test fixture blocks `socket.create_connection` so any accidental outbound network
use causes the test to fail before analysis starts.

## Expected outcomes

- Analyzer succeeds in deterministic mode (`use_local_heuristic_backend = false`).
- Analyzer succeeds with config-based local mock backend enabled.
- No private input text is logged by these checks.

## Supported configuration limits

This verification does not validate third-party LLM services or non-locked runtimes.
For external backends, add an explicit offline policy and integration test for that
runtime before calling it supported.
