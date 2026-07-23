# Known limitations

- The current runtime covers a small deterministic rule set and a mock local backend path.
- Local generation integration is available through the mock transport path.
  No tested local model has qualified for production correction or suggestions;
  the repaired evidence, specialist prompts, runtime comparison, and production
  adapter are tracked by M5 and [#43](https://github.com/PSyron/polis/issues/43).
- The #60 specialist engine and router boundary are implemented and tested with
  injected fakes. No default router identifies residual syntax or inflection
  work, and no real specialist backend is configured until later M5 selection.
- The sentence-only category router from #69 is experimental and is not wired
  into the default analyzer. Its best configuration, Qwen3 1.7B MLX, reached
  only 0.571 syntax precision and 0.160 syntax recall on development. Bielik
  1.5B and Qwen3 0.6B produced no exact syntax edits. No configuration
  qualified, and corpus-v3 holdout remains unopened for this experiment.
- Issue #70 qualified four LanguageTool punctuation rule IDs on sentences at
  precision 1.00 and recall 0.038 on its one-shot holdout. Source-policy version
  1.1 enables the three newly exposed IDs alongside the two existing IDs. This
  remains narrow punctuation coverage and does not correct syntax or inflection.
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
  one-shot holdout is consumed. Issue #114 prepares the independent CC0-1.0
  `polis_polish_correction_safety_corpus_v1`. Paweł Cyroń reviewed all 240 cases
  and the corpus is frozen, but issue #114 produces no holdout score. The new
  corpus does not replace corpus v3 or the broader corpus work tracked by #85;
  a follow-up issue owns the one-shot re-qualification run.
- No DOCX/ODT/RTF document adapters are in scope for this repository yet.
- No GUI is included.
- No broad stylistic rewriting is performed; corrections are limited and
  intentionally conservative.
- The preferred sentence-only LanguageTool path requires OpenJDK and an explicit
  local build of the pinned vendored 6.8 subset. It reuses one persistent stdio
  JVM; the #77 benchmark measured 441,483,264 bytes combined Python and Java RSS,
  938.60 ms cold startup, and 5.08 ms warm p95. Java artifacts are not included
  in wheel or sdist, and Polis does not download them.
- The older optional HTTP mode still requires a separately started LanguageTool
  6.8 process on loopback. The two modes cannot be enabled together.
- The LanguageTool rule is synchronous. Both `analyze()` and `analyze_async()`
  can wait up to its configured timeout, and it only covers five reviewed
  missing-comma rule IDs.
- The source-built five-rule LanguageTool subset is not a general Polish corrector.
  Only those qualified comma findings are automatic under
  source-policy `1.1`; contextual inflection is reviewable, and paragraph
  behavior has not passed an M5 release gate.
- The hybrid architecture in [ADR-0008](architecture/decisions/0008-hybrid-correction-policy.md)
  is implemented as the baseline delivery behavior in #60. `Analyzer.correct()`
  and `correct_async()` share one orchestration path, apply a versioned
  source-policy for deterministic rules, keep every model edit reviewable, and
  expose optional suggestion status and actual call counts.

## Accuracy and policy notes

The system is conservative by design:

- missed findings are preferred over aggressive rewriting,
- unresolvable edits are not applied,
- and correction selection is explicit.

Review known limitations in `docs/quality-baseline.md` and release planning in
`docs/project/ROADMAP.md`.
