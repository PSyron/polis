# Polish LanguageTool Sentence Subset Benchmark

- Date: 2026-07-22
- Corpus SHA-256: `d5ce257f78a67ad2bdc6ed71ed1ec4f4403d0f287a71db7a316e68bd32f4d468`
- LanguageTool: 6.8, upstream commit `e807fcde6a6506191e1470744d2345da28c26be6`
- Runtime: OpenJDK 17.0.19, Apple M4, 16 GiB RAM, macOS 15.3.1
- Command: `./scripts/benchmark.sh`

The benchmark exercised the current five-rule source-built Polish engine
through one local
stdio process. Its oracle came from all 33 corpus cases, not from the recorded
LanguageTool snapshot.

| Measurement | Result |
| --- | ---: |
| Qualified punctuation TP / FP / FN | 20 / 0 / 4 |
| Qualified precision / recall / F1 | 1.000 / 0.833 / 0.909 |
| All-gold TP / FP / FN | 20 / 0 / 30 |
| All-gold precision / recall / F1 | 1.000 / 0.400 / 0.571 |
| Hard negatives unchanged | 10 / 10 |
| Cold process plus first check | 933.1 ms |
| Warm p50 / p95 | 3.9 / 7.0 ms |
| Peak RSS | 358,336 KiB (350.0 MiB) |
| Thin JAR plus runtime libraries | 54,043,536 bytes (51.5 MiB) |

Compared with the general 6.8 installation recorded in ADR-0006, the runtime
footprint fell from 413.7 MB to 51.5 MiB and RSS from 629.8 MiB to 350.0 MiB.
Warm checks and the measured cold startup were faster. Timing and RSS values
remain machine-state-sensitive measurements, while the corpus scores and disk
footprint are deterministic for the pinned source and toolchain.

The scope is intentionally narrow. It does not fix spelling, agreement,
inflection, word order, every paired relative-clause or vocative comma, or
spacing edits. Every missed gold edit is counted in the all-gold false-negative
total and preserved in the per-case JSON report generated with `--json PATH`.
The independent corpus-v3 selection and one-shot holdout evidence is in
`../../experiments/languagetool_rule_inventory/report.json`.

## Inflection candidate generation

Issue #58 measured the same pinned process through its real `PolishTagger` and
`PolishSynthesizer`. On 24 eligible development edits and 34 eligible holdout
edits from frozen corpus v3, expected-form recall and unchanged-form coverage
were both 1.000 in ordinary-word, first-name, and surname classes. Warm p95 was
2.68 ms on development and 1.75 ms on holdout. The separate candidate run
measured 566.4 ms cold start, 367,099,904 bytes peak RSS, 54,072,194 bytes of
runtime artifacts, and 8,821,678 bytes of Polish resources.

The candidate set is deliberately recall-oriented. Mean distinct-form
ambiguity was 23.5 for ordinary development words and 11.1 for development
surnames; p95 reached 41 and 16 respectively. A later selector must use context
without treating any synthesized alternative as a correction. Exact commands,
authored edge cases, class tables, and licensing consequences are in
`../../experiments/inflection_candidates/README.md`.
