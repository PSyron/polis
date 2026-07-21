# Known limitations

- The current runtime covers a small deterministic rule set and a mock local backend path.
- Local generation integration is available through the mock transport path. A real
  local model for Polish flexion, syntax, and contextual punctuation is benchmarked
  in [#42](https://github.com/PSyron/polis/issues/42); its production adapter is
  tracked separately in [#43](https://github.com/PSyron/polis/issues/43).
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

## Accuracy and policy notes

The system is conservative by design:

- missed findings are preferred over aggressive rewriting,
- unresolvable edits are not applied,
- and correction selection is explicit.

Review known limitations in `docs/quality-baseline.md` and release planning in
`docs/project/ROADMAP.md`.
