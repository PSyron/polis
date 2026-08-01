# Runtime-first portfolio disposition

Decision authority:

- Issue #120
- ADR-0020
- [accepted runtime-first charter design](../superpowers/specs/2026-08-01-runtime-first-product-charter-design.md)
  (`docs/superpowers/specs/2026-08-01-runtime-first-product-charter-design.md`)
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

- `Runtime 0.x Hardening`: active product safety and invariant work; #84 is P0
  product-safety work; #95 is P1 hardening; shared milestone membership does not
  make #95 a current runtime-release blocker.
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

- `#84`: replace the complete legacy dependency section, not only one sentence;
  remove body claims that it depends on `#76`, blocks `#64`, or blocks final
  release authorization; remove native `blockedBy` edge `#76 -> #84`; remove
  native `blocking` edge `#84 -> #64`.
- `#84` adds an implementation-independent runtime section stating that
  automatic privileges are versioned P0 product-safety behavior, new automatic
  privileges still require direct source behavior evidence, and optional
  research completion does not block this issue.
- `#95`: replace legacy M5 publication wording, including any claim that it does
  not block publication of M5; record it as P1 runtime hardening that follows
  #84 without blocking the current runtime release by milestone membership
  alone.
- `#95` appends a product-hardening section stating that it is P1 hardening after
  `#84`, that it follows the P0 product-safety gate, and that neither the shared
  milestone nor roadmap arrow makes it a current runtime-release blocker.
- `#90`: replace the complete dependency section so it keeps only internal
  optional-research dependencies `#76`, `#85`, `#86`, `#88`, and `#89`; remove
  body and native edges involving superseded `#43`, product `#84`, and blocking
  `#64`.
- `#100` records `#95` as an external hardening prerequisite, not an M6 child,
  and its child checklist becomes `#96`, `#97`, `#98`, and `#99` only.
- `#100`: replace legacy release-authority prose, including any claim that `#93`
  remains authoritative for the next release or that the current M5 publication
  controls runtime release sequencing.
- `#120` updates its checklist/body to reference PR #121 as Phase 1, carry the
  #84 P0 / #95 P1 distinction, and state that the issue closes only after every
  live-state assertion in this manifest passes.

## Execution gates

- Every research issue body says it does not block runtime releases.
- `#76` names `#119` as its current research dependency.
- Other research issues retain only internal research dependencies.
- `#84` is unblocked from `#76`.
- `M5 - Hybrid Polish Correction` closes only after its open issue count reaches
  zero.
- `#120` closes only after every live-state assertion passes.

## Post-mutation rejection assertions

- post-mutation inventory rejects `#93 remains authoritative for the next
  release`
- post-mutation inventory rejects `current M5 publication`
- post-mutation inventory rejects `blocks #64` on #84 or #90
- post-mutation inventory rejects native `blockedBy` edges from #76 to #84, from
  #43 to #90, and from #84 to #90
- post-mutation inventory rejects native `blocking` edges from #84 to #64 and
  from #90 to #64
- post-mutation inventory rejects any product-release dependency on #43, #76,
  #90, #93, model research, Java, network, research corpus, or consumed holdout

## Exact label transition ledger

- `#43`: add `status:superseded`; remove `status:blocked`; final labels `type:feature`, `area:llm`, `priority:P0`, `status:superseded`.
- `#64`: add `status:superseded`; remove `status:blocked`; final labels `type:test`, `area:evaluation`, `priority:P0`, `status:superseded`.
- `#66`: add `status:superseded`; remove `status:blocked`; final labels `type:test`, `area:evaluation`, `priority:P0`, `status:superseded`.
- `#76`: add none; remove none; final labels `type:research`, `area:evaluation`, `priority:P0`, `status:blocked`.
- `#84`: add none; remove `status:blocked`; final labels `type:bug`, `area:correction`, `priority:P0`.
- `#85`: add none; remove none; final labels `type:research`, `area:evaluation`, `priority:P0`, `status:blocked`.
- `#86`: add none; remove none; final labels `type:research`, `area:evaluation`, `priority:P0`, `status:blocked`.
- `#87`: add none; remove none; final labels `type:research`, `area:rules`, `priority:P0`, `status:blocked`.
- `#88`: add none; remove none; final labels `type:research`, `area:rules`, `priority:P0`, `status:blocked`.
- `#89`: add none; remove none; final labels `type:research`, `area:llm`, `priority:P0`, `status:blocked`.
- `#90`: add none; remove none; final labels `type:research`, `area:evaluation`, `priority:P0`, `status:blocked`.
- `#92`: add `status:superseded`; remove `status:blocked`; final labels `type:research`, `area:packaging`, `priority:P0`, `status:superseded`.
- `#93`: add `status:superseded`; remove none; final labels `type:research`, `area:packaging`, `priority:P0`, `status:superseded`.
- `#95`: add none; remove none; final labels `type:chore`, `area:evaluation`, `priority:P1`.
- `#96`: add none; remove none; final labels `type:chore`, `area:core`, `priority:P1`.
- `#97`: add none; remove none; final labels `type:chore`, `area:rules`, `priority:P2`.
- `#98`: add none; remove none; final labels `type:chore`, `area:rules`, `priority:P2`.
- `#99`: add none; remove none; final labels `type:chore`, `area:analysis`, `priority:P2`.
- `#100`: add none; remove none; final labels `type:chore`, `area:core`, `priority:P1`.
- `#119`: add none; remove none; final labels `type:research`, `area:evaluation`, `priority:P0`.
- `#120`: add `type:decision`, `area:core`; remove `type:chore`, `area:packaging`; final labels `type:decision`, `area:core`, `priority:P0`.

