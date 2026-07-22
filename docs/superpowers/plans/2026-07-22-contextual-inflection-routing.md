# Contextual Polish Inflection Routing Implementation Plan

**Goal:** Qualify or reject a gold-independent deterministic inflection router
for one Polish sentence.

**Architecture:** A source-only detector identifies closed government or
adjacent-name evidence. One warm local LanguageTool process synthesizes finite
forms for detected spans. A conservative ranker selects a unique constrained
candidate or abstains, while a separate corpus wrapper scores exact edits.

## Task 1: Freeze source-only detection and ranking contracts

- [x] Add failing tests for sentence tokenization, adjacent-name evidence,
  government patterns, excluded layouts, and routing-input leakage.
- [x] Add immutable evidence, candidate, proposal, and abstention records.
- [x] Require exact Unicode half-open source spans and closed evidence kinds.

## Task 2: Implement finite-candidate contextual selection

- [x] Add failing tests for candidate provenance, case/number/gender matching,
  adjective-noun agreement, already-correct forms, ambiguity, and unsupported
  morphology.
- [x] Reuse the validated LanguageTool synthesis response contract.
- [x] Select only one distinct finite form and otherwise abstain.

## Task 3: Implement privacy-safe scoring and holdout guards

- [x] Add failing tests for exact edit scoring, class metrics, protected
  negatives, report privacy, frozen hashes, and atomic holdout reservation.
- [x] Run all 69 development sentences with source-only inputs.
- [x] Freeze and run the 142-sentence holdout once only if every development
  gate passes.

## Task 4: Record and verify the decision

- [x] Add an experiment README, identifier-only report, and ADR-0015.
- [x] Update roadmap and limitations with the consequence for #43.
- [x] Run offline integration, Ruff, formatting, mypy, full pytest, and
  distribution checks.
- [x] Commit and push one focused #71 change and close only with complete
  acceptance evidence.
