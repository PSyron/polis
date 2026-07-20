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

## Accuracy and policy notes

The system is conservative by design:

- false positives are preferred over aggressive rewriting,
- unresolvable edits are not applied,
- and correction selection is explicit.

Review known limitations in `docs/quality-baseline.md` and release planning in
`docs/project/ROADMAP.md`.
