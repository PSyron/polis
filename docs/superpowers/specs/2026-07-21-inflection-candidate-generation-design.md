# Deterministic Inflection Candidate Generation Design

## Status and scope

This design implements GitHub issue #58 as an experiment over the pinned
LanguageTool 6.8 Polish module delivered by #54. It does not add a production
dependency, select a contextually correct form, or apply a correction.

## Considered approaches

1. Extend the existing local LanguageTool stdio bridge with a `synthesize`
   operation. This reuses the pinned build, warm process, Polish tagger,
   synthesizer, licensing boundary, and resource measurements. This is the
   selected approach.
2. Add a separate experiment-only Java executable. This isolates research code
   but duplicates process management, JSON validation, classpath assembly, and
   runtime measurements.
3. Add Morfeusz 2 through Python. It offers strong Polish morphology, but it
   would bypass the required LanguageTool-first evaluation and introduce a new
   packaging path before a gap is demonstrated.

## Boundary and data flow

The existing newline-delimited JSON process accepts its current check request
unchanged. A synthesis request has `operation: "synthesize"`, `language:
"pl-PL"`, source `text`, and one or more half-open `[start, end)` spans. Each
span must select one non-empty token in the original text.

The bridge tags only the selected surface with the real `PolishTagger`. For
each supported noun or adjective analysis, it enumerates compatible upstream
Polish tags and asks the real `PolishSynthesizer` for forms. It does not inspect
corpus expectations. Results are deduplicated deterministically and preserve
the source capitalization pattern. Every span includes the unchanged surface;
unknown or unsupported analyses return only that safe candidate plus an
explicit reason.

The candidate record contains a stable content-derived ID, original span,
optional lemma, form, and sorted morphological features. It claims only that
LanguageTool can synthesize the form for the analysis, never that the form is
correct in sentence context.

## Experiment and metrics

Authored fixtures cover nouns, adjectives, first names, surnames,
capitalization, diacritics, an indeclinable name, an unknown token, already
inflected forms, and duplicate analyses. A Python runner also evaluates every
single-token inflection edit in the frozen v3 corpus. Gold data identifies the
target span and measures recall only; it is never sent as a lemma, tag, or
candidate.

Reports separate ordinary words, first names, and surnames. For each class they
record expected-form recall, mean and p95 distinct-form ambiguity, unsupported
counts, and unchanged-form coverage. Runtime evidence includes cold startup,
warm p50/p95 latency, peak RSS, runtime disk footprint, upstream revision, and
license. Reports contain case IDs and metrics, not private text.

Morfeusz is evaluated later only if LanguageTool misses a required class or has
insufficient recall for finite-candidate prompting. The ADR records the result
and whether #58 can supply independent candidates to #57/#63.

## Validation and failure behavior

Malformed operations, languages, spans, or non-token spans fail before
synthesis. Duplicate candidates merge deterministically. Missing analyses,
unsupported POS classes, and synthesizer misses are data outcomes rather than
process failures. The current punctuation-check protocol remains backward
compatible.

Fast Python tests use authored response fixtures and fake transports. Java
source-policy tests assert use of the upstream tagger and synthesizer and reject
corpus lookup tables. A slow offline integration test runs the built bridge;
the full Java build and verification scripts remain mandatory for completion.
