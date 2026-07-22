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

## M5 - Hybrid Polish Correction

M5 keeps automatic deterministic corrections separate from reviewable model
suggestions. ADR-0008 is the policy gate for every behavior change in this
milestone.

| Key | Issue | Outcome | Depends on |
| --- | ---: | --- | --- |
| M5-00 | #65 | Record the hybrid correction architecture and M5 policy | #54 |
| M5-01 | #55 | Repair real-model benchmark integrity and evidence reporting | #54, #65 |
| M5-02 | #56 | Build an independent Polish correction corpus v3 | #55 |
| M5-03 | #57 | Benchmark role-correct specialist prompts for small Polish models | #55, #56 |
| M5-04 | #58 | Evaluate deterministic inflection candidate generation | #54, #56 |
| M5-05 | #59 | Implement selected specialist prompt contracts | #57 |
| M5-06 | #60 | Implement the hybrid correction and suggestion policy | #58, #59 |
| M5-07 | #61 | Benchmark MLX and GGUF runtimes for the hybrid pipeline | #55, #57, #60 |
| M5-08 | #62 | Prepare a licensed Polish correction fine-tuning dataset | #56; selected data shapes from #57 |
| M5-09 | #63 | Benchmark an MLX QLoRA adapter for Bielik 1.5B | #57, #61, #62 |
| M5-10 | #67 | Specify a two-pass constrained Qwen3.5 correction protocol | #58, #59, #60, #61, #63 |
| M5-11 | #68 | Benchmark the constrained two-pass Qwen3.5 2B protocol | #67 |
| M5-12 | #69 | Benchmark deterministic category routing with a syntax-only compact model | #68 |
| M5-12a | #70 | Inventory and qualify broader deterministic Polish LanguageTool rules | #54, #56, #65, #69 |
| M5-12b | #71 | Build gold-independent contextual inflection routing for Polish sentences | #54, #56, #58, #69 |
| M5-12c | #72 | Enable four qualified Polish LanguageTool sentence rules in source policy | #54, #60, #65, #70 |
| M5-12d | #73 | Integrate qualified contextual inflection suggestions for sentences | #58, #60, #71 |
| M5-12e | #74 | Qualify a Qwen3 1.7B MLX residual syntax route for sentences | #59, #60, #61, #69, #72, #73 |
| M5-12f | #75 | Add high-precision residual syntax rules for sentences | #60, #65, #69, #74 |
| M5-12g | #77 | Integrate one persistent vendored LanguageTool stdio session for sentences | #54, #60, #70, #71, #72, #73 |
| M5-12h | #76 | Add the installed-package sentence correction release gate | #55, #56, #60, #61, #65, #70, #71, #72, #73, #74, #75, #77 |
| M5-13 | #43 | Add a qualified production local model backend | #55, #56, #59, #60, #61, #63; blocked because no model qualified |
| M5-14 | #64 | Add the broader sentence and paragraph correction release gate | #43, #76 and all preceding M5 issues |
| M5-15 | #66 | Perform final owner verification before first publication | #43, #64 and all preceding M5 issues |

The primary dependency flow is:

`#54 -> #65 -> #55 -> #56`.

After #56, prompt work (`#57 -> #59`) and morphology work (`#58`) may proceed
independently. Both join at #60. Runtime evidence then proceeds through #61,
while #62 prepares fine-tuning data from #56 and the selected #57 data shapes.
Issues #61 and #62 join at #63. Because #63 rejected both its adapter and
baseline, #67 freezes a two-pass constrained protocol and #68 evaluates the new
small-model candidate. Because #68 and #69 failed their model gates, #70
qualifies broader deterministic sentence rules for integration in #72, while
#71 qualifies contextual inflection for integration in #73. After #74 rejected
the compact-model route, #75 adds only the deterministic residual sentence
syntax coverage supported by exact evidence. Issue #77 makes these qualified
sentence components practical through one persistent local process, and #76
freezes the sentence-only installed-package gate before any paragraph claim.
Issue #64 is the broader paragraph release gate and #66 is the final owner
verification.

The fresh #76 development run after #78 now qualifies without changing the
gates: automatic precision and full-correction accuracy are `1.00` (`6 TP`,
`0 FP`), reviewable precision is `1.00` (`18 TP`, `0 FP`), and all protected,
offline, process, memory, and stability checks pass. The closed development
report was frozen before the one-shot holdout.

The holdout is now consumed and did not qualify: automatic exact-edit
precision remained `1.00` (`5 TP`, `0 FP`), but one of five automatically
changed cases was incomplete, yielding full-correction accuracy `0.80`. The
threshold remains `1.00`; the result must not be tuned against or rerun. #76
remains open and does not unblock the paragraph release gate.

Fine-tuning is an experiment after the prompt-only baseline. A rejected adapter
is a valid #63 outcome, but #43 cannot proceed until another exact configuration
passes the accepted suggestion gates.

## Critical Path

M0-01 -> M0-03 -> M0-05 -> M0-06 -> M0-07 -> M1-02 -> M1-06 -> M2-05 -> M3-01 -> M3-02 -> M3-06 -> M4-03 -> M4-04

M5 policy and evidence path:

`#54 -> #65 -> #55 -> #56 -> (#57 + #58) -> (#59 + #60) -> #61 -> #63 -> #67 -> #68 -> #69 -> ((#70 -> #72) + (#71 -> #73)) -> #74 -> #75 -> #77 -> #76 -> (#43 -> #64) -> #66`

Rule implementations M1-03 through M1-05 can proceed independently after segmentation and the rule registry. Documentation and performance work in M3 can proceed in parallel after their listed dependencies close.
