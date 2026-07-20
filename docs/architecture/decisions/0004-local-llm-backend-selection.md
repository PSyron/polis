# ADR-0004: Select the first offline local backend approach for MVP LLM integration

- Status: Accepted
- Date: 2026-07-20
- Owner: Paweł Cyroń
- Issue: #17

## Context

Milestone `M2` requires a concrete local generation strategy before schema,
retry, and orchestration work can proceed. At repository level this project has:

- no guaranteed external model server in local CI,
- strict offline requirements,
- no runtime model dependency yet,
- no evidence for a production-grade local-serving stack under our supported matrix.

For `M2-01` we therefore ran a constrained benchmark using three mock offline
backend candidates over a fixed Polish slice and exact seed slices in the
repository. The goal is to select a deterministic, reproducible integration
point that can evolve later without reworking orchestration seams.

## Decision

Select **`mock-heu`** as the first backend identifier for MVP integration:

- It is fully local, has no external dependencies, and is offline-by-default.
- It reports deterministic JSON spans for known spellings from the seeded slice.
- It scored highest mean F1 against the evidence slice with no malformed responses.
- It is fast and reproducible in CI and local environments.

Rejection rationale:

- `mock-empty` never produces findings (quality 0.0), so it cannot progress
  error-correction capability for the first backend slot.
- `mock-noisy` produces extra findings on non-errors (precision drop), which is
  high-risk for user trust before stronger validation exists.

## Evidence snapshot

The benchmark script writes:

- per-backend mean F1, precision, recall, total/average latency, success rate,
  malformed-response count,
- the selected backend with deterministic tie-breakers,
- reproducible benchmark slice definition,
- environment metadata (platform, CPU hints, python runtime), and
- reproducibility settings (seed, backend candidate order, selection metric).

The accepted evidence is in `experiments/llm_backends/results.json`.

An example of the recorded evidence metadata layout is:

```json
{
  "settings": {
    "seed": "m2-01-heuristic-v1",
    "candidates": ["mock-empty", "mock-heu", "mock-noisy"],
    "selection_metric": "mean_f1_then_latency",
    "offline_only": true
  },
  "environment": {
    "hardware": {
      "platform": "macOS-...",
      "machine": "arm64",
      "processor": "arm"
    },
    "software": {
      "python": "3.13.12",
      "python_implementation": "CPython"
    }
  }
}
```

## Implementation consequences

- `mock-heu` is recorded as the seed backend in `M2-02` schema and prompt
  contract work.
- Later real runtimes (for example local command/server adapters) must reuse the
  same contract and pass the same validation and offline checks before replacing
  or adding candidates.
- The benchmark remains lightweight and repository-local, and does not claim to
  measure semantic model quality beyond the seeded slice used in this stage.

## Verification

```bash
uv run python experiments/llm_backends/run_benchmark.py \
  --output experiments/llm_backends/results.json
uv run python experiments/llm_backends/run_benchmark.py \
  --validate --results experiments/llm_backends/results.json
```
