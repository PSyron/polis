# Local LLM backend benchmark artifacts

This folder stores the milestone `M2-01` evidence and reproducible results for the
first local backend selection.

The benchmark compares lightweight mock backends on the same Polish test slice:

- deterministic runtime score (mean wall-clock latency and success rate),
- quality score (precision / recall / F1 against seeded expectations),
- operational reliability (malformed-response rate under strict schema validation).

All backends are offline and repository-local by design.

## Running the benchmark

```console
python experiments/llm_backends/run_benchmark.py \
  --output experiments/llm_backends/results.json
```

Use `--validate` to rerun the same harness against an existing JSON result:

```console
python experiments/llm_backends/run_benchmark.py \
  --validate \
  --results experiments/llm_backends/results.json
```

The first command writes a machine-readable JSON report and a short console summary.

## Seed data

The benchmark slice lives in `run_benchmark.py` to keep the experiment
self-contained and avoid external resources. Every input is intentionally small and
uses Polish phrases that are also covered in repository-owned rule tests.
