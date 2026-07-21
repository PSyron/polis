# Vendored Polish LanguageTool Module Design

## Decision

Issue #54 adds a separately buildable, Polish-only Java module at
`third_party/languagetool-pl/`. It is a source-level derivative of a pinned
LanguageTool upstream revision and is kept outside `src/polis`. Polis retains
zero Python runtime dependencies and does not include the Java module in its
wheel or source distribution.

The module is intended to replace the large general LanguageTool installation
only after it passes the existing Polish corpus and resource benchmarks. It is
not enabled by default and does not change the current optional LanguageTool
adapter until qualification completes.

## Boundaries

The module contains only the required LanguageTool core classes and Polish
module resources, a small Polis entry point, and their direct build metadata.
It excludes other language modules, GUI, office integrations, browser clients,
HTTP server, public API code, n-gram downloads, and premium services.

The entry point consumes one UTF-8 JSON request on standard input and writes
one UTF-8 JSON response on standard output. It does not listen on a network
port, write analyzed text to disk, download assets, or invoke external
services. Python integration is optional and uses an injected subprocess
transport; importing `polis` never starts Java.

## Polish behavior

Only `pl-PL` is accepted. The initial release preserves the two proven comma
rules used by the existing optional adapter:

- `BRAK_PRZECINKA_ZE`
- `BRAK_PRZECINKA_ZEBY`

Additional Polish spelling, flexion, syntax, or punctuation rules enter only
with explicit corpus positives, correct hard negatives, stable rule IDs, and
per-rule quality results. The module may diagnose more cases than Polis
automatically corrects; automatic correction remains limited to independently
qualified high-confidence edits.

## Licensing and provenance

The module is distributed under LGPL-2.1-or-later. It contains an unmodified
copy of the upstream LGPL text, a `NOTICE`, an `UPSTREAM.md` file with the exact
commit hash and retrieval date, and a machine-readable manifest of every
included upstream path and its local modification status.

Each modified inherited file carries a prominent change notice and date. The
repository keeps complete corresponding source, build scripts, and uncombined
library form for the vendored module. Project-authored Python code remains MIT
and communicates with the module as a separate process. Before a public binary
release, all included dictionaries and Maven artifacts receive a separate
license audit.

## Build and packaging

The source build requires a pinned JDK and Maven version. Dependency resolution
is allowed only during an explicit build preparation step; the produced module
must run without network access. The normal `uv` workflow does not compile Java
and no Java artifact is inserted into Python wheel or sdist output.

The initial implementation uses an allowlisted Maven dependency manifest rather
than an opaque shaded executable. A later distributable bundle must preserve
user replacement and relinking rights required by LGPL, and therefore needs a
dedicated release-license review.

## Verification

Fast tests validate directory boundaries, required license and provenance
files, manifest consistency, absence of Java artifacts from Python
distributions, benchmark scoring, and source-level integration markers. The
slow workflow builds the module, exercises unseen cases offline over
stdin/stdout, audits open sockets, and runs every case in the 33-case corpus.

Qualification records disk size, cold-start latency, warm p50/p95 latency, and
RSS against the 6.8 baseline: 733 MB installed, 630 MiB RSS, 1.34 s cold start,
and 46.8/59.7 ms warm p50/p95. The vendored module is adopted only if it retains
the current allowlist quality gate (18 TP, 0 FP, 6 FN; F1 0.857; zero findings
on 10 negatives) while materially reducing the measured footprint.

## Non-goals

- Reimplementing LanguageTool's full parser or Polish morphology in Python.
- Bundling a JVM into the Python package.
- Releasing an opaque or non-relinkable Java executable.
- Claiming improvement for unmeasured flexion or word-order cases.
