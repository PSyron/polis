# Residual sentence syntax evaluation

This experiment qualifies two deterministic sources for three deliberately
narrow Polish sentence constructions:

- missing `się` after sentence-initial `On`, `Ona`, or `Ono` plus `boi`;
- missing `się` after sentence-initial `Nie spodziewaliśmy`;
- missing `tym` in sentence-initial `Im …, bardziej …`.

It does not evaluate or claim paragraph correction, broad reflexive-verb
coverage, general word-order rewriting, or model-backed syntax correction.
Detection receives only the source sentence. Scoring compares the emitted
`[start, end)` edit tuples with independently reviewed gold edits after the
rule run; gold categories and tags are not visible to detection.

Run development and freeze the exact implementation only if its gates pass:

```console
python -m experiments.residual_syntax_rules.run_evaluation \
  --split development \
  --output experiments/residual_syntax_rules/report.json \
  --frozen experiments/residual_syntax_rules/frozen_rules.json
```

The holdout is reserved once, before any holdout case is loaded. It requires
the qualified development report and matching frozen hashes:

```console
python -m experiments.residual_syntax_rules.run_evaluation \
  --split holdout \
  --output experiments/residual_syntax_rules/report.json \
  --development-report experiments/residual_syntax_rules/report.json \
  --frozen experiments/residual_syntax_rules/frozen_rules.json \
  --holdout-marker experiments/residual_syntax_rules/holdout.started
```

The committed report contains case IDs, counts, edit hashes, exact-match
flags, and latency only. It contains no source sentences, expected outputs,
or visible edit material.