## Issue-by-issue disposition manifest

| Group | Issue | Current state | Target state | Labels | Milestone | Dependency/body change | Closure reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Product | #84 | Open in M5 legacy release-train metadata; runtime product gate still represented with a dependency on #76 plus legacy #64/final-release body authority. | Open P0 runtime product-safety gate. | Add none; remove `status:blocked`; final labels `type:bug`, `area:correction`, `priority:P0`. | Move from `M5 - Hybrid Polish Correction` to `Runtime 0.x Hardening`. | Replace the complete dependency section; remove #76, #64, and final-release body claims; remove native `blockedBy` #76 and native `blocking` #64; state that new automatic privileges still require evidence and optional research does not block this issue. | - |
| Product | #95 | Open in M6 as future architecture/hardening follow-up with legacy M5 publication wording. | Open P1 product-hardening follow-up after #84; not a current runtime-release blocker by milestone or arrow alone. | Add none; remove none; final labels `type:chore`, `area:evaluation`, `priority:P1`. | Move from `M6 - Internal Architecture and Extensibility` to `Runtime 0.x Hardening`. | Replace legacy M5 publication wording and append the P1 hardening disposition so the issue is explicitly part of the runtime lane without making M6 or #95 current-release blockers. | - |
| Product | #120 | Open with no milestone. | Open portfolio-migration controller for the runtime-first charter. | Add `type:decision`, `area:core`; remove `type:chore`, `area:packaging`; final labels `type:decision`, `area:core`, `priority:P0`. | Assign `Runtime 0.x Hardening`. | Update checklist/body to mark PR #121 as Phase 1, carry the #84 P0 / #95 P1 distinction, and require final live-state verification before closure. | - |
| Research | #76 | Open in M5 as optional model-qualification work. | Open optional research gate. | Add none; remove none; final labels `type:research`, `area:evaluation`, `priority:P0`, `status:blocked`. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section and name `#119` as the current independent requalification dependency; state that this issue does not block runtime releases. | - |
| Research | #85 | Open in M5 as research follow-up. | Open optional research corpus work. | Add none; remove none; final labels `type:research`, `area:evaluation`, `priority:P0`, `status:blocked`. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section; retain only internal research dependencies and state that this issue does not block runtime releases. | - |
| Research | #86 | Open in M5 as research/qualification replay work. | Open optional research qualification-replay work. | Add none; remove none; final labels `type:research`, `area:evaluation`, `priority:P0`, `status:blocked`. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section; retain only internal research dependencies and state that this issue does not block runtime releases. | - |
| Research | #87 | Open in M5 as research qualification work. | Open optional research qualification work. | Add none; remove none; final labels `type:research`, `area:rules`, `priority:P0`, `status:blocked`. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section; retain only internal research dependencies and state that this issue does not block runtime releases. | - |
| Research | #88 | Open in M5 as research integration work. | Open optional provider research integration work. | Add none; remove none; final labels `type:research`, `area:rules`, `priority:P0`, `status:blocked`. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section; retain only internal research dependencies and state that this issue does not block runtime releases. | - |
| Research | #89 | Open in M5 as research ranker qualification work. | Open optional bounded-ranker research work. | Add none; remove none; final labels `type:research`, `area:llm`, `priority:P0`, `status:blocked`. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section; retain only internal research dependencies and state that this issue does not block runtime releases. | - |
| Research | #90 | Open in M5 as research majority-coverage gate work with legacy dependencies on superseded #43, product #84, and blocking #64. | Open optional installed-package research gate work. | Add none; remove none; final labels `type:research`, `area:evaluation`, `priority:P0`, `status:blocked`. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section; replace dependency prose and native edges so only internal research dependencies #76, #85, #86, #88, and #89 remain; remove #43, #84, and #64 body/native edges; state that this issue does not block runtime releases. | - |
| Research | #119 | Open in M5 as the current research prerequisite. | Open optional research prerequisite. | Add none; remove none; final labels `type:research`, `area:evaluation`, `priority:P0`. | Move from `M5 - Hybrid Polish Correction` to `Research — Optional Local Model Qualification`. | Append the standard research section and state that this issue does not block runtime releases. | - |
| Superseded | #43 | Open in M5 as part of the old combined product/research release train. | Closed as superseded historical evidence. | Add `status:superseded`; remove `status:blocked`; final labels `type:feature`, `area:llm`, `priority:P0`, `status:superseded`. | Remove from `M5 - Hybrid Polish Correction`. | Add the superseded comment prefix and identify surviving research in `#88` and `#89`. | `not planned` |
| Superseded | #64 | Open in M5 as the paragraph/integration release gate in the old train. | Closed as superseded historical evidence. | Add `status:superseded`; remove `status:blocked`; final labels `type:test`, `area:evaluation`, `priority:P0`, `status:superseded`. | Remove from `M5 - Hybrid Polish Correction`. | Add the superseded comment prefix and state that paragraph integration is outside the current Polis runtime product. | `not planned` |
| Superseded | #66 | Open in M5 as the final old-train owner verification gate. | Closed as superseded historical evidence. | Add `status:superseded`; remove `status:blocked`; final labels `type:test`, `area:evaluation`, `priority:P0`, `status:superseded`. | Remove from `M5 - Hybrid Polish Correction`. | Add the superseded comment prefix and state that product verification is now owned by runtime release gates. | `not planned` |
| Superseded | #92 | Open in M5 as the old combined artifact-publication gate. | Closed as superseded historical evidence. | Add `status:superseded`; remove `status:blocked`; final labels `type:research`, `area:packaging`, `priority:P0`, `status:superseded`. | Remove from `M5 - Hybrid Polish Correction`. | Add the superseded comment prefix and state that runtime publication no longer depends on the combined M5 artifact graph. | `not planned` |
| Superseded | #93 | Open in M5 as the umbrella sequencing tracker for the old release path. | Closed as superseded historical evidence. | Add `status:superseded`; remove none; final labels `type:research`, `area:packaging`, `priority:P0`, `status:superseded`. | Remove from `M5 - Hybrid Polish Correction`. | Add the superseded comment prefix and state that active sequencing is replaced by the runtime product lane and the optional research lane. | `not planned` |
| Future product | #96 | Open in M6 future product architecture. | Remain open future product architecture. | Add none; remove none; final labels `type:chore`, `area:core`, `priority:P1`. | Remain in `M6 - Internal Architecture and Extensibility`. | No dependency/body change in this migration. | - |
| Future product | #97 | Open in M6 future product architecture. | Remain open future product architecture. | Add none; remove none; final labels `type:chore`, `area:rules`, `priority:P2`. | Remain in `M6 - Internal Architecture and Extensibility`. | No dependency/body change in this migration. | - |
| Future product | #98 | Open in M6 future product architecture. | Remain open future product architecture. | Add none; remove none; final labels `type:chore`, `area:rules`, `priority:P2`. | Remain in `M6 - Internal Architecture and Extensibility`. | No dependency/body change in this migration. | - |
| Future product | #99 | Open in M6 future product architecture. | Remain open future product architecture. | Add none; remove none; final labels `type:chore`, `area:analysis`, `priority:P2`. | Remain in `M6 - Internal Architecture and Extensibility`. | No dependency/body change in this migration. | - |
| Future product | #100 | Open in M6 future product architecture with `#95` still represented as part of its child/dependency framing and legacy #93/M5 release-authority prose. | Remain open future product architecture. | Add none; remove none; final labels `type:chore`, `area:core`, `priority:P1`. | Remain in `M6 - Internal Architecture and Extensibility`. | Treat `#95` as an external hardening prerequisite, not an M6 child; the child checklist becomes `#96`, `#97`, `#98`, and `#99` only; replace legacy #93/current-M5 release-authority prose. | - |
