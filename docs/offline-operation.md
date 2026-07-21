# Offline operation verification

This project is designed to run analysis without external network access.

## Supported offline configuration

- Runtime uses `Analyzer` and deterministic rule registry in-process.
- Optional mock backend uses local prompt parsing and local transport (`MockHeuristicBackend`).
- Optional LanguageTool support connects only to a separately started
  LanguageTool 6.8 server on a numeric loopback address. It never uses a public
  LanguageTool API, DNS name, proxy, or redirect.
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

## Optional local LanguageTool

Start a separately installed LanguageTool 6.8 server bound to loopback, then
enable it explicitly:

```toml
[language_tool]
base_url = "http://127.0.0.1:8081"
timeout_seconds = 1.0
```

Omit the entire section to disable the adapter. Configuration does not start or
download the server. Before sending analyzed text, Polis makes a fixed-text
preflight request and requires server name `LanguageTool` and version `6.8`.
Only reviewed comma findings from `BRAK_PRZECINKA_ZE` and
`BRAK_PRZECINKA_ZEBY` are retained. A local sidecar failure produces no
optional findings and does not discard findings from in-process rules.

## Supported configuration limits

This verification does not start or validate separately installed runtimes.
For external backends, add an explicit offline policy and integration test for that
runtime before calling it supported.

For source-level reproducibility audits, this repository includes
`third_party/languagetool-pl` with pinned LanguageTool provenance and local build
scripts. This directory is explicitly excluded from packaged artifacts.

After one online dependency-preparation build, the vendored subset can be
rebuilt and exercised without network access:

```console
cd third_party/languagetool-pl
POLIS_LT_OFFLINE=1 ./scripts/build.sh
./scripts/run_stdio.sh
```

The stdio process does not bind a port. It loads the checked-in Polish 6.8
rules and resources and returns only the two corpus-qualified comma rule IDs.
