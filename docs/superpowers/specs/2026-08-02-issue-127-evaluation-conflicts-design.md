# Issue #127 Evaluation Conflict Contract Design

## Decision and scope

Issue #127 reconciles the evaluation-dataset validator with the accepted
correction-selection contract in ADR-0003. The ADR is authoritative: an
insertion conflicts with a non-empty replacement at either endpoint and at
every offset between them. This is already the production behavior of
`polis.correction.findings_conflict`.

The change is limited to evaluation fixture validation, its authored tests, and
the evaluation-dataset documentation. It does not alter correction production
code, corpus or holdout contents, quality thresholds, model qualification, or
the generated-property work owned by #95.

## Considered approaches

1. Change production correction behavior to allow the replacement end. This
   would contradict ADR-0003 and change the public correction contract.
2. Keep the evaluator's half-open predicate and describe it as evaluator-only.
   This would leave evaluator fixtures able to define an oracle the runtime
   rejects.
3. Replace the evaluator predicate with the ADR's closed-boundary predicate.
   This preserves the public contract and makes invalid fixture edits fail
   before later generated properties consume them.

Approach 3 is selected.

## Design

`_validate_non_overlapping` continues to reject overlapping non-empty
replacement ranges and duplicate insertion offsets. Its insertion-versus-
replacement test changes from the half-open condition
`replacement_start <= insertion < replacement_end` to the closed-boundary
condition `replacement_start <= insertion <= replacement_end`.

The authored validator regression uses the existing first fixture case, whose
replacement occupies offsets `[0, 2)`. It appends a punctuation insertion at
offset `2` and asserts `ValueError("colliding expected findings")`. That
expectation is hand-derived from ADR-0003 rather than from evaluator helper
logic. The existing permissive boundary test is split into a replacement-end
rejection and a strictly outside insertion acceptance at offset `3`.

The evaluation documentation will say that insertion offsets at the start,
inside, or end of a non-empty replacement are rejected. It will state that an
insertion is permitted only strictly outside that replacement range.

## Compatibility and verification

The production implementation and its public correction-selection behavior are
not modified. Tests retain the existing coverage for duplicate insertions and
overlapping replacements. The required red/green regression and focused
validator, conflict-detection, and analysis-apply tests demonstrate contract
alignment; the fast suite, Ruff, mypy, and whitespace check provide the final
repository checks. No evaluation, holdout, corpus-scoring, or model command is
permitted.

## Protected corpus and holdout inventory

The following tracked data-bearing assets were recorded before edits with Git
blob hashes and must have identical hashes after the change:

| Path | Git blob hash |
| --- | --- |
| `experiments/contextual_inflection_routing/holdout.started` | `3c897232a8d7518bc072097700b2a909d170c1af` |
| `experiments/languagetool_rule_inventory/holdout.started` | `6d6f429b5a7fecdb2aae87a4c4d1ac6d15c95a19` |
| `experiments/residual_syntax_rules/holdout.started` | `5d5e34a978f8810801c97b47923d0c1f0aae6917` |
| `experiments/sentence_safety_gate/holdout.started` | `8962a085198bc8b8a4aa5964d9e5db21c5bda6c8` |
| `src/polis/evaluation/datasets/v1/cases.json` | `04945d9a5887b737efed1ecd28c988753e53b92b` |
| `tests/fixtures/e2e/polish_correction_corpus.json` | `c27968d7ec7d3b7c100e0e938bc8b370e90602ac` |
| `tests/fixtures/e2e/polish_correction_corpus.xml` | `5cd2dcb5d8ee34694548a8273cbb5af86009c820` |
| `tests/fixtures/evaluation/polish_correction_corpus_v3.json` | `56dafebd22380bc18a033c85dd222c2780169c7f` |
| `tests/fixtures/evaluation/polish_correction_corpus_v3.xml` | `062f59e6b83a08d5803b2ba76eadb68832a386d3` |
| `tests/fixtures/evaluation/polish_correction_safety_corpus_v1.approval.json` | `e2a272ff92f07daec73b1156f9f9908e723f1d0a` |
| `tests/fixtures/evaluation/polish_correction_safety_corpus_v1.json` | `9ef540ef007c1ceabac37e158ce731a57fd66948` |
| `tests/fixtures/evaluation/polish_correction_safety_corpus_v1.xml` | `6b7ff529315e24078968693181ebdfe568eb58e7` |

## Design self-review

The design has no unresolved choices: the issue and ADR choose the closed
boundary. It changes one evaluator predicate, replaces the now-invalid
permissive test expectation, and updates the one conflicting documentation
paragraph. It explicitly preserves the production contract and protects every
tracked corpus or holdout asset in scope.
