# Known limitations

- The current runtime covers a small deterministic rule set and a mock local backend path.
- Local generation integration is available through the mock transport path.
  No tested local model has qualified for production correction or suggestions;
  the repaired evidence, specialist prompts, runtime comparison, and production
  adapter are tracked by M5 and [#43](https://github.com/PSyron/polis/issues/43).
- No DOCX/ODT/RTF document adapters are in scope for this repository yet.
- No GUI is included.
- No broad stylistic rewriting is performed; corrections are limited and
  intentionally conservative.
- Optional LanguageTool support requires a separately installed LanguageTool
  6.8 process and Java runtime. The measured local installation plus OpenJDK was
  about 733 MB, with about 630 MiB RSS after startup.
- The LanguageTool rule is synchronous. Both `analyze()` and `analyze_async()`
  can wait up to its configured timeout, and it only covers reviewed missing
  commas before `że` and `żeby`.
- The source-built two-rule LanguageTool subset is not a general Polish corrector
  and has not passed the M5 automatic-correction source-policy gate.
- The hybrid architecture in [ADR-0008](architecture/decisions/0008-hybrid-correction-policy.md)
  is implemented as the baseline delivery behavior in #60. `Analyzer.correct()`
  now applies a versioned source-policy for deterministic rules and exposes
  optional suggestion outcomes for backend visibility.

## Accuracy and policy notes

The system is conservative by design:

- missed findings are preferred over aggressive rewriting,
- unresolvable edits are not applied,
- and correction selection is explicit.

Review known limitations in `docs/quality-baseline.md` and release planning in
`docs/project/ROADMAP.md`.
