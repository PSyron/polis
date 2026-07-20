# Build and development dependency license review

- Review date: 2026-07-20
- Owner: Paweł Cyroń
- Scope: the complete `uv.lock` graph for the `dev` extra, including the local
  project and build backend
- Decision: approved for build and development use under the obligations below

The exact versions and artifact hashes are recorded in `uv.lock`. The Evidence
column links to the immutable version-specific PyPI JSON used to verify package
identity and published license metadata. Repository license files were checked
where PyPI exposes only a legacy classifier.

| Package | Version | SPDX expression | Role | Evidence and obligations |
| --- | --- | --- | --- | --- |
| `ast-serialize` | 0.6.0 | MIT | mypy transitive | [PyPI metadata](https://pypi.org/pypi/ast-serialize/0.6.0/json); preserve the copyright and MIT notice if redistributed. |
| `build` | 1.5.0 | MIT | direct development | [PyPI metadata](https://pypi.org/pypi/build/1.5.0/json); preserve the copyright and MIT notice if redistributed. |
| `colorama` | 0.4.6 | BSD-3-Clause | build transitive on Windows | [PyPI metadata](https://pypi.org/pypi/colorama/0.4.6/json); preserve copyright, conditions, and disclaimer; do not use contributor names for endorsement. |
| `hatchling` | 1.31.0 | MIT | direct build and development | [PyPI metadata](https://pypi.org/pypi/hatchling/1.31.0/json); preserve the copyright and MIT notice if redistributed. |
| `iniconfig` | 2.3.0 | MIT | pytest transitive | [PyPI metadata](https://pypi.org/pypi/iniconfig/2.3.0/json); preserve the copyright and MIT notice if redistributed. |
| `librt` | 0.13.0 | MIT | mypy transitive | [PyPI metadata](https://pypi.org/pypi/librt/0.13.0/json); preserve the copyright and MIT notice if redistributed. |
| `mypy` | 2.3.0 | MIT | direct development | [PyPI metadata](https://pypi.org/pypi/mypy/2.3.0/json); preserve the copyright and MIT notice if redistributed. |
| `mypy-extensions` | 1.1.0 | MIT | mypy transitive | [PyPI metadata](https://pypi.org/pypi/mypy-extensions/1.1.0/json); preserve the copyright and MIT notice if redistributed. |
| `packaging` | 26.2 | Apache-2.0 OR BSD-2-Clause | build, Hatchling, and pytest transitive | [PyPI metadata](https://pypi.org/pypi/packaging/26.2/json); the compound expression receives explicit approval under the BSD-2-Clause option. Preserve its copyright, license conditions, and disclaimer if redistributed. |
| `pathspec` | 1.1.1 | MPL-2.0 | Hatchling and mypy transitive | [PyPI metadata](https://pypi.org/pypi/pathspec/1.1.1/json); MPL-2.0 is explicitly approved for this build/development-only dependency. Preserve notices and license text; if modified covered files are distributed, make their source available under MPL-2.0. Polis does not modify or bundle it. |
| `pluggy` | 1.6.0 | MIT | pytest transitive | [PyPI metadata](https://pypi.org/pypi/pluggy/1.6.0/json); preserve the copyright and MIT notice if redistributed. |
| `polis-nlp` | 0.0.0 | MIT | local project | `pyproject.toml` and `LICENSE`; project-authored code and documentation remain MIT-licensed. |
| `pygments` | 2.20.0 | BSD-2-Clause | pytest transitive | [PyPI metadata](https://pypi.org/pypi/pygments/2.20.0/json); preserve copyright, license conditions, and disclaimer if redistributed. |
| `pyproject-hooks` | 1.2.0 | MIT | build transitive | [PyPI metadata](https://pypi.org/pypi/pyproject-hooks/1.2.0/json); preserve the copyright and MIT notice if redistributed. |
| `pytest` | 9.1.1 | MIT | direct development | [PyPI metadata](https://pypi.org/pypi/pytest/9.1.1/json); preserve the copyright and MIT notice if redistributed. |
| `ruff` | 0.15.22 | MIT | direct development | [PyPI metadata](https://pypi.org/pypi/ruff/0.15.22/json); preserve the copyright and MIT notice if redistributed. |
| `trove-classifiers` | 2026.6.1.19 | Apache-2.0 | Hatchling transitive | [PyPI metadata](https://pypi.org/pypi/trove-classifiers/2026.6.1.19/json); preserve the license and notices, and mark modified files if redistributed. |
| `typing-extensions` | 4.16.0 | PSF-2.0 | mypy transitive | [PyPI metadata](https://pypi.org/pypi/typing-extensions/4.16.0/json); preserve the PSF license and notices if redistributed. |

## External bootstrap tool

uv cannot be part of the graph it resolves, so it is reviewed and pinned
separately. `tool.uv.required-version` rejects any version other than 0.11.2,
and the README installs that exact release.

| Tool | Version | SPDX expression | Role | Evidence and obligations |
| --- | --- | --- | --- | --- |
| `uv` | 0.11.2 | Apache-2.0 OR MIT | environment bootstrap and locked workflow | [PyPI metadata](https://pypi.org/pypi/uv/0.11.2/json) and [upstream licensing](https://github.com/astral-sh/uv/tree/0.11.2#license); the compound expression receives explicit approval under the MIT option. Preserve the copyright and MIT license notice if redistributed. |

## Adoption decision

All locked packages except `pathspec` and `packaging` use a single SPDX license
already allowed by ADR-0001. `packaging` combines two allowed licenses with
`OR`; Polis adopts it under BSD-2-Clause. The external uv bootstrap tool also
uses a compound expression, `Apache-2.0 OR MIT`, and is explicitly adopted
under the MIT option. `pathspec` uses MPL-2.0, which is outside the default
allowlist; it is adopted only as an unmodified transitive build/development
dependency and is not included in Polis distribution artifacts. These explicit
decisions satisfy ADR-0001's dedicated-review requirement. A change to any
reviewed expression, role, version, or redistribution model requires a new
review.
