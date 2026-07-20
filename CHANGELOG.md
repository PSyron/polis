# Changelog

## 0.1.0 (2026-07-20)

- Added release-focused reliability work before stable publication:
  - end-to-end Polish spelling/grammar/punctuation acceptance corpus and tests,
  - dedicated privacy and dependency audit evidence and tests,
  - distribution packaging/build/install validation utilities and documentation,
  - release-artifact verification checklist for M4.
- Confirmed that release artifacts contain the expected modules and metadata and
  pass clean installation smoke tests from both wheel and sdist.
- No runtime dependencies were introduced; production distribution remains
  dependency-light.

### Known limitations

- Model-assisted backend remains constrained to the repository’s selected local
  backend abstraction and mock path used for deterministic tests.
- Styling and broad linguistic rewriting are intentionally out of scope for this
  release.
- No DOCX/ODT/RTF adapters are included; use external tooling for document
  containers.

## 0.0.0

- Initial project scaffold and core offline analysis baseline.
