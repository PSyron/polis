# Runtime-first portfolio disposition

Decision authority:

- Issue #120
- ADR-0020
- the accepted runtime-first charter in `PROMPT.md` and `docs/project/ROADMAP.md`

Baseline snapshot for this manifest:

- Baseline date: 2026-08-01
- Repository: `PSyron/polis`
- Source: Task 0 live portfolio baseline recorded locally; this manifest does not
  mutate GitHub
- Open in `M5 - Hybrid Polish Correction`: #43, #64, #66, #76, #84, #85, #86,
  #87, #88, #89, #90, #92, #93, #119
- Open in `M6 - Internal Architecture and Extensibility`: #95, #96, #97, #98,
  #99, #100
- Open with no milestone: #120
- No open issue in the recorded baseline carries `status:superseded`, and the
  repository did not yet have that label

Milestone definitions:

- `Runtime 0.x Hardening`: active product safety and invariant work; no due
  date
- `Research — Optional Local Model Qualification`: optional evidence work; no
  due date

Research evidence is preserved. Superseded issues are historical planning and
evidence records, not completed work. This manifest distinguishes closed as
superseded from completed and preserves surviving research destinations.

## Exact standard body/comment text

### Research issue section to append

```markdown
## Runtime-first charter disposition (2026-08-01)

Classification: optional research under ADR-0020 and #120.

This issue preserves its research evidence and internal research dependencies.
Its outcome does not block a Polis runtime release and cannot qualify an
unverified model as supported product behavior.
```

### Superseded issue comment prefix

```markdown
Superseded by the runtime-first product charter adopted in ADR-0020 and tracked
through #120. The acceptance criteria were not completed.
```

### Product issue body requirements

- `#84` replaces `Depends on completion of #76` with an implementation-
  independent runtime section stating that automatic privileges are versioned
  product behavior, new automatic privileges still require direct source
  behavior evidence, and the runtime issue no longer depends on optional
  research completion.
- `#95` appends a product-hardening section stating that it follows `#84` in
  the supported runtime lane and does not turn M6 architecture work into a
  current runtime-release blocker.
- `#100` records `#95` as an external hardening prerequisite, not an M6 child,
  and its child checklist becomes `#96`, `#97`, `#98`, and `#99` only.
- `#120` updates its checklist/body to reference PR #121 as Phase 1 and to
  state that the issue closes only after every live-state assertion in this
  manifest passes.

## Execution gates

- Every research issue body says it does not block runtime releases.
- `#76` names `#119` as its current research dependency.
- Other research issues retain only internal research dependencies.
- `#84` is unblocked from `#76`.
- `M5 - Hybrid Polish Correction` closes only after its open issue count reaches
  zero.
- `#120` closes only after every live-state assertion passes.

## Issue-by-issue disposition manifest

