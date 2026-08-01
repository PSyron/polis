# Runtime-First Product Charter and Portfolio Reset

**Status:** Accepted for planning by the maintainer
**Issue:** #120
**Date:** 2026-08-01

## Decision summary

Polis is a complete offline product without a local language model. Its supported
product is the small runtime under `src/polis`: stable typed contracts,
segmentation, deterministic rules, analysis orchestration, conservative
correction, optional local adapters, strict serialization, and the CLI.

A local model is an optional research and extension path. Model-backed output is
always review-only, may enter the supported product only after independent
qualification, and never blocks a runtime release. LanguageTool remains an
optional local adapter and is not a default runtime dependency.

This decision supersedes the earlier requirement that a qualified local model
must be part of the product's critical path. It does not delete model research or
its evidence. It changes the authority and sequencing of that work.

Issue #120 is a finite migration epic. It closes after the product charter,
roadmap, risks, milestones, and affected issue graph agree with this decision.

## Why this decision is needed

The runtime boundary merged through PR #121 made release artifacts and product
CI independent from the research workspace. The remaining project governance
still describes the model-qualification M5 graph as authoritative for the next
release. That leaves two incompatible definitions of completion:

- the runtime can be built, installed, verified, and used offline without a
  model, Java process, network, or research corpus;
- the old release graph requires successful model and majority-coverage research
  before publication and final owner verification.

The repository must have one answer. Runtime safety and product correctness are
release requirements. Optional model quality is research evidence until a
separate accepted decision promotes an exact qualified configuration.

## Product charter

### Supported product

The supported Polis product provides:

- `Analyzer` and its synchronous and asynchronous analysis and correction APIs;
- stable typed public models and strict versioned JSON serialization;
- deterministic segmentation with half-open Unicode offsets against the
  original text;
- deterministic spelling, agreement, punctuation, and syntax rules whose
  behavior is documented and regression-tested;
- deterministic normalization, conflict detection, and correction application;
- conservative automatic correction controlled by an explicit versioned source
  policy;
- optional injected local adapters that fail closed and do not become default
  dependencies;
- an offline CLI and TOML configuration;
- reproducible wheel and source-distribution verification.

The product is releasable when these contracts and gates pass. It does not wait
for model qualification, corpus expansion, majority-coverage experiments, or a
paragraph-level integration gate.

### Optional model extension

The repository may continue to investigate local language models under these
rules:

- model support is disabled by default and does not change the default install;
- every model-derived or model-selected edit remains review-only regardless of
  confidence;
- analyzed text never leaves the device;
- an exact backend, model artifact, prompt/protocol version, and operation must
  pass fresh independent evidence before documentation may call it qualified;
- a failed or incomplete qualification is a valid research outcome and cannot
  block a runtime release;
- consumed holdouts are never rerun or used for tuning;
- research code, corpora, reports, and model artifacts remain outside release
  artifacts.

Promotion of a model configuration into supported optional product behavior
requires a separate issue and accepted ADR. This charter grants no model
automatic-correction privileges.

### Optional LanguageTool adapter

LanguageTool remains different from the model-research path because Polis has a
bounded, deterministic, locally verified adapter for a narrow rule subset. It
remains optional, disabled by default, local-only, version-pinned, and subject to
the same source-behavior policy as built-in deterministic rules. Broader
LanguageTool coverage requires fresh evidence and does not follow from this
charter.

## Release authority

The product release path is authoritative for releases of the Polis runtime. It
contains only gates that can run from a clean checkout or installed artifact
without a model, model server, Java process, network, consumed holdout, or
research corpus:

1. supported-platform Fast CI;
2. Ruff, formatting, and strict mypy;
3. public API, serialization, privacy, Unicode offset, conflict, and correction
   invariants;
4. deterministic rule regressions and conservative source-policy tests;
5. wheel and sdist content verification;
6. clean-install, offline API, and CLI smoke tests;
7. version uniqueness, license, provenance, and release identity checks.

Research gates may support a later promotion decision but are not product
release dependencies. Reports must identify themselves as research evidence and
must not use product-release language for an unqualified model.

## Source-of-truth changes

`PROMPT.md` remains the product source of truth and must be revised in place. Its
offline, privacy, modularity, API, quality, and testing requirements remain.
Statements that make a local model or selected model backend mandatory are
replaced with the optional-extension policy above.

The accepted architecture decision record will state explicitly that it
supersedes only the mandatory-model critical path. Historical ADRs and reports
remain valid evidence for the exact experiments they record; they do not retain
authority over current release sequencing.

`docs/project/ROADMAP.md` will present separate product and research lanes. It
will no longer call the M5 majority-error graph authoritative for product
delivery. Historical completed M5 work remains documented.

## Portfolio disposition

### Product work

- **#84 — version-bound automatic privileges:** remains product-facing P0. The
  enforcement mechanism no longer depends on #76. Unknown or changed source,
  category, operation, behavior, or policy versions fail closed. New automatic
  privileges still require separate qualification evidence.
