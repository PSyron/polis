# LanguageTool Polish Rule Inventory Design

- Status: Accepted for issue #70
- Date: 2026-07-22
- Owner: Paweł Cyroń

## Objective

Discover which additional upstream LanguageTool 6.8 Polish rules can safely
improve correction of one sentence. Inspection must not broaden the existing
production `check` operation or its two-rule allowlist.

## Alternatives

1. **Separate inspection operation — selected.** Add an explicit `inspect`
   request to the local stdio bridge. It returns all upstream Polish matches to
   an experiment, while `check` continues filtering exactly the two existing
   rule IDs.
2. **Temporarily widen `check`.** Rejected because experiment configuration
   could leak into production behavior and invalidate the existing source
   policy.
3. **Parse Polish grammar XML statically.** Rejected because rule definitions
   alone do not measure tagger behavior, offsets, replacements, conflicts, or
   protected negatives on real sentences.

## Protocol isolation

`{"operation":"inspect","language":"pl-PL","text":"..."}` is accepted only
by the vendored stdio process. Its response includes `operation=inspect`, pinned
software identity, and unfiltered upstream matches. The default operation stays
`check`, keeps its current response shape, and emits only
`BRAK_PRZECINKA_ZE` and `BRAK_PRZECINKA_ZEBY`. Synthesis is unchanged.

The bridge never receives corpus IDs, labels, tags, expected output, or gold
spans. Python sends only sentence source text. Raw inspection responses stay in
an ignored private work directory; committed evidence contains rule IDs,
counts, hashes, timings, and resource measurements only.

## Scoring and selection

Development contains the 69 sentence cases from corpus v3. Every replacement
from every rule match is normalized to a Unicode code-point half-open edit. A
rule cannot choose the best replacement using gold: all distinct proposed edits
count. Rules without usable replacements are inventoried but cannot qualify.

Per-rule TP, FP, FN, exact outputs, protected-negative changes, and categories
are reported. A candidate rule ID requires at least one exact TP, precision
1.00, and zero edits on protected negatives. The combined candidate allowlist
must also retain precision 1.00, have no conflicts or protected changes, and
produce only application-valid edits. No production source-policy changes are
made by this research issue.

The allowlist is frozen with the corpus, bridge, configuration, and candidate
rule hashes before holdout. Holdout may run once only if development yields a
non-empty qualifying allowlist. Otherwise it remains unopened.

## Verification

Fast tests cover operation isolation, closed request/response shapes, Unicode
offsets, all-replacement scoring, gold-independent inputs, deterministic
selection, report privacy, and holdout-once reservation. Slow tests build and
run the real vendored module. Repository-wide quality, distribution, and
offline integration checks remain required.
