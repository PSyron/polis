# Quality Baseline (M3-02)

Baseline run date: `2026-07-20`.

## Evaluation configuration

- Dataset: `src/polis/evaluation/datasets/v1/cases.json`
- Dataset id: `polis_pl_initial_v1`
- Schema version: `1`
- Dataset SHA-256: `9da57f054a4d6793e76436d4a786e1ab1872cfc437c1689f8db8a7c1d73f88b3`
- Cases: `17` (`9` incorrect / `8` correct)
- Analyzer configuration:
  - Registry: `SpellingJestesRule`, `SpellingWlasnieRule`, `SpellingZebyRule`,
    `AgreementCopulaRule`, `SyntaxListSpacingRule`, `SyntaxCommaSpacingRule`,
    `SyntaxQuoteSpacingRule`
  - Sources enabled: `rule`; `llm` backend tested separately as zero-variance control

## Aggregate quality

| Metric | Value |
| --- | ---: |
| Precision | `1.0000` |
| Recall | `0.2222` |
| F1 | `0.3636` |
| Span Accuracy | `0.2222` |
| Correction Accuracy | `1.0000` |
| False Positive Rate | `0.0000` |
| True Positives | `2` |
| False Positives | `0` |
| False Negatives | `7` |
| Expected Findings | `9` |
| Predicted Findings | `2` |

## By category

| Group | Precision | Recall | F1 | Span Acc. | Corr. Acc. | FP Rate | TP | FP | FN | Exp | Pred |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| inflection | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0 | 0 | 1 | 1 | 0 |
| agreement | 1.0000 | 0.5000 | 0.6667 | 0.5000 | 1.0000 | 0.0000 | 1 | 0 | 1 | 2 | 1 |
| syntax | 1.0000 | 0.5000 | 0.6667 | 0.5000 | 1.0000 | 0.0000 | 1 | 0 | 1 | 2 | 1 |
| spelling | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0 | 0 | 1 | 1 | 0 |
| punctuation | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0 | 0 | 2 | 2 | 0 |
| style | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0 | 0 | 1 | 1 | 0 |

## By source

| Group | Precision | Recall | F1 | Span Acc. | Corr. Acc. | FP Rate | TP | FP | FN | Exp | Pred |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rule | 1.0000 | 0.2222 | 0.3636 | 0.2222 | 1.0000 | 0.0000 | 2 | 0 | 7 | 9 | 2 |
| llm | 1.0000 | 0.0000 | 0.0000 | 0.0000 | 1.0000 | 0.0000 | 0 | 0 | 9 | 9 | 0 |

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
| `precision` | `>= 1.0000` |
| `recall` | `>= 0.2222` |
| `f1` | `>= 0.3600` |
| `span_accuracy` | `>= 0.2200` |
| `correction_accuracy` | `>= 1.0000` |
| `false_positive_rate` | `<= 0.0000` |

Known limitations:

- `llm` source is currently deterministic and returns no additional structured findings for this seed dataset.
- `syntax` and `spelling` coverage is intentionally minimal and should be expanded in later roadmap items to raise recall.
