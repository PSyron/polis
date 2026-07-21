# Local LanguageTool Benchmark Design

## Decision scope

Issue #52 determines whether the open-source LanguageTool 6.8 server is a
credible deterministic Polish analysis layer. It does not add Java or
LanguageTool to the production package and does not wire the server into
`Analyzer`.

## Considered approaches

1. Call the public LanguageTool API. This is rejected because it sends text
   off-device, is rate-limited, and can run rules that differ from the
   open-source distribution.
2. Embed LanguageTool through Java. This gives direct access to Java objects,
   but it would couple an experiment to a JVM bridge and obscure the eventual
   process boundary.
3. Run the pinned local HTTP server and benchmark `/v2/check`. This is the
   selected approach because it preserves the offline boundary, exercises the
   documented integration surface, and keeps the Python package dependency
   free.

## Architecture

The experiment has three boundaries. A loopback-only HTTP client sends form
POST requests with `language=pl-PL`. A strict parser validates the response,
converts Java UTF-16 offsets to Python Unicode code-point offsets, and retains
all replacement alternatives and LanguageTool rule metadata. A scorer compares
normalized matches with explicit corpus gold edits and produces an auditable
report without raw analyzed text.

LanguageTool is treated as a rule engine, not an LLM. A production follow-up,
if justified, belongs under `polis.rules` and must remain replaceable. Unknown
LanguageTool categories remain `unmapped`; the experiment never guesses that a
generic grammar match is specifically agreement or inflection.

## Scoring and correction

Each prediction is matched one-to-one with a gold edit. An exact correction
requires the same source range and original text plus the gold suggestion
among LanguageTool's alternatives. Duplicate predictions are false positives.
A same-span prediction with no correct alternative is both a false positive
and a false negative.

Two text-level measurements stay separate:

- `top_replacement_output` applies the first usable replacement for each
  non-overlapping match in deterministic order;
- `gold_reachable` reports whether LanguageTool offered the required gold
  edits, even when they were not its first choices.

Any changing suggestion on a correct negative case fails negative safety.
Overlaps are recorded and skipped deterministically rather than silently
resolved.

## Reproducibility and privacy

The live run is pinned to LanguageTool 6.8 and a loopback endpoint. The report
records the tool version, corpus SHA-256, mapping/scoring versions, p50/p95
latency, startup time when supplied, and server RSS when supplied. Case records
contain identifiers and counts, not raw inputs, outputs, prompts, or responses.
Fast tests use authored synthetic responses; the real server test is marked
`slow`.

## Acceptance decision

The ADR will choose one of three outcomes: reject the candidate, keep it only
as benchmark evidence, or open a separate production integration issue. A
production recommendation requires zero changed negatives and measured value
over the existing rules. It does not relax the LLM quality gates or make
LanguageTool's first replacement automatically applicable.