| Group | Issue | Current state | Target state | Labels | Milestone | Dependency/body change | Closure reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Product | #84 | Open in M5 legacy release-train metadata; runtime product gate still represented with a dependency on #76. | Open runtime product gate. | Remove `status:blocked`; preserve remaining current labels. | Move from `M5 - Hybrid Polish Correction` to `Runtime 0.x Hardening`. | Replace `Depends on completion of #76` with the implementation-independent runtime section; state that new automatic privileges still require evidence and that optional research does not block this issue. | - |
| Product | #95 | Open in M6 as future architecture/hardening follow-up. | Open product-hardening follow-up after #84. | Preserve current labels. | Move from `M6 - Internal Architecture and Extensibility` to `Runtime 0.x Hardening`. | Append the product-hardening disposition so the issue is explicitly part of the runtime lane. | - |
| Product | #120 | Open with no milestone. | Open portfolio-migration controller for the runtime-first charter. | Change to `type:decision`, `area:core`, `priority:P0`. | Assign `Runtime 0.x Hardening`. | Update checklist/body to mark PR #121 as Phase 1 and to require final live-state verification before closure. | - |
| Research | #76 | Open in M5 as optional model-qualification work. | Open optional research gate. | Retain `status:blocked` only while its internal research dependency remains unresolved; preserve other current labels. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section and name `#119` as the current independent requalification dependency; state that this issue does not block runtime releases. | - |
| Research | #85 | Open in M5 as research follow-up. | Open optional research corpus work. | Retain `status:blocked` only while internal research dependencies remain unresolved; preserve other current labels. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section; retain only internal research dependencies and state that this issue does not block runtime releases. | - |
| Research | #86 | Open in M5 as research/qualification replay work. | Open optional research qualification-replay work. | Retain `status:blocked` only while internal research dependencies remain unresolved; preserve other current labels. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section; retain only internal research dependencies and state that this issue does not block runtime releases. | - |
| Research | #87 | Open in M5 as research qualification work. | Open optional research qualification work. | Retain `status:blocked` only while internal research dependencies remain unresolved; preserve other current labels. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section; retain only internal research dependencies and state that this issue does not block runtime releases. | - |
| Research | #88 | Open in M5 as research integration work. | Open optional provider research integration work. | Retain `status:blocked` only while internal research dependencies remain unresolved; preserve other current labels. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section; retain only internal research dependencies and state that this issue does not block runtime releases. | - |
| Research | #89 | Open in M5 as research ranker qualification work. | Open optional bounded-ranker research work. | Retain `status:blocked` only while internal research dependencies remain unresolved; preserve other current labels. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section; retain only internal research dependencies and state that this issue does not block runtime releases. | - |
| Research | #90 | Open in M5 as research majority-coverage gate work. | Open optional installed-package research gate work. | Retain `status:blocked` only while internal research dependencies remain unresolved; preserve other current labels. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section; retain only internal research dependencies and state that this issue does not block runtime releases. | - |
| Research | #119 | Open in M5 as the current research prerequisite. | Open optional research prerequisite. | Preserve current labels; keep unblocked. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section and state that this issue does not block runtime releases. | - |
| Superseded | #43 | Open in M5 as part of the old combined product/research release train. | Closed as superseded historical evidence. | Add `status:superseded`; remove `status:blocked`. | Remove from `M5 - Hybrid Polish Correction`. | Add the superseded comment prefix and identify surviving research in `#88` and `#89`. | `not planned` |
| Superseded | #64 | Open in M5 as the paragraph/integration release gate in the old train. | Closed as superseded historical evidence. | Add `status:superseded`; remove `status:blocked`. | Remove from `M5 - Hybrid Polish Correction`. | Add the superseded comment prefix and state that paragraph integration is outside the current Polis runtime product. | `not planned` |
| Superseded | #66 | Open in M5 as the final old-train owner verification gate. | Closed as superseded historical evidence. | Add `status:superseded`; remove `status:blocked`. | Remove from `M5 - Hybrid Polish Correction`. | Add the superseded comment prefix and state that product verification is now owned by runtime release gates. | `not planned` |
| Superseded | #92 | Open in M5 as the old combined artifact-publication gate. | Closed as superseded historical evidence. | Add `status:superseded`; remove `status:blocked`. | Remove from `M5 - Hybrid Polish Correction`. | Add the superseded comment prefix and state that runtime publication no longer depends on the combined M5 artifact graph. | `not planned` |
| Superseded | #93 | Open in M5 as the umbrella sequencing tracker for the old release path. | Closed as superseded historical evidence. | Add `status:superseded`; remove `status:blocked`. | Remove from `M5 - Hybrid Polish Correction`. | Add the superseded comment prefix and state that active sequencing is replaced by the runtime product lane and the optional research lane. | `not planned` |
| Future product | #96 | Open in M6 future product architecture. | Remain open future product architecture. | Preserve current labels. | Remain in `M6 - Internal Architecture and Extensibility`. | No dependency/body change in this migration. | - |
| Future product | #97 | Open in M6 future product architecture. | Remain open future product architecture. | Preserve current labels. | Remain in `M6 - Internal Architecture and Extensibility`. | No dependency/body change in this migration. | - |
| Future product | #98 | Open in M6 future product architecture. | Remain open future product architecture. | Preserve current labels. | Remain in `M6 - Internal Architecture and Extensibility`. | No dependency/body change in this migration. | - |
| Future product | #99 | Open in M6 future product architecture. | Remain open future product architecture. | Preserve current labels. | Remain in `M6 - Internal Architecture and Extensibility`. | No dependency/body change in this migration. | - |
| Future product | #100 | Open in M6 future product architecture with `#95` still represented as part of its child/dependency framing. | Remain open future product architecture. | Preserve current labels. | Remain in `M6 - Internal Architecture and Extensibility`. | Treat `#95` as an external hardening prerequisite, not an M6 child; the child checklist becomes `#96`, `#97`, `#98`, and `#99` only. | - |
