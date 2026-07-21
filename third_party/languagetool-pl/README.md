# Vendored Polish LanguageTool Module

This directory contains an isolated, source-based LanguageTool 6.8 derivative
for the two Polish punctuation rules qualified by Polis. It adds no Python
runtime dependency and is excluded from Polis wheels and source distributions.

## Included scope

- the upstream 6.8 parent build metadata;
- the LanguageTool core `src/main` tree with deterministic release metadata;
- the unmodified Polish module `src/main` tree and resources;
- a project-authored stdin/stdout bridge; and
- reproducibility, provenance, license, verification, and benchmark scripts.

Other languages, the HTTP server, command-line application, GUI, office and
browser integrations, n-gram data, and premium services are excluded. The
runtime emits only `BRAK_PRZECINKA_ZE` and `BRAK_PRZECINKA_ZEBY` findings.

## Toolchain and build

The pinned toolchain is OpenJDK 17.0.19 and Maven 3.9.16. The checked-in
`sources/` directory is sufficient for source review. To recreate it byte for
byte from the pinned upstream commit, run:

```bash
./scripts/bootstrap.sh
```

Bootstrap needs GitHub access. The first build may access Maven repositories to
populate the module-local `.m2/` cache:

```bash
./scripts/build.sh
```

The script first builds the copied LanguageTool parent, core, and Polish module
into that private repository. It then builds a thin, relinkable bridge JAR and
copies its runtime libraries to `target/dependency/`. It never falls back to a
different implementation when an upstream build fails. Release time and JAR
entry timestamps are fixed to the v6.8 release commit for repeatable artifacts.
Bootstrap applies the reviewed patch documented in `UPSTREAM.md`; it prevents
metadata from the enclosing repository from entering the core JAR.

Once the local cache exists, the same source build is verified offline with:

```bash
POLIS_LT_OFFLINE=1 ./scripts/build.sh
```

Build preparation is the only step that resolves dependencies. Runtime does
not download resources or open a network listener.

## Stdio protocol

Start the local process with:

```bash
./scripts/run_stdio.sh
```

The process reads newline-delimited UTF-8 JSON and writes one JSON object per
request. A one-request invocation may close stdin immediately after its JSON
object. Each request has this shape:

```json
{"text": "Powiedział że jutro wróci.", "language": "pl-PL"}
```

Only `pl-PL` is accepted. The process keeps one `JLanguageTool(new Polish())`
instance warm between requests. Responses contain genuine LanguageTool 6.8
rule identifiers, offsets, replacement candidates, and rule metadata.

## Verification and benchmark

Run static provenance and boundary checks with:

```bash
./scripts/verify.sh
```

Run the real engine against every case in the Polish correction corpus with:

```bash
./scripts/benchmark.sh
```

The benchmark derives its oracle directly from corpus gold edits; it does not
consult the recorded LanguageTool snapshot. It reports qualified punctuation
and all-gold metrics, per-case false negatives, hard-negative changes, cold
startup, warm p50/p95 latency, peak RSS, and runtime disk size. The measured
baseline and limitations are in `BENCHMARK.md`.

## Directory map

- `sources/` — complete corresponding source for the included upstream paths;
- `patches/` — reviewed changes to upstream build metadata;
- `src/main/java/` — project-authored stdio integration boundary;
- `manifest.json` — revision, included/excluded paths, modifications, and build metadata;
- `UPSTREAM.md` — exact upstream source and retrieval instructions;
- `scripts/` — bootstrap, build, run, benchmark, and verification entry points;
- `LICENSE-LGPL-2.1.txt` and `NOTICE` — licensing and provenance notices.

The upstream source derivative is LGPL-2.1-or-later. Project-authored Python
code remains MIT-licensed and communicates with this optional module as a
separate local process.
