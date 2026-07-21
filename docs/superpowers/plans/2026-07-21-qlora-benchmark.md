# Issue #63 implementation plan

1. Add a closed experiment configuration, artifact metadata, report, and
   selection-rule schema with failing fast tests.
2. Add offline preparation and preflight helpers that verify the model revision,
   dataset hashes, MLX chat records, local artifact paths, and no-leakage gate.
3. Run a bounded QLoRA preflight on the 16 GB target and record time, memory,
   swap, and initial learning-curve evidence.
4. Run the fixed full training configuration and hash the local adapter.
5. Evaluate prompt-only, adapted, and prompt-ablation arms on #62 validation;
   then run the single frozen #56 holdout comparison.
6. Apply the predeclared selection rule, record the decision in an ADR, document
   reproduction and limitations, and keep all weights and raw artifacts local.
7. Run Ruff, formatting, mypy, the complete fast suite, and the marked slow
   experiment verification before committing and closing #63.
