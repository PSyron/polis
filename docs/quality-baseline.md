# Quality Baseline (M3-02)

Baseline run date: `2026-07-20`.

## Evaluation configuration

- Dataset: `src/polis/evaluation/datasets/v1/cases.json`
- Dataset id: `polis_pl_initial_v1`
- Schema version: `1`
- Canonical dataset SHA-256: `d3e06798950d5d0ca5af6d61d56e7b5ba6c423e72d1d765b41e214fda47a042a`
- Cases: `17` (`9` incorrect / `8` correct)
- Analyzer configuration:
  - Registry: `SpellingJestesRule`, `SpellingWlasnieRule`, `SpellingZebyRule`,
    `AgreementCopulaRule`, `SyntaxListSpacingRule`, `SyntaxCommaSpacingRule`,
    `SyntaxQuoteSpacingRule`
  - Sources enabled: `rule`; `llm` backend tested separately as zero-variance control

## Metric definitions

An exact edit matches the gold category, half-open span, original fragment, and
replacement. Let `TP` be exact edit matches, `FP` be emitted edits without an
exact gold match, and `FN` be gold edits without an exact emitted match. A
prediction at a gold span with the wrong replacement is therefore both one
`FP` and one `FN`.

- Exact-edit precision is `TP / (TP + FP)`.
- Exact-edit recall is `TP / (TP + FN)`.
- Exact-edit F1 is `2TP / (2TP + FP + FN)`.
- Span accuracy is `matched gold spans / gold edits`.
- Correction accuracy is `exact replacements / matched gold spans`.
- False-discovery proportion is `FP / (TP + FP)`. This is not a
  false-positive rate because its denominator contains emitted findings rather
  than negative cases.
- Correct-sentence false-alarm rate is
  `correct cases with at least one emitted finding / correct cases`. Multiple
  findings in one correct sentence count as one alarmed case.

A metric with a zero denominator is reported as `N/A`, never as a perfect
score. `N/A` fails both minimum and maximum release gates, so an empty analyzer
or a dataset without the required negative cases cannot qualify vacuously.

## Aggregate quality

| Metric | Value |
| --- | ---: |
| Exact-edit precision | `1.0000` |
| Exact-edit recall | `0.2222` |
| Exact-edit F1 | `0.3636` |
| Span Accuracy | `0.2222` |
| Correction Accuracy | `1.0000` |
| False-discovery proportion | `0.0000` |
| Correct-sentence false-alarm rate | `0.0000` |
| True Positives | `2` |
| False Positives | `0` |
| False Negatives | `7` |
| Expected Findings | `9` |
| Predicted Findings | `2` |
| Correct Cases | `8` |
| Alarmed Correct Cases | `0` |

## By category

| Group | Edit Prec. | Edit Recall | Edit F1 | Span Acc. | Corr. Acc. | False Discovery | Correct Alarm | TP | FP | FN | Exp | Pred |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| inflection | N/A | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0.0000 | 0 | 0 | 1 | 1 | 0 |
| agreement | 1.0000 | 0.5000 | 0.6667 | 0.5000 | 1.0000 | 0.0000 | 0.0000 | 1 | 0 | 1 | 2 | 1 |
| syntax | 1.0000 | 0.5000 | 0.6667 | 0.5000 | 1.0000 | 0.0000 | 0.0000 | 1 | 0 | 1 | 2 | 1 |
| spelling | N/A | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0.0000 | 0 | 0 | 1 | 1 | 0 |
| punctuation | N/A | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0.0000 | 0 | 0 | 2 | 2 | 0 |
| style | N/A | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0.0000 | 0 | 0 | 1 | 1 | 0 |

## By source

| Group | Edit Prec. | Edit Recall | Edit F1 | Span Acc. | Corr. Acc. | False Discovery | Correct Alarm | TP | FP | FN | Exp | Pred |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rule | 1.0000 | 0.2222 | 0.3636 | 0.2222 | 1.0000 | 0.0000 | 0.0000 | 2 | 0 | 7 | 9 | 2 |
| llm | N/A | 0.0000 | 0.0000 | 0.0000 | N/A | N/A | 0.0000 | 0 | 0 | 9 | 9 | 0 |

## Reproducibility and variance check

Two full evaluations were executed for M3-02:

1. Rules-only analyzer
2. Rules + configured mock local backend

The two runs are identical on this dataset:

- Aggregate metrics are exactly equal.
- `rule` source metrics are identical.
- `llm` source produced no findings under current mock backend prompt schema.

## Release gates (enforced in tests)

| Gate | Value |
| --- | ---: |
| `exact_edit_precision` | `>= 1.0000` |
| `exact_edit_recall` | `>= 0.2222` |
| `exact_edit_f1` | `>= 0.3600` |
| `span_accuracy` | `>= 0.2200` |
| `correction_accuracy` | `>= 1.0000` |
| `false_discovery_proportion` | `<= 0.0000` |
| `correct_sentence_false_alarm_rate` | `<= 0.0000` |

Every gate requires a defined metric; `N/A` is a gate failure.

Known limitations:

- `llm` source is currently deterministic and returns no additional structured findings for this seed dataset.
- `syntax` and `spelling` coverage is intentionally minimal and should be expanded in later roadmap items to raise recall.
