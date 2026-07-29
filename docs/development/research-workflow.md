# Research workflow

Polis keeps one repository with two intentional pytest paths:

- Product-only fast path:
  `uv run --locked --extra dev pytest -m "not research and not slow and not model"`
- Research path:
  `uv run --locked --extra dev pytest -m research`
- Explicit slow/model path:
  `uv run --locked --extra dev pytest -m "slow or model"`

Research results do not qualify a production model automatically. Qualification
still depends on the accepted gates, owner-reviewed evidence, and the separate
release decision for runtime behavior.

Do not rerun or tune against a consumed one-shot holdout. Once a holdout has
been reserved and scored, follow-up work must use new approved data or a new
maintainer-approved evaluation design instead of reusing the spent holdout.

Keep provenance and evidence in their repository homes:

- corpora and approved fixtures under `tests/fixtures/evaluation/`,
  `tests/fixtures/e2e/`, and `data/finetuning/`;
- research reports and frozen benchmark inputs beside their runners under
  `experiments/**/report.json`, `experiments/**/config.json`, and related
  experiment directories;
- optional local LanguageTool evidence under
  `experiments/languagetool_stdio_session/` and `third_party/languagetool-pl/`.

Research code may consume public result models from `src/polis`, but runtime
analysis code must not import research runners, benchmark assemblers, or
holdout-control helpers from `experiments/`.
