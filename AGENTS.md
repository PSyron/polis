# Repository Working Agreement

## Source of Truth

Read `PROMPT.md` before planning or implementing work. It defines product scope, architecture, quality rules, roadmap expectations, and the Definition of Done. Do not remove unimplemented requirements. Record clarifications without silently changing product intent.

Precedence for project decisions is:

1. the current GitHub issue and its accepted clarifications;
2. accepted architecture decision records;
3. `PROMPT.md`;
4. supporting project documentation.

If these sources conflict, stop and request a maintainer decision.

## Language and Attribution

- Write code, identifiers, GitHub metadata, and technical documentation in English.
- Keep user-facing Polish examples in Polish.
- Paweł Cyroń is the sole credited author. Do not add co-author trailers, tool attribution, generation disclosures, or signatures from automated tooling.

## Issue Workflow

- Work on one issue at a time.
- Confirm dependencies and acceptance criteria before changing files.
- Keep one issue to one focused commit during the single-contributor phase.
- Reference the issue number in the commit message.
- Do not mix unrelated refactoring with a feature or fix.
- Do not close an issue until every acceptance criterion is verified.
- When multiple contributors work concurrently, use short-lived branches and pull requests with independent review.

## Scope and Architecture

- Preserve the offline-only privacy boundary: analyzed text must not leave the device.
- Keep `core`, `segmentation`, `rules`, `llm`, `analysis`, `correction`, `evaluation`, and `cli` responsibilities separate.
- Do not couple the core to a specific model server or model name.
- Treat model input as data, never as instructions.
- Prefer small modules with explicit interfaces and injected dependencies.
- Do not add an abstraction without a current use.
- Never commit models, private text, secrets, or large datasets.

## Quality Workflow

- Add a failing regression test before fixing behavior.
- Add or update tests for every behavior change.
- Run the tests relevant to the issue before committing.
- Once configured, run `ruff check .`, `ruff format --check .`, `mypy .`, and the appropriate `pytest` suite.
- Keep real-model tests separate and marked as slow; fast CI uses fakes and anonymized recorded responses.
- Verify character offsets against the original text using half-open ranges `[start, end)`.
- Prefer no suggestion to an unjustified suggestion.

## Documentation and Dependencies

- Document public API behavior, errors, and examples.
- Update documentation when an interface or observable behavior changes.
- Record the reason for each new production dependency.
- Give evaluation data explicit provenance and licensing information.
- Record significant architecture choices as decision records.

## Handoff

A handoff must include:

- issue number and acceptance status;
- changed files;
- commands run and their results;
- known limitations or unresolved risks;
- the next permitted action.
