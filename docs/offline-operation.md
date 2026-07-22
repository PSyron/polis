# Offline operation verification

This project is designed to run analysis without external network access.

## Supported offline configuration

- Runtime uses `Analyzer` and deterministic rule registry in-process.
- Optional mock backend uses local prompt parsing and local transport (`MockHeuristicBackend`).
- The specialist engine is disabled unless a caller explicitly injects both a
  router and backend. The #60 engine performs no I/O itself; the injected
  adapter remains responsible for proving local-only transport.
- Optional LanguageTool support connects only to a separately started
  LanguageTool 6.8 server on a numeric loopback address. It never uses a public
  LanguageTool API, DNS name, proxy, or redirect.
- The preferred vendored LanguageTool mode directly starts one persistent local
  stdio child from an explicit absolute path. It opens no socket and performs no
  implicit download or update.
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

## Preferred vendored LanguageTool sentence path

Build the pinned subset during explicit dependency preparation:

```console
cd third_party/languagetool-pl
./scripts/build.sh
```

Then configure one sentence-only stdio session:

```toml
[vendored_language_tool]
stdio_path = "/absolute/path/to/polis/third_party/languagetool-pl/scripts/run_stdio.sh"
timeout_seconds = 2.0
```

The analyzer starts the process lazily and reuses it for qualified punctuation
checks and contextual synthesis. Close analyzer-owned processes with a context
manager or `Analyzer.close()`. Source-policy `1.1` keeps qualified comma
insertions automatic and contextual inflection reviewable. A missing executable,
timeout, malformed or oversized response, broken pipe, or stopped process fails
closed without removing built-in deterministic findings or placing analyzed
text in an error.

The runner binds no port and opens no network socket. Removing
`[vendored_language_tool]` disables the process. Do not combine this section
with either legacy mode below.

## Optional loopback LanguageTool compatibility mode

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
Only reviewed comma findings from `BRAK_PRZECINKA_KTORY`,
`BRAK_PRZECINKA_SPOJNIK_PROSTY`, `BRAK_PRZECINKA_ZE`,
`BRAK_PRZECINKA_ZEBY`, and `WOLACZ_BEZ_PRZECINKA` are retained. A local
sidecar failure produces no optional findings and does not discard findings
from in-process rules.

The legacy contextual inflection path uses the source-built stdio runner
directly, but starts a process per eligible sentence:

```toml
[contextual_inflection]
stdio_path = "/absolute/path/to/polis/third_party/languagetool-pl/scripts/run_stdio.sh"
timeout_seconds = 2.0
```

The path must be absolute and executable. Each call starts that local process,
uses the tag-preserving `synthesize_context` operation, and closes it after the
sentence response. Failures produce no inflection suggestion. Suggestions are
never automatically applied. Multi-sentence input is outside this rule's scope
and causes no contextual morphology process call.

## Supported configuration limits

This verification does not start or validate separately installed runtimes.
For external backends, add an explicit offline policy and integration test for that
runtime before calling it supported.
No real specialist model is enabled by the current supported configuration.

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
rules and resources and returns only the five corpus-qualified comma rule IDs.
