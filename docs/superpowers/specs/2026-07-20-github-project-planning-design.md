# GitHub Project Planning Design

**Date:** 2026-07-20
**Status:** Approved
**Repository:** `PSyron/polis`

## Goal

Configure the repository for disciplined, issue-driven development and create a dependency-aware backlog derived from `PROMPT.md`. This planning change does not implement the Polis analyzer.

## Decisions

- GitHub metadata, technical documentation, issue bodies, and `AGENTS.md` use English.
- `PROMPT.md` remains in Polish and is the product source of truth.
- The backlog uses the balanced split: 32 independently verifiable issues across milestones M0-M4.
- Every implementation issue has exactly one milestone, one `type:*` label, one `area:*` label, and one `priority:*` label.
- Blocking relationships are written explicitly in issue bodies and mirrored in `docs/project/ROADMAP.md`.
- Existing default GitHub labels remain available. `bug`, `documentation`, and `enhancement` are renamed to the corresponding `type:*` labels because no existing issue references them.
- No target model, backend, NLP dependency, Python version range, or quality threshold is assumed before its decision or measurement issue is complete.

## Repository Files

- `.gitignore`: excludes Python caches, environments, build output, editor files, macOS metadata, local models, generated benchmark output, and non-versioned corpora.
- `AGENTS.md`: defines source-of-truth precedence, issue workflow, scope discipline, testing, privacy constraints, and handoff format.
- `.github/ISSUE_TEMPLATE/task.yml`: structured template for technical implementation work.
- `.github/ISSUE_TEMPLATE/bug.yml`: structured template for defects and regressions.
- `.github/ISSUE_TEMPLATE/decision.yml`: structured template for ADRs, research, and blocking experiments.
- `.github/ISSUE_TEMPLATE/config.yml`: disables unstructured issues and links to project guidance.
- `.github/PULL_REQUEST_TEMPLATE.md`: acceptance, testing, privacy, and scope checklist for future branch-based collaboration.
- `docs/project/ROADMAP.md`: milestones, issue ordering, dependency map, and completion rules.
- `docs/project/RISKS.md`: open decisions, risks, impact, mitigation, and owning issue.
- `PROMPT.md`: tracked without changing its product requirements.

## Label Taxonomy

### Type

`type:decision`, `type:feature`, `type:bug`, `type:docs`, `type:test`, `type:research`, `type:chore`

### Area

`area:core`, `area:segmentation`, `area:rules`, `area:llm`, `area:analysis`, `area:correction`, `area:evaluation`, `area:cli`, `area:packaging`

### Priority and State

`priority:P0`, `priority:P1`, `priority:P2`, and optional `status:blocked`

Administrative labels such as `duplicate`, `good first issue`, `help wanted`, `invalid`, `question`, and `wontfix` remain available but are not required on every issue.

## Issue Contract

Every planned issue contains:

1. a single outcome-oriented goal;
2. rationale tied to `PROMPT.md`;
3. explicit in-scope work;
4. explicit non-goals;
5. objectively verifiable acceptance criteria;
6. required unit, integration, quality, or documentation checks;
7. dependencies identified by planning key and, after creation, GitHub issue link;
8. exactly one milestone and the required type, area, and priority labels.

An issue is not complete until its acceptance criteria, tests, linting, formatting, type checking, and relevant documentation checks pass. Behavioral regressions require a failing test before the fix. Model-dependent checks are marked slow and do not run in the fast CI suite.

## Roadmap

### M0 - Foundation and Decisions

1. `M0-01 Define supported Python versions, platforms, and licensing policy`
2. `M0-02 Evaluate Polish NLP dependencies and record the architecture decision`
3. `M0-03 Scaffold the Python package and quality tooling`
4. `M0-04 Configure fast CI quality checks`
5. `M0-05 Define public data models and versioned JSON serialization`
6. `M0-06 Approve the public API and exception contract`
7. `M0-07 Define analyzer, rule, and LLM backend protocols`
8. `M0-08 Create the initial licensed evaluation dataset`

### M1 - Deterministic Core

9. `M1-01 Segment paragraphs and sentences with stable character offsets`
10. `M1-02 Implement the deterministic rule registry`
11. `M1-03 Add high-precision spelling rules`
12. `M1-04 Add high-precision agreement rules`
13. `M1-05 Add selected syntax and punctuation rules`
14. `M1-06 Normalize, deduplicate, prioritize, and filter findings`
15. `M1-07 Detect conflicting corrections`
16. `M1-08 Apply selected non-conflicting corrections deterministically`

### M2 - Local LLM

17. `M2-01 Benchmark candidate runtimes and models; select the first backend`
18. `M2-02 Define versioned prompts and the LLM response schema`
19. `M2-03 Implement the selected local backend adapter`
20. `M2-04 Add response validation, timeouts, controlled retries, and safe failures`
21. `M2-05 Integrate LLM findings with the analysis pipeline`
22. `M2-06 Verify and document fully offline operation`

### M3 - MVP Quality

23. `M3-01 Expand the evaluation dataset with positive and hard-negative cases`
24. `M3-02 Establish the quality baseline and measurable release gates`
25. `M3-03 Measure latency, throughput, and memory usage`
26. `M3-04 Document the public API, privacy guarantees, and extension guides`
27. `M3-05 Add a thin CLI and executable examples`
28. `M3-06 Build and verify the first prerelease candidate`

### M4 - Release Stabilization

29. `M4-01 Audit compatibility and define semantic-versioning guarantees`
30. `M4-02 Audit privacy, dependencies, and packaged artifacts`
31. `M4-03 Produce and validate the PyPI distribution`
32. `M4-04 Publish version 0.1.0 with release notes and documented limitations`

## Dependency Strategy

M0 decisions and contracts precede implementation. M1 rules can proceed independently only after segmentation, data models, the dependency decision, and the rule registry are ready. M2 begins with an evidence-producing benchmark and backend decision; schema and resilience work precede pipeline integration. M3 release gates are derived from measured baselines. M4 packaging and release work depends on the verified prerelease.

Dependencies are acyclic. If a GitHub issue cannot start, it receives `status:blocked` and a comment naming the unresolved dependency. A failed metadata operation stops bootstrap execution; rerunning the bootstrap must discover existing labels, milestones, and issues by exact name and avoid duplicates.

## Risks and Resolutions

- Python and platform support are undecided: M0-01 records an explicit compatibility policy.
- Polish NLP dependencies may constrain licensing, package size, or offline behavior: M0-02 compares candidates before adoption.
- The proposed API and confidence semantics are not final: M0-05 and M0-06 freeze the first versioned contracts.
- Dataset licensing and representativeness may block meaningful evaluation: M0-08 records provenance and establishes a small initial corpus.
- Backend and model availability are unstable: M2-01 benchmarks candidates and records an adapter-level decision without coupling the core to a vendor.
- Quality thresholds are unknown: M3-02 derives gates from the measured baseline rather than inventing targets.
- The CLI is optional in the architecture but included in the MVP roadmap: M3-05 remains a thin manual-testing and demonstration layer with no business logic.
- Repository metadata may be partially created if GitHub rejects a request: bootstrap operations are idempotent and verification compares exact expected counts and names.

## Verification

Local verification checks Markdown structure, YAML syntax, required issue-form fields, ignored artifacts, and a clean diff limited to planning assets. Remote verification confirms five milestones, the complete label taxonomy, exactly 32 uniquely titled planned issues, one milestone per issue, required labels, and dependency references. No issue is automatically closed and no implementation is started by this bootstrap.
