# ADR-0001: Python, platform, licensing, and asset policy

- Status: Accepted
- Date: 2026-07-20
- Owner: Paweł Cyroń
- Issue: #1

## Context

Polis will provide an offline, pure-Python core and may gain optional native adapters.
CPython uses an annual release lifecycle, so the project needs a clear minimum
version and a maintainable test policy. Code, data, and model assets also have
different provenance and licensing obligations.

## Decision

### Python compatibility

Installation metadata accepts CPython >=3.12 through `requires-python = ">=3.12"` and has no upper bound.
The initially tested and supported minors are CPython 3.12, CPython 3.13, and CPython 3.14.
Newer untested minors are best-effort until they are promoted after the CI matrix passes.
A dedicated release removes an older minor after its end of life or after a
verified compatibility blocker.

### Platforms and interpreters

Per-change CI uses this initial representative matrix, not Cartesian all-platform coverage:

| Runner | Architecture | CPython versions |
| --- | --- | --- |
| `ubuntu-24.04` | x86_64 | CPython 3.12, CPython 3.13, CPython 3.14 |
| `macos-15` | arm64 | CPython 3.12, CPython 3.14 |
| `windows-2025` | x86_64 | CPython 3.12, CPython 3.14 |

These runner labels are pinned and reviewed when the provider retires an image.
The core compatibility policy is separate from availability of optional adapters.
Other Python interpreters, 32-bit platforms, musl, unsupported OS releases, and
untested OS/architecture pairs are best-effort.

Polis does not claim support for every Linux distribution. If native wheels are
published, their supported manylinux or musllinux policy and libc floor must be
documented.

### Repository, packaging, and dependency licensing

Repository code and project-authored documentation are licensed under MIT.
In future `[project]` metadata, M0-03 must set `license = "MIT"` and `license-files = ["LICENSE"]`.
Deprecated `License ::` classifiers are not used.
Both the built wheel and sdist must verify `License-Expression: MIT` and `License-File: LICENSE`.

The default approved dependency SPDX identifiers are MIT, BSD-2-Clause,
BSD-3-Clause, ISC, Apache-2.0, PSF-2.0, Python-2.0, Zlib, and 0BSD. Required
notices must be preserved. The allowlist applies to direct and transitive runtime, optional, build, and development dependencies.
Compound expressions and expressions outside this allowlist require a dedicated review before adoption.

### Data, models, and private material

Project-authored evaluation data should use CC0-1.0. Every redistributed CC-BY-4.0 dataset or subset must ship attribution and provenance.
Retain the creator, copyright notice if supplied, license link, source link where practicable, and modification indication.
Data with other or unknown terms requires review.

Model weights, tokenizers, checkpoints, and large corpora remain external. They
are never bundled or automatically downloaded. Before model support is claimed, review must confirm that publisher terms permit the intended local use.
Document material restrictions, redistribution status, attribution, and the exact revision.

User and private text, credentials, prompts containing that text, logs, and
private corpora are never committed or published. Test fixtures are synthetic or
explicitly licensed with recorded provenance.

## Alternatives considered

- Supporting >=3.11 was rejected because it is security-only and scheduled EOL
  2027-10, and it expands the maintenance matrix.
- Supporting >=3.13 was rejected because it would be unnecessarily restrictive.
- A full OS and architecture support matrix was rejected as premature.
- A strict CC0-only data policy was rejected because correctly attributed data can
  be useful.
- Permissive licensing without provenance was rejected because it is unauditable.

## Consequences

M0-03 implements the package metadata and M0-04 implements the CI matrix.
Optional adapters must document any narrower availability. This compatibility
policy receives periodic review.

## Verification

Run `python3 -m unittest tests/test_architecture_policy.py -v` and manually
review the official version and licensing sources below.

## References

- [Supported CPython versions](https://devguide.python.org/versions/)
- [PEP 602: Annual Release Cycle for Python](https://peps.python.org/pep-0602/)
- [PyPA guidance on dropping older Python versions](https://packaging.python.org/en/latest/guides/dropping-older-python-versions/)
- [PyPA platform compatibility tags](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/)
- [OSI MIT License](https://opensource.org/license/mit)
- [SPDX license list](https://spdx.org/licenses/)
- [PyPA license metadata specification](https://packaging.python.org/en/latest/specifications/core-metadata/#license)
- [Creative Commons CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)
- [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/)
