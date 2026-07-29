# Runtime-First Product Boundary and Artifact Policy

**Status:** Proposed for implementation after maintainer review
**Issue:** #120
**Date:** 2026-07-29

## Decision summary

Polis remains one repository. The repository will contain both the supported
offline library and the research/evaluation material needed to develop and
audit it, but those two concerns will have different interfaces, release
artifacts, and CI paths.

The supported product is the runtime exposed through src/polis: typed public
models, segmentation, deterministic rules, analysis orchestration, conservative
correction, optional local protocol adapters, and the thin CLI. Experiments,
training data, qualification corpora, benchmark reports, vendored build trees,
and historical planning documents remain repository material. They are not part
of the supported library interface and must not enter wheel or source
distribution artifacts unless a separate release decision explicitly permits
them.

This is a repository and packaging boundary, not a change to the linguistic
claims. Polis continues to be offline-only, fail-closed, offset-preserving, and
conservative. No local model is treated as production-qualified without passing
the existing evidence gates.

## Context

The repository currently has a narrow installed runtime but a broad source
checkout. The wheel target already selects src/polis, while the source tree
also contains experiments, fine-tuning data, evaluation fixtures, a vendored
LanguageTool build, and Superpowers planning records. This makes the repository
look like a research laboratory even though the intended user-facing object is
a small offline Python library.

The open issue set reflects the same mixture. M5 contains corpus construction,
model qualification, release gates, and publication tracking. M6 contains
future internal architecture work. These are valuable engineering records,
but they must not silently define the supported runtime or block a small
deterministic library release.

The project requirements in PROMPT.md remain in force. This specification does
not delete unimplemented requirements. It gives them an explicit home:
runtime requirements belong to the product path; model qualification,
benchmark expansion, and future document adapters remain repository research or
future-product work until separately accepted.

## Goals

- Keep one repository and use short-lived branches for changes.
- Give the runtime a small, deep interface with stable public contracts.
- Make the product/research distinction visible in packaging, CI, tests, and
  documentation.
- Keep research and evaluation evidence reproducible and reviewable without
  shipping it as library content.
- Keep LanguageTool optional and local, with no Java or model startup in the
  default runtime.
- Preserve public finding identity, JSON schema, half-open Unicode offsets,
  correction conflict behavior, privacy guarantees, and failure semantics.
- Make it possible to improve research tooling without expanding the public
  runtime interface.

## Non-goals

- Creating a second repository such as polis-research.
- Removing research evidence merely because it is not shipped.
- Qualifying or integrating a local production model as part of this boundary
  change.
- Adding a general grammar DSL, document adapters, GUI, or stylistic rewrite.
- Rewriting the public API or changing analysis behavior as a side effect of
  packaging cleanup.

## Product interface

The product interface is the smallest surface needed by a caller who wants to
analyze Polish text offline and optionally apply explicit safe corrections:

- Analyzer and its synchronous/asynchronous analysis and correction methods;
- AnalysisOptions, AnalysisResult, Finding, CorrectionResult, and the related
  typed configuration and exception contracts;
- deterministic segmentation and original-text offset invariants;
- built-in deterministic rules and their documented source behavior;
- optional local adapters that satisfy injected protocols;
- strict versioned JSON serialization;
- the thin polis CLI and TOML configuration.

The product interface does not include:

- experiment runners and benchmark-specific orchestration;
- training-data generation or fine-tuning assets;
- corpus-authoring and holdout-control internals;
- historical model prompts, raw qualification reports, or model artifacts;
- vendored Java source trees;
- Superpowers implementation plans as public technical API documentation.

### Evaluation namespace policy

The current polis.evaluation package contains useful validators and metrics,
but its role is primarily repository evaluation rather than text-analysis
runtime. It will not be expanded as part of the product boundary. Before any
removal, the implementation plan must choose one of these compatible paths:

1. move evaluation code to a repository tool namespace and remove it from the
   distributed package in the next development release; or
2. retain a deliberately documented compatibility namespace while moving the
   large corpora and research-only code out of the shipped artifact.

The choice must be made with an import-compatibility check. No evaluator code
will be deleted before all repository references and public documentation are
updated.

## Repository organization

The first implementation phase will avoid a broad directory move. Existing
paths remain stable while their roles become explicit:

| Repository material | Role | Shipped by default |
| --- | --- | --- |
| src/polis runtime modules | Supported library implementation | Yes |
| runtime tests and type examples | Product regression contract | No, unless sdist policy explicitly includes them |
| examples and selected public docs | User-facing usage | Documentation only |
| experiments | Research and benchmark implementations | No |
| data/finetuning | Training/evaluation input material | No |
| tests/fixtures/evaluation | Release and research fixtures | No |
| third_party/languagetool-pl | Optional local build source | No |
| docs/superpowers | Historical planning records | No |
| docs/architecture/decisions | Accepted architectural record | Selected documentation only |

If a later move into a lab directory materially improves navigation, it will
be a separate mechanical issue. The product boundary does not depend on
renaming paths.

## Module and seam design

Analyzer remains the deep external module. Callers provide text and typed
options; the implementation owns segmentation, rule selection, local adapter
coordination, normalization, correction policy, and controlled failures.

Internal seams remain narrow and dependency-injected:

- deterministic rule seam: one rule receives the request-scoped input and
  returns validated findings;
- local-generation seam: an optional backend accepts a validated request and
  returns a validated, bounded response;
