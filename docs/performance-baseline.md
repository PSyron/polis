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
