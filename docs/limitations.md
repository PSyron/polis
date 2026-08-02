# Known limitations and product boundary

- The current runtime covers a small deterministic rule set and a mock local backend path.
- Polis is a complete offline runtime without a model. No production support
  waits for model qualification, and optional model research never blocks a
  runtime release. The runtime release path does not require a model, Java
  process, network service, research corpus, or consumed holdout.
- Local generation integration is available through the mock transport path.
  No tested local model has qualified for production correction or suggestions;
  repaired evidence, specialist prompts, runtime comparison, and adapter work
  remain optional research evidence.
- The #60 specialist engine and router boundary are implemented and tested with
  injected fakes. No default router identifies residual syntax or inflection
  work, and no real specialist backend is configured for the supported runtime.
- The sentence-only category router from #69 is experimental and is not wired
  into the default analyzer. Its best configuration, Qwen3 1.7B MLX, reached
  only 0.571 syntax precision and 0.160 syntax recall on development. Bielik
  1.5B and Qwen3 0.6B produced no exact syntax edits. No configuration
  qualified, and corpus-v3 holdout remains unopened for this experiment.
- Issue #70 qualified five LanguageTool punctuation rule IDs on sentences at
  precision 1.00 and recall 0.038 on its one-shot holdout. Source-policy version
  1.1 is the historical qualification record for all five reviewed IDs. Active
  policy `1.2` preserves only that membership under the exact
  `check.allowlisted_comma` / `pl-6.8-five-rule-comma/1.0` behavior identity.
  This remains narrow punctuation coverage and does not correct syntax or
  inflection.
- The sentence-only contextual inflection router reached precision 1.00 and
  supported recall 0.667 on its one-shot holdout and is available through an
  optional local stdio configuration. It is suggestion-only; first-name
  ambiguity, verbal agreement, most government relations, and all paragraph
  behavior remain unsupported.
- Issue #74 retested the pinned Qwen3 1.7B MLX model with a generic verifier,
  an evidence-specific checklist plus verifier, and separate diagnosis plus
  correction. The best precision was 1.00 at only 0.04 syntax recall; the best
  recall was 0.16 at 0.571 precision. No route qualified, holdout remains
  unopened, and no real model is enabled for sentence syntax suggestions.
- Issue #75 adds reviewable deterministic suggestions for only three
  sentence-initial constructions: missing `się` after `On/Ona/Ono boi` or
  `Nie spodziewaliśmy`, and missing `tym` in `Im …, bardziej …`. Development
  produced 3 true-positive edits, no false positives, and precision 1.00. The
  142-sentence one-shot holdout contained no eligible construction, so it
  produced no edits and could not establish non-vacuous precision. The sources
  are not automatically applied, do not generalize to other reflexive verbs or
  word-order defects, and abstain on multi-sentence input.
- The corpus-v3 installed-package sentence safety gate did not qualify and its
  one-shot holdout is consumed. The independent CC0-1.0
  `polis_polish_correction_safety_corpus_v1` is frozen and owner-reviewed. Issue
  #115 qualified its 80-case development split, then executed the independent
  160-case holdout exactly once. The holdout failed: automatic precision and
  correction accuracy were `1.00`, but the reviewable channel produced `0 TP /
  2 FP` and precision `0.00` against the required `0.90`. The holdout is
  consumed and cannot be rerun or used for tuning. The corpus does not replace
  corpus v3 or the broader optional research work tracked by #85, and #76
  remains open.
- The evaluated nominal-agreement extension reached reviewable inflection
  recall `18/20` on development, but the complete reviewable source produced
  `0 TP / 2 FP` on the one-shot holdout. The extension was therefore removed
  from active runtime after the verdict. No replacement was selected or tuned
  against the consumed records; collective and quantifying subject agreement
  remains unsupported.
