# Polish LanguageTool sentence-rule inventory

Issue #70 inventories upstream LanguageTool 6.8 rules on one Polish sentence
at a time. The experiment-only `inspect` operation exposes every upstream
match, while the production `check` operation retains its existing two-rule
allowlist.

## Frozen decision

Development used 69 reviewed sentence cases from corpus v3. Four punctuation
rules qualified with exact edit precision 1.00, no conflicts, no invalid edit
applications, and no changes to protected negatives:

- `BRAK_PRZECINKA_KTORY`
- `BRAK_PRZECINKA_SPOJNIK_PROSTY`
- `BRAK_PRZECINKA_ZE`
- `WOLACZ_BEZ_PRZECINKA`

The frozen selection records the configuration and Java bridge SHA-256 values.
The 142-sentence holdout was reserved and run once. It retained precision 1.00
with 5 true-positive edits, 0 false-positive edits, 0 protected-negative
changes, and 0 invalid applications. Recall remained low at 0.038. Complete
output exactness was 18/69 on development and 37/142 on holdout; these totals
include already-correct sentences that appropriately remained unchanged.

| Split | TP / FP / FN | Precision / recall | Warm p95 | Peak RSS |
| --- | ---: | ---: | ---: | ---: |
| Development | 4 / 0 / 67 | 1.000 / 0.056 | 6.4 ms | 359,481,344 B |
| Holdout | 5 / 0 / 127 | 1.000 / 0.038 | 5.9 ms | 355,434,496 B |

The built runtime occupied 54,072,523 bytes. Cold startup was about 0.9 s.
`report.json` contains only identifiers, counts, hashes, timings, and boolean
outcomes; it contains no source sentences or raw LanguageTool responses.

## Reproduction

Build the pinned source subset without network access, then run development and
freeze a qualifying selection:

```bash
POLIS_LT_OFFLINE=1 third_party/languagetool-pl/scripts/build.sh
uv run --locked --extra dev python -m \
  experiments.languagetool_rule_inventory.run_benchmark \
  --output experiments/languagetool_rule_inventory/report.json \
  --freeze experiments/languagetool_rule_inventory/frozen_allowlist.json
```

The holdout command is intentionally one-shot. It atomically creates
`holdout.started` before inspecting any holdout sentence and refuses a second
run:

```bash
uv run --locked --extra dev python -m \
  experiments.languagetool_rule_inventory.run_benchmark \
  --output experiments/languagetool_rule_inventory/report.json \
  --holdout \
  --frozen experiments/languagetool_rule_inventory/frozen_allowlist.json \
  --holdout-marker experiments/languagetool_rule_inventory/holdout.started
```

Qualification is evidence for a separate source-policy change. This issue does
not broaden production correction automatically.
