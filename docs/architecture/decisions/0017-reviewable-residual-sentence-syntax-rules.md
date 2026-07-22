# ADR-0017: Keep residual sentence syntax rules reviewable

- Status: Accepted
- Date: 2026-07-22
- Owner: Paweł Cyroń
- Issue: #75

## Context

ADR-0016 rejected all tested Qwen3 1.7B operations for residual Polish syntax
and permitted a narrower deterministic path. Issue #75 therefore froze two
source-only rules for exactly three sentence-initial constructions: missing
`się` after `On`, `Ona`, or `Ono` plus `boi`; missing `się` after
`Nie spodziewaliśmy`; and missing `tym` in `Im …, bardziej …`.

The development split contained 69 independently reviewed corpus-v3 sentences.
The rules emitted three exact edits, all true positives, for edit precision
1.00 and overall edit recall 0.0423. They changed no hard negative. Warm p95 was
0.012 ms on the target Mac mini. The implementation and configuration were then
frozen before reserving the holdout once.

The holdout contained 142 sentences but no eligible occurrence of the three
constructions. The rules emitted zero edits, changed no hard negative, and had
overall edit recall 0.00. A zero-edit result cannot establish non-vacuous edit
precision, even though it introduces no observed false positive.

## Decision

Register both rules in the default analyzer as sentence-only, reviewable
findings with stable sources `rule:syntax.missing_reflexive` and
`rule:syntax.missing_correlative`. Do not add either source to automatic
correction policy `1.1`. `Analyzer.correct()` must leave these findings in
`skipped_findings` until a caller explicitly selects them.

Do not claim broader reflexive-verb detection, word-order correction, paragraph
coverage, or model-assisted syntax correction. A future automatic-policy change
requires new isolated evaluation data containing eligible positive constructions
and protected near-negatives, followed by a separately authorized gate.

## Consequences

- The three development examples now produce useful minimal suggestions without
  a local model or additional runtime memory.
- Automatic correction remains conservative because the holdout lacked positive
  coverage.
- Other syntax errors continue to be missed by design.
- Multi-sentence input is rejected by these rules before pattern matching.

## Alternatives considered

- **Treat zero holdout edits as precision 1.00.** Rejected because this would
  qualify automatic correction without any positive holdout evidence.
- **Broaden patterns after viewing holdout.** Rejected because it would violate
  the frozen one-shot protocol and increase false-positive risk.
- **Enable the rejected Qwen3 route.** Rejected by ADR-0016 for failing the
  accepted precision, recall, and response-validity gates.
