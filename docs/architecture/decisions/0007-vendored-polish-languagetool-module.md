# ADR-0007: Add a source-built Polish LanguageTool subset

- Status: Accepted
- Date: 2026-07-21
- Owner: Paweł Cyroń
- Issue: #54

## Context

Issue #54 requires a local, reproducible, non-network runtime workflow for
Polish rule checks without adding Java/JVM files to the Python runtime package.
LanguageTool `6.8` already exists as an optional external process, but M4
asks for a build-time path where source provenance and module selection are
explicitly tracked in the repository.

## Decision

Pin the LanguageTool 6.8 release commit and keep unmodified copies of the
upstream parent metadata, core `src/main`, and Polish module `src/main` under
`third_party/languagetool-pl/sources`. Build those copied modules into a
module-local Maven repository before compiling the project-authored bridge.

The bridge is a thin JAR with separate runtime libraries, not a shaded
executable. It creates a real `JLanguageTool(new Polish())` engine and exposes a
persistent newline-delimited JSON stdin/stdout boundary. Only the two
corpus-qualified upstream rule IDs are emitted. No HTTP server or other
LanguageTool language module is included.

The directory is excluded from wheel and sdist outputs.

## Consequences

- Source-level LanguageTool remains explicitly optional and locally built.
- No new Python dependencies are introduced.
- Runtime behavior of existing Polis optional LanguageTool adapter stays unchanged.
- The copied sources and thin runtime preserve inspection and relinking paths;
  binaries remain local build products and are not published with Polis.
- The two-rule subset retains 18 TP, 0 FP, and 6 FN on qualified punctuation,
  while all other corpus misses remain explicit benchmark false negatives.
