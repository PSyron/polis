# Issue #62 implementation plan

1. Define a closed JSONL schema and immutable Python record model.
2. Add failing tests for counts, balance, messages, ChatML, provenance,
   positive/no-change behavior, negative coverage, duplicates, split leakage,
   and corpus-v3 isolation.
3. Implement strict loading, deterministic statistics, and review-manifest
   validation without adding a production dependency.
4. Implement a deterministic generator backed by explicitly reviewed Polish
   transformations and split-disjoint lexicons/templates.
5. Generate 1,200 train and 240 validation records plus a deterministic
   manifest and document licensing and limitations.
6. Run the complete fast suite, Ruff formatting/linting, mypy, and regeneration
   reproducibility checks before committing and closing #62.