- LanguageTool seam: an optional local adapter owns process/HTTP mechanics and
  never becomes a core dependency;
- evaluation seam: repository tools consume public results and corpora but are
  not imported by runtime analysis.

The seam rule is evidence-driven. A new adapter or internal interface requires
at least two real implementations or a concrete test/replacement need. No
general plugin registry, grammar DSL, or research abstraction is introduced by
the packaging cleanup.

## Artifact policy

The release artifacts must be inspectable and minimal:

- the wheel contains the supported runtime package and required metadata only;
- the sdist contains the files needed to inspect, build, and use the supported
  project, but excludes experiments, fine-tuning data, research holdouts,
  reports, and vendored build trees by default;
- no model weights, private text, Java artifacts, or generated holdout results
  are included in a release artifact;
- optional LanguageTool support requires an explicitly supplied local executable
  or an explicitly built local artifact and remains disabled by default;
- package inspection tests assert the absence of excluded paths rather than
  relying only on a manually reviewed configuration file.

The exact Hatch include/exclude configuration belongs to the implementation
plan. It must be verified by building both wheel and sdist and listing their
contents.

## CI and test policy

CI will expose two intentional paths:

1. **Fast product path:** runtime tests, public contract tests, architecture
   policy, Ruff, formatting, mypy, build, package-content checks, and offline
   verification. It uses fakes and synthetic fixtures.
2. **Research/evaluation path:** slow benchmarks, corpus validators, recorded
   qualification replay, optional LanguageTool build/runtime checks, and real
   local-model experiments. It is explicit and never required to pretend that
   an unqualified model is production behavior.

The boundary change must not weaken the existing fast matrix. Tests that move
out of the installed package must retain a repository execution path and clear
provenance.

## Issue disposition

The following disposition is architectural guidance, not automatic closure:

- Keep product-facing: #84 (version-bound automatic privileges) and #95
  (generative Unicode, offset, and correction invariants).
- Keep as future internal product work, but remove from the immediate release
  critical path: #96 (shared analyzed-document substrate), #97 (rule catalog),
  #98 (minimal token-pattern primitives), and #99 (adapter-owned fingerprints).
- Reclassify as research/release-evidence work: #76, #85, #86, #87, #88, #89,
  #90, #92, #93, and #119. Their evidence remains valuable, but a failed or
  unqualified research gate must not be represented as a missing runtime
  feature.

Before changing labels, milestones, or state, each issue will receive an
explicit disposition and dependency note. No holdout will be rerun or tuned
against.

## Migration phases

### Phase 1: Boundary and packaging evidence

- add the product/repository artifact policy;
- classify runtime versus research tests;
- tighten wheel/sdist include and exclude rules;
- add package-content inspection;
- update README and release documentation to state the supported boundary;
- verify no runtime behavior changes.

### Phase 2: Evaluation isolation

- decide the polis.evaluation compatibility path;
- move or isolate evaluator-only code and assets without losing provenance;
- keep repository validators runnable through an explicit research command;
- update imports, tests, and documentation in focused commits.

### Phase 3: Optional adapter hygiene

- keep LanguageTool behind its existing injected seam;
- verify that the default install has no Java/model/network requirement;
- document the optional build artifact and its license/provenance separately;
- avoid increasing the supported rule set without fresh evidence.

### Phase 4: Issue and roadmap reconciliation

- update M5/M6 descriptions and labels to match the product/research split;
- introduce no hidden dependency from M6 architecture work to the product
  release;
- revise the roadmap only after the artifact and compatibility checks pass.

## Acceptance criteria

- [ ] This specification is committed on a branch from current main.
- [ ] The supported runtime surface and repository-only material are documented.
- [ ] Wheel and sdist inspection prove that excluded research material is not
      shipped.
- [ ] Default installation and Analyzer operation require no Java, model,
      network, or cloud service.
- [ ] Public result, finding, correction, serialization, privacy, and Unicode
      offset tests remain green.
- [ ] Runtime and research/evaluation commands are separately documented.
- [ ] The polis.evaluation compatibility decision is recorded before any
      namespace removal.
- [ ] Affected GitHub issues have an explicit disposition before implementation
      of behavior or packaging changes.

## Alternatives considered

### Separate research repository

Rejected for this decision. It would produce a clean product repository but
split provenance, issue context, and development flow. The maintainer explicitly
selected one repository.

### Packaging-only cleanup

Rejected as the final architecture. It would make artifacts smaller while
leaving the source tree and public namespace conceptually mixed. It remains a
useful first phase and a low-risk migration step.

### Full workspace reorganization

Deferred. Moving all paths to packages/polis and lab/ could improve visual
separation, but it introduces broad mechanical churn without improving the
runtime interface. It may be revisited after Phase 1 evidence.

## Risks and mitigations

- **Import breakage from evaluation extraction:** inventory imports first; keep
  a compatibility namespace or defer removal until the next development
  release.
- **Accidentally weakening evidence:** retain corpora and reports in Git,
  preserve provenance, and separate artifact exclusion from deletion.
- **Runtime behavior drift during refactoring:** require regression-first tests,
  exact finding/offset comparison, and focused commits.
- **LanguageTool becoming an implicit dependency:** test a clean install with
  no Java and keep its configuration opt-in.
- **Research work silently blocking product work:** encode issue dispositions
  and CI paths explicitly instead of relying on milestone names.
