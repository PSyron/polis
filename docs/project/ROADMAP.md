# Polis Roadmap

`PROMPT.md` is the product source of truth. This roadmap defines delivery order; GitHub issues hold executable acceptance criteria. A milestone is complete only when all its issues are closed, integration checks pass, and known limitations are documented.

## Delivery Rules

- Start an issue only after all listed dependencies are closed.
- Each issue produces one independently verifiable outcome and one focused commit during the single-contributor phase.
- Every issue requires one milestone plus one `type:*`, one `area:*`, and one `priority:*` label.
- A blocked issue receives `status:blocked` and a comment naming the unresolved dependency.
- Quality thresholds are derived from the measured baseline, not selected in advance.

## M0 - Foundation and Decisions

| Key | Outcome | Labels | Depends on |
| --- | --- | --- | --- |
| M0-01 | Define supported Python versions, platforms, and licensing policy | `type:decision`, `area:packaging`, `priority:P0` | - |
| M0-02 | Evaluate Polish NLP dependencies and record the architecture decision | `type:research`, `area:rules`, `priority:P0` | M0-01 |
| M0-03 | Scaffold the Python package and quality tooling | `type:chore`, `area:packaging`, `priority:P0` | M0-01 |
| M0-04 | Configure fast CI quality checks | `type:chore`, `area:packaging`, `priority:P0` | M0-03 |
| M0-05 | Define public data models and versioned JSON serialization | `type:feature`, `area:core`, `priority:P0` | M0-03 |
| M0-06 | Approve the public API and exception contract | `type:decision`, `area:core`, `priority:P0` | M0-05 |
| M0-07 | Define analyzer, rule, and LLM backend protocols | `type:feature`, `area:core`, `priority:P0` | M0-05, M0-06 |
| M0-08 | Create the initial licensed evaluation dataset | `type:test`, `area:evaluation`, `priority:P0` | M0-03, M0-05 |

## M1 - Deterministic Core

| Key | Outcome | Labels | Depends on |
| --- | --- | --- | --- |
| M1-01 | Segment paragraphs and sentences with stable character offsets | `type:feature`, `area:segmentation`, `priority:P0` | M0-02, M0-03, M0-05 |
| M1-02 | Implement the deterministic rule registry | `type:feature`, `area:rules`, `priority:P0` | M0-07 |
| M1-03 | Add high-precision spelling rules | `type:feature`, `area:rules`, `priority:P0` | M1-01, M1-02 |
| M1-04 | Add high-precision agreement rules | `type:feature`, `area:rules`, `priority:P0` | M1-01, M1-02 |
| M1-05 | Add selected syntax and punctuation rules | `type:feature`, `area:rules`, `priority:P1` | M1-01, M1-02 |
| M1-06 | Normalize, deduplicate, prioritize, and filter findings | `type:feature`, `area:analysis`, `priority:P0` | M0-05, M1-02 |
| M1-07 | Detect conflicting corrections | `type:feature`, `area:correction`, `priority:P0` | M0-05 |
| M1-08 | Apply selected non-conflicting corrections deterministically | `type:feature`, `area:correction`, `priority:P0` | M1-07 |

## M2 - Local LLM

| Key | Outcome | Labels | Depends on |
| --- | --- | --- | --- |
| M2-01 | Benchmark candidate runtimes and models; select the first backend | `type:research`, `area:llm`, `priority:P0` | M0-07, M0-08 |
| M2-02 | Define versioned prompts and the LLM response schema | `type:feature`, `area:llm`, `priority:P0` | M0-05, M0-07 |
| M2-03 | Implement the selected local backend adapter | `type:feature`, `area:llm`, `priority:P0` | M2-01, M2-02 |
| M2-04 | Add response validation, timeouts, controlled retries, and safe failures | `type:feature`, `area:llm`, `priority:P0` | M2-03 |
| M2-05 | Integrate LLM findings with the analysis pipeline | `type:feature`, `area:analysis`, `priority:P0` | M1-06, M2-04 |
| M2-06 | Verify and document fully offline operation | `type:docs`, `area:llm`, `priority:P1` | M2-03, M2-05 |

## M3 - MVP Quality

| Key | Outcome | Labels | Depends on |
| --- | --- | --- | --- |
| M3-01 | Expand the evaluation dataset with positive and hard-negative cases | `type:test`, `area:evaluation`, `priority:P0` | M1-03, M1-04, M1-05, M2-05 |
| M3-02 | Establish the quality baseline and measurable release gates | `type:test`, `area:evaluation`, `priority:P0` | M3-01 |
| M3-03 | Measure latency, throughput, and memory usage | `type:test`, `area:evaluation`, `priority:P1` | M2-05 |
| M3-04 | Document the public API, privacy guarantees, and extension guides | `type:docs`, `area:core`, `priority:P1` | M1-08, M2-06 |
| M3-05 | Add a thin CLI and executable examples | `type:feature`, `area:cli`, `priority:P1` | M0-06, M2-05 |
| M3-06 | Build and verify the first prerelease candidate | `type:chore`, `area:packaging`, `priority:P0` | M3-02, M3-03, M3-04, M3-05 |

## M4 - Release Stabilization

| Key | Outcome | Labels | Depends on |
| --- | --- | --- | --- |
| M4-01 | Audit compatibility and define semantic-versioning guarantees | `type:decision`, `area:packaging`, `priority:P1` | M3-06 |
| M4-02 | Audit privacy, dependencies, and packaged artifacts | `type:chore`, `area:packaging`, `priority:P0` | M3-06 |
| M4-03 | Produce and validate the PyPI distribution | `type:chore`, `area:packaging`, `priority:P0` | M4-01, M4-02 |
| M4-04 | Publish version 0.1.0 with release notes and documented limitations | `type:chore`, `area:packaging`, `priority:P0` | M4-03 |

## Critical Path

M0-01 -> M0-03 -> M0-05 -> M0-06 -> M0-07 -> M1-02 -> M1-06 -> M2-05 -> M3-01 -> M3-02 -> M3-06 -> M4-03 -> M4-04

Rule implementations M1-03 through M1-05 can proceed independently after segmentation and the rule registry. Documentation and performance work in M3 can proceed in parallel after their listed dependencies close.
