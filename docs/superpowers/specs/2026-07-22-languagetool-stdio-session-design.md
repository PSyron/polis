# Vendored LanguageTool stdio session design

## Scope

Issue #77 connects the already vendored Polish LanguageTool 6.8 subset to the
public sentence analyzer. One persistent, explicitly configured local process
serves both allowlisted punctuation checks and contextual inflection synthesis.
This removes the current requirement for a separate full LanguageTool HTTP
installation and avoids starting a JVM for each eligible sentence.

The feature does not enable new LanguageTool rules, change source-policy `1.1`,
add a Python dependency, bundle Java output in wheel or sdist, evaluate
paragraphs, or add a model backend.

## Options considered

1. Keep HTTP punctuation and per-call stdio synthesis. This preserves the
   current code but does not exercise the vendored subset through the complete
   analyzer and has repeated JVM startup cost.
2. Add a persistent stdio transport used by both rule contracts. This is the
   selected option because the Java bridge already implements both operations,
   the process remains local and offline, and one session can serve repeated
   sentence calls.
3. Embed Java in the Python process. This would require a new runtime binding,
   increase packaging complexity, and weaken process isolation.

## Configuration

`AnalyzerConfig` gains `vendored_language_tool_stdio_path: str | None` and
`vendored_language_tool_timeout_seconds: float`. TOML uses:

```toml
[vendored_language_tool]
stdio_path = "/absolute/path/to/run_stdio.sh"
timeout_seconds = 2.0
```

The executable must be an absolute executable file. Vendored mode is mutually
exclusive with `language_tool_url` and `contextual_inflection_stdio_path`,
because those settings would create competing punctuation or morphology
transports. Existing HTTP-only and contextual-only configurations remain
backward compatible.

Selecting vendored mode enables both `LocalLanguageToolRule` and
`ContextualInflectionRule` with one transport. Punctuation findings retain
source `rule:languagetool.pl`, confidence `0.85`, and automatic eligibility
under source-policy `1.1`. Contextual findings retain source
`rule:languagetool.contextual_inflection`, confidence `0.95`, and reviewable
status.

## Persistent transport

`LocalLanguageToolStdioSession` lives in
`src/polis/rules/languagetool_stdio.py`. It implements both
`LanguageToolTransport.check()` and
`ContextMorphologyTransport.synthesize_context()`.

The production constructor receives one absolute executable path and derives a
single-element command without a shell. A lower-level command tuple constructor
is available for tests and embedding, but validates that every item is a
non-empty string and never passes it through a shell.

The session starts lazily on the first request. It launches one child process
with binary stdin and stdout, `stderr` redirected away from API diagnostics,
and a dedicated daemon reader thread. The reader uses bounded
`readline(max_response_bytes + 1)` and places complete records in a queue. This
works for pipe handles on macOS, Linux, and Windows without relying on
`select()`.

All request/response exchanges are serialized by one lock. A request is encoded
as one UTF-8 JSON line, checked against a `64 KiB` request limit, written, and
flushed. The caller waits on the reader queue for the configured timeout. The
response must be one UTF-8 JSON object no larger than `1 MiB`. Empty output,
invalid UTF-8/JSON, excess bytes, timeout, broken pipe, early exit, or an object
other than a mapping marks the session broken, terminates the process, and
raises a generic `OSError`, `TimeoutError`, or `ValueError` containing no source
text or response body. A broken or closed session never restarts implicitly.

`check()` accepts only `pl-PL` and sends the existing check request.
`synthesize_context()` sends the existing versioned operation and exact spans.
The rule-specific validators remain authoritative for software identity,
allowlisted matches, candidate tags, candidate IDs, offsets, and ambiguity.

## Ownership and shutdown

An analyzer constructed from `vendored_language_tool_stdio_path` owns its
session. `Analyzer.close()` closes stdin, waits up to the configured timeout,
then terminates and finally kills only if necessary. It is idempotent.
`Analyzer` implements synchronous context-manager methods so normal use is:

```python
with Analyzer.from_config("polis.toml") as analyzer:
    result = analyzer.correct("Wiem że jutro wróci.")
```

Using an owned analyzer after `close()` raises a privacy-safe `RuntimeError`
before analysis. Existing analyzers without an owned session remain usable
after `close()` because they own no external resource.

Injected transports remain caller-owned. `Analyzer.close()` does not inspect or
close them. For combined injected tests, the same object is passed explicitly
as both the punctuation and contextual transport.

The child process is also terminated through a best-effort finalizer if a caller
loses the analyzer without closing it, but explicit `close()` or the context
manager is the documented lifecycle.

## Analyzer wiring

`Analyzer.__init__` creates the owned session before constructing the default
registry and passes it to both rule registrations. `_make_default_registry()`
accepts independent optional punctuation and contextual transports. It never
constructs two stdio sessions for vendored mode.

The existing loopback HTTP path still constructs
`LoopbackLanguageToolHttpTransport`; the existing standalone contextual path
still constructs `StdioContextMorphologyTransport`. No model name or server
type enters core protocols or result models.

## Failure behavior

Both rules already fail closed on their transport exception allowlists. If the
vendored process is unavailable or breaks, built-in rules continue to emit
findings. The LanguageTool punctuation and contextual sources emit nothing for
that call. `Analyzer.correct()` therefore preserves deterministic corrections
and returns no fabricated partial success outcome.

Configuration errors are raised before process startup. Runtime errors emitted
by the transport never include analyzed text, raw JSON, executable output, or
environment values. No retry or process restart occurs inside a sentence call.

## Performance and privacy evidence

The benchmark uses the 69 reviewed development sentences from corpus-v3 and one
analyzer/session. It records process startup, first-request latency, warm p50 and
p95, throughput, Java RSS, Python RSS, combined RSS, process-start count, and
socket audit. The accepted gates are:

- exactly one Java process start;
- warm end-to-end p95 at most `500 ms` per sentence;
- combined loaded RSS at most `1 GiB`;
- zero swap growth;
- no network socket owned by the Java process; and
- identical findings on two repeated passes.

The committed report contains case IDs, counts, latency, memory, process and
artifact hashes, and finding hashes only. It contains no sentence text,
original forms, suggestions, raw responses, or private paths. Holdout data is
not opened by #77.

## Testing and documentation

Tests are written first for configuration closure and mutual exclusion, lazy
startup, process reuse, concurrent serialization, bounded records, timeout,
broken process, idempotent shutdown, ownership, public context management,
automatic punctuation, reviewable inflection, deterministic fallback, and
privacy-safe errors. Opt-in real integration uses the pinned vendored artifact
to verify both operations, one JVM, no sockets, latency, RSS, and clean exit.

Documentation updates cover configuration, public API lifecycle, offline use,
privacy, performance, removal, limitations, changelog, and roadmap. Full Ruff,
formatting, mypy, pytest, vendored integration, wheel/sdist build, content
verification, clean installation, and offline checks are required before #77 is
closed.
