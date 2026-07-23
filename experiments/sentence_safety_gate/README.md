# Installed-package sentence safety gate

This experiment re-qualifies the sentence-only installed-package behavior
tracked by #76 against the independent corpus created by #114. It selectively
ports the evaluator from the closed, unmerged PR #79, but does not reuse that
PR's corpus-v3 configuration, results, frozen hashes, or consumed holdout
marker.

The runner exercises the public `Analyzer.analyze()`, `Analyzer.correct()`, and
`CorrectionResult.apply_suggestions()` paths from a clean wheel installation.
Gold edits remain in the repository-side scorer and are never sent to the
installed process.

## Evaluated source boundary

`evaluated_source.json` binds the frozen wheel and sdist to commit
`24cda9ae664bcdf9d486ae713ad426257e614085` and tree
`f42ff0b8ccb5a4241c10be2dcd1a0c8976a635b8`. That immutable snapshot produced
the development and one-shot results retained here.

The final marker, report, documentation, CI portability fix, durable-reservation
maintenance, and removal of the rejected nominal-agreement extension are
post-verdict changes. They are deliberately not represented as holdout-tested
behavior. `frozen_gate.json`, `holdout.started`, and `report.json` remain the
unaltered evidence from the consumed run; the holdout must not be loaded or run
again.

## Development phase

Build the vendored runtime without network access:

```bash
POLIS_LT_OFFLINE=1 third_party/languagetool-pl/scripts/build.sh
```

Build fresh distributions:

```bash
python -m build --no-isolation \
  --outdir /private/tmp/polis-sentence-safety-dist
```

Run the 80-case development split and freeze a qualifying report:

```bash
uv run python -m experiments.sentence_safety_gate.run_evaluation \
  --development \
  --config experiments/sentence_safety_gate/config.json \
  --dist /private/tmp/polis-sentence-safety-dist \
  --vendored-stdio "$PWD/third_party/languagetool-pl/scripts/run_stdio.sh" \
  --output experiments/sentence_safety_gate/report.json \
  --freeze experiments/sentence_safety_gate/frozen_gate.json
```

Development streams only records whose split is `development`. It cannot
materialize the holdout or create `holdout.started`.

### Frozen development result

The `2026-07-23` development execution qualified:

| Channel | TP | FP | Precision | Correction accuracy |
| --- | ---: | ---: | ---: | ---: |
| Automatic | `10` | `0` | `1.00` | `1.00` |
| Reviewable | `18` | `0` | `1.00` | `1.00` |

Structured outcome validity was `1.00`; protected hard negatives had zero
automatic changes and zero reviewable findings. Both repetitions were stable,
with zero sockets, swap growth, and model calls. Exact report, artifact, and
configuration hashes are retained in `frozen_gate.json`.

The report's top-level decision remains false by design until a holdout result
exists; `development.decision.qualified` is the qualifying checkpoint verdict.

## Final one-shot result

Paweł Cyroń authorized the irreversible holdout after the qualifying
development checkpoint. The evaluator reserved and scored all 160 holdout cases
exactly once on `2026-07-23`.

| Channel | TP | FP | Precision | Correction accuracy |
| --- | ---: | ---: | ---: | ---: |
| Automatic | `11` | `0` | `1.00` | `1.00` |
| Reviewable | `0` | `2` | `0.00` | `1.00` |

The overall result did not qualify because reviewable precision was below the
required `0.90`. Structured validity was `1.00`; protected hard negatives had
zero automatic changes and zero reviewable findings. Offline, artifact,
performance, stability, process, socket, swap, and model-call gates passed.

`holdout.started` is retained and matches `frozen_gate.json`. The final report
canonical SHA-256 is
`ec43b1691a6d4a348ecd1ce01cd537cf7fac32ae5e9f7d52cf49d20ca2adb706`;
the marker raw SHA-256 is
`198371e64acb4fe04c8b2ae962e172b37e61ef3149b2d832c97175bde10f4d82`.
The holdout is consumed and must not be rerun or used for tuning. Issue #76
remains open.

The nominal-agreement extension evaluated by this snapshot was removed from
active runtime after the failed verdict. This preserves the negative evidence
without promoting the rejected behavior.
