# Performance Baseline (M3-03)

Date: `2026-07-20`

## Goal and scope

Measure offline latency, throughput, and memory for the rule-only pipeline and for the
same pipeline with the mock local backend attached.

## Method

- Dataset: `src/polis/evaluation/datasets/v1/cases.json`
- Seed and slice: `m3-03-v1`
- Configurations:
  - `rules-only`
  - `rules+mock-llm`
- Warmup repetitions: `1`
- Measured repetitions per case: `2`
- Environment: recorded in the JSON report (`macOS-15.3.1-arm64-arm-64bit-Mach-O`).

The benchmark is intentionally narrow and machine-generated JSON-only for auditability:

- `experiments/performance/run_benchmark.py --repetitions 2 --warmup 1 --output experiments/performance/results.json`
- No analyzed text is embedded; per-case payload stores only case id and input size.

## Reproducibility

The report includes:

- software and hardware fingerprints,
- dataset id/schema/path and SHA-256 snapshot,
- per-config latency distributions (min/max/mean/median/p50/p95/count),
- throughput in chars/sec and cases/sec,
- peak memory in bytes,
- per-case latency distributions.

## Observed results

| Metric | Rules only | Rules + mock LLM |
| --- | ---: | ---: |
| Input cases | `17` | `17` |
| Repetitions | `2` | `2` |
| Repetitions measured | `34` samples per run | `34` samples per run |
| Mean latency (ms) | `0.2128` | `0.2955` |
| P95 latency (ms) | `0.2638` | `0.3509` |
| Throughput (chars/sec) | `53,773.21` | `38,723.80` |
| Throughput (cases/sec) | `4,699.97` | `3,384.60` |
| Peak memory (bytes) | `41,031` | `33,020` |

## Outcome

This baseline is reproducible under the current repository state and demonstrates that
adding the mock local backend introduces measurable latency in this benchmark slice while
remaining deterministic.

The benchmark and artifacts are intentionally kept lightweight for fast local checks and
are suitable for full-system baseline updates before release.

## Persistent vendored LanguageTool sentence baseline (#77)

Date: `2026-07-22`. The source-only benchmark used the 69 corpus-v3 development
sentence cases, one warmup pass, and two measured passes on
`macOS-15.3.1-arm64` with Python 3.13.12 and the pinned LanguageTool 6.8 subset.
The report is
`experiments/languagetool_stdio_session/report.json`; it contains identifiers,
hashes, counts, and measurements but no analyzed text.

| Metric | Measured result |
| --- | ---: |
| Cold first request | `938.60 ms` |
| Warm p50 | `2.77 ms` |
| Warm p95 | `5.08 ms` |
| Throughput | `327.98` cases/second |
| Combined Python + Java RSS | `441,483,264 bytes` |
| Process starts | `1` |
| Network sockets | `0` (zero network sockets) |
| Swap growth | `0 bytes` |
| Repeatable cases | `69 / 69` |

The frozen gates were warm p95 at most 500 ms, combined RSS at most 1 GiB,
zero swap growth, zero sockets, one process, and repeatable findings for all 69
cases. This sentence-only local transport qualified. It does not establish
paragraph quality or broad Polish grammar coverage.

## Installed sentence safety development checkpoint (#115)

Date: `2026-07-23`. The fresh-wheel development run processed 80 independent
sentence cases twice on `macOS-15.3.1-arm64` with CPython 3.13.12 and the pinned
LanguageTool 6.8 runtime.

| Metric | Measured result |
| --- | ---: |
| Cold installed request | `973.83 ms` |
| Warm in-process p50 / p95 | `5.41 / 10.68 ms` |
| Warm installed-runner p50 / p95 | `5.67 / 11.25 ms` |
| Throughput | `81.89` cases/second |
| Character throughput | `5,110.02` characters/second |
| Combined loaded/peak RSS | `376,569,856 bytes` |
| Process starts | `1` |
| Network sockets | `0` |
| Swap growth | `0 bytes` |
| Model calls | `0` |
| Stable repetitions | `2` |

All development performance and privacy gates qualified. The one-shot holdout
was subsequently executed once and did not qualify on reviewable precision.

### One-shot holdout performance

| Metric | Measured result |
| --- | ---: |
| Cases | `160` |
| Cold installed request | `950.21 ms` |
| Warm in-process p50 / p95 | `5.31 / 7.65 ms` |
| Warm installed-runner p50 / p95 | `5.49 / 7.77 ms` |
| Throughput | `114.96` cases/second |
| Character throughput | `7,071.03` characters/second |
| Combined loaded/peak RSS | `415,662,080 bytes` |
| Process starts | `1` |
| Network sockets | `0` |
| Swap growth | `0 bytes` |
| Model calls | `0` |
| Stable repetitions | `2` |

Every holdout performance and privacy threshold passed. These measurements do
not override the failed reviewable precision gate.