- **#95 — generative invariant hardening:** remains product-facing P1 and
  follows #84. It must be decomposed into atomic child issues before
  implementation.

These issues move to a new `Runtime 0.x Hardening` milestone. Product releases
may distinguish P0 blockers from P1 hardening through explicit issue priority;
mere milestone membership does not silently create a release blocker.

### Future product architecture

Issues #96 through #100 remain open under M6. They are future product
engineering and do not block current runtime releases. Their existing dependency
ordering remains until a focused architecture decision changes it.

### Optional research

Issues #76, #85, #86, #87, #88, #89, #90, and #119 remain open and move to a
new milestone named `Research — Optional Local Model Qualification`, with no due
date. They retain their evidence, provenance, and internal research dependencies
but have no dependency edge into the product release path.

The `status:blocked` label is retained only when an issue is genuinely blocked
by another research dependency. It must not imply that the product is blocked.

### Superseded release train

Issues #43, #64, #66, #92, and #93 are closed as superseded, not completed:

- #43 required a qualified production model provider and bounded ranker;
- #64 made paragraph integration part of the old release gate;
- #66 owned final verification of that old M5 release train;
- #92 published from the old combined product/research artifact graph;
- #93 tracked the old evidence-first release path.

Each closure comment must state that its acceptance criteria were not completed,
link #120 and the accepted charter ADR, and identify any surviving work. No
holdout, report, or result changes during this migration.

After all remaining issues are moved or closed, the M5 milestone is closed as a
historical milestone. Closing the milestone does not claim that every original
M5 objective shipped.

## Issue #120 lifecycle

PR #121 is recorded as Phase 1 of #120: artifact, CI, documentation, and initial
classification boundaries.

The remaining migration is complete when:

1. this charter has an accepted ADR;
2. `PROMPT.md`, roadmap, risks, limitations, and release documentation agree;
3. the product and research milestones exist;
4. every affected open issue has the disposition defined above;
5. obsolete dependency edges and `status:blocked` labels are removed where they
   incorrectly connect research to product work;
6. current GitHub state is verified after mutation;
7. repository policy tests prevent the old mandatory-model release language from
   returning.

Issue #120 then closes as completed. Future charter changes require new decision
issues rather than turning #120 into a permanent meta-tracker.

## Implementation boundaries

This migration changes governance and documentation only. It does not:

- change runtime code or public API behavior;
- qualify, integrate, download, or execute a model;
- rerun a consumed holdout;
- add automatic correction privileges;
- delete corpora, reports, experiments, or historical ADRs;
- implement #84, #95, or M6 architecture work;
- add paragraph adapters, document adapters, GUI, cloud services, or stylistic
  rewriting.

GitHub mutations must be prepared as an exact disposition record before they are
applied. Markdown issue bodies and comments are supplied through body files or
standard input, never fragile inline shell quoting.

## Verification

The migration is verified by:

- policy tests that assert the runtime-first charter and optional-model language
  in `PROMPT.md`, the ADR, roadmap, limitations, and release documentation;
- checks that no product critical-path documentation names research issues as
  release dependencies;
- checks that model output remains review-only and the default dependency set is
  unchanged;
- the complete fast product suite, static checks, artifact verification, and
  offline clean-install smoke tests;
- a post-mutation GitHub inventory confirming issue state, labels, milestones,
  dependency notes, and closure comments;
- `git diff --check` and a final whole-branch review.

Research tests are collected but not executed during this migration. Consumed
holdouts remain untouched.

## Risks and mitigations

- **Silent requirement loss:** preserve historical requirements and explain each
  supersession in the charter ADR and issue closure comments.
- **Research represented as deleted:** keep research issues and evidence open or
  archived with explicit provenance; do not delete artifacts.
- **Model behavior accidentally promoted:** keep model findings review-only in
  policy tests and require a separate promotion ADR.
- **Product and research become coupled again:** add executable documentation
  checks for release dependency language and keep separate milestones.
- **Open issue metadata drifts from the roadmap:** capture the intended mutation
  set before applying it and verify live GitHub state afterward.
- **#84 loses necessary evidence discipline:** separate enforcement from
  qualification; fail closed for every unknown version and require evidence for
  each new automatic privilege.

## Alternatives rejected

### Keep the mandatory model as a future product requirement

Rejected. It would preserve the old contradiction: the supported runtime is
complete and releasable without a model, while product completion remains tied
to an unqualified research outcome.

### Remove all model and evaluation work

Rejected. Research evidence, validators, and optional local-model experiments
remain useful and auditable. They need a separate authority boundary, not
deletion.

### Keep #120 open permanently

Rejected. A permanent umbrella has no verifiable completion condition and makes
future direction changes difficult to audit. #120 is the finite migration from
the old combined release train to the runtime-first charter.