- Issue #119 prepares `polis_polish_correction_safety_corpus_v2` as an
  independent CC0-1.0 qualification asset. All 240 cases were reviewed by the
  authorized `Polis architecture owner` role and frozen at canonical JSON
  SHA-256
  `53cfce6b9cbe3f188290a064b34527912ea8f2a85c9ed29a67984c5ef5caaa29`.
  This produces no development or holdout quality score, does not reverse the
  failed #115 verdict, and does not qualify #76. A separate one-shot gate is
  still required. This work remains separate from #85 and #90.
- Issue #146 ran 80 development cases in two stable repetitions under the
  unchanged sentence-only gates and was not qualified. Automatic precision and
  correction accuracy were `1.00`, with recall `0.3333333333333333`; the
  reviewable channel proposed no edits and failed the required non-vacuous
  precision gate. Structured validity was `1.00` and both protected-negative
  counts were zero. Aggregate report SHA-256 is
  `7485c543a5abcfe45096cfc9334b59cf4c5dd510186c6318a44d0c38cdeb1141`.
  There is no frozen gate, the marker is absent, and the holdout was not
  reserved, materialized, or run. Development will not be rerun or used for
  tuning. #76 remains open and Task 6 is forbidden. The result does not qualify
  a production model or paragraph behavior.
- No DOCX/ODT/RTF document adapters are in scope for this repository yet.
- No GUI is included.
- No broad stylistic rewriting is performed; corrections are limited and
  intentionally conservative.
- The default installation has no production model or LanguageTool dependency.
  Research corpora, benchmark runners, training assets, and holdout evidence
  remain repository-only workflows; they do not establish production support
  and optional model research never blocks a runtime release.
- Default Polis runtime does not require OpenJDK, a LanguageTool process, a
  model, or network access. The optional sentence-only vendored LanguageTool
  path requires OpenJDK and an explicit local build of the pinned vendored 6.8
  subset. It reuses one persistent stdio JVM; the #77 benchmark measured
  441,483,264 bytes combined Python and Java RSS, 938.60 ms cold startup, and
  5.08 ms warm p95. Java artifacts are not included in wheel or sdist, and
  Polis does not download them.
- The older optional HTTP mode still requires a separately started LanguageTool
  6.8 process on loopback. The two modes cannot be enabled together.
- The LanguageTool rule is synchronous. Both `analyze()` and `analyze_async()`
  can wait up to its configured timeout, and it only covers five reviewed
  missing-comma rule IDs.
- The source-built five-rule LanguageTool subset is not a general Polish corrector.
  Only those qualified comma findings are automatic under
  active source-policy `1.2` when their complete behavior identity matches;
  policy `1.1` remains the historical qualification record. Contextual
  inflection is reviewable, sentence-only, and limited to narrow constructions,
  and paragraph behavior has not passed an M5 release gate.
- `polis.evaluation` remains import-compatible for existing evaluator helpers in
  the current 0.x line, but it is not the primary runtime analysis API. Large
  corpora, holdouts, reports, experiments, and training assets are excluded from
  wheel and source-distribution artifacts.
- The hybrid architecture in [ADR-0008](architecture/decisions/0008-hybrid-correction-policy.md)
  is implemented as the baseline delivery behavior in #60. `Analyzer.correct()`
  and `correct_async()` share one orchestration path, apply a versioned
  source-policy for deterministic rules, keep every model edit reviewable, and
  expose optional suggestion status, actual call counts, and the effective
  policy version. Policy `1.2` adds exact behavior identity enforcement; it
  does not qualify another rule, LanguageTool feature, or model.
  [ADR-0020](architecture/decisions/0020-runtime-first-product-charter.md)
  supersedes only the mandatory-model critical path; it does not rewrite the
  failed qualification results above.

## Accuracy and policy notes

The system is conservative by design:

- missed findings are preferred over aggressive rewriting,
- unresolvable edits are not applied,
- and correction selection is explicit.

Review known limitations in `docs/quality-baseline.md` and release planning in
`docs/project/ROADMAP.md`.
