# Compatibility policy and semantic versioning

This document publishes the M4 compatibility baseline and deprecation policy.

## Supported configurations

`polis` is verified on the same matrix as fast CI:

- CPython 3.12, 3.13, 3.14 on Linux x86_64,
- CPython 3.12, 3.14 on macOS arm64,
- CPython 3.12, 3.14 on Windows x86_64.

No optional model runtime is required for core deterministic checks.

### Evidence and deprecation policy enforcement

- Compatibility assertions are checked in `.github/workflows/fast-ci.yml` (Linux x86_64,
  macOS arm64, Windows x86_64) on each push and PR.
- For each release block, we verify the compatibility fixture and quality gates by
  running `uv run --locked --extra dev python scripts/verify_prerelease_candidate.py`.
- Any required API/schema change must update `tests/fixtures/public_api_snapshot.json`
  and include migration notes before release.

## Platform verification profile 1.0

This versioned profile assigns platform-sensitive evidence to an explicit owner.
A check that cannot run on one platform is not silently removed: it remains owned by
the stated platform job or by a separate release-gate verification path. Evidence
from one operating system does not qualify another operating system.

| Check | Owner | Platforms and verification path |
| --- | --- | --- |
| Fast deterministic suite and supported interpreter matrix | `.github/workflows/fast-ci.yml` | Linux, macOS, and Windows fast CI |
| CLI UTF-8 process boundary, including inherited CP1252 streams | `tests/test_cli.py` and `tests/test_release_distribution_installation.py` | Every fast-CI platform; clean wheel and sdist installation repeat the boundary check |
| Effective `text`/`eol` policy and checkout byte/hash stability | `tests/test_fast_ci_workflow.py` | Every fast-CI platform, including a CRLF-configured behavioral checkout |
| Vendored upstream byte-exact overrides | `.gitattributes` and `tests/test_fast_ci_workflow.py` | Every fast-CI platform; `-text -eol` must remain effective |
| POSIX executable bits for vendored launchers | `tests/test_languagetool_vendor_artifacts.py` | Linux and macOS fast CI; Windows does not model the POSIX mode bit, so the POSIX jobs retain this evidence |
| macOS network-denial evidence (`sandbox-exec`) | sentence-release qualification owner (issue #79) | macOS release job through separate release-gate verification; Linux and Windows require their own enforced denial mechanisms before either can claim equivalent evidence |
| POSIX process and resource evidence (`/bin/ps`, `lsof`, `sysctl`) | sentence-release qualification owner (issue #79) | Platform-native Linux/macOS release jobs; a Darwin-only command may not stand in for Linux evidence |
| Windows pipe, process, resource, and network-denial evidence | sentence-release qualification owner (issue #79) | Windows release job with Windows-native mechanisms; POSIX `select()` on subprocess pipes and POSIX utilities are not accepted substitutes |

The sentence-release gate must report unsupported or unavailable platform evidence as
a release blocker. A skip is acceptable only where the table assigns the same check
to another required job, such as POSIX executable-bit verification on Linux/macOS.

## Public API compatibility policy

- **Patch**: fixes, documentation-only updates, test additions, and bug fixes with no behavior-breaking effect on stable public symbols.
- **Minor**: additive public symbols, additive enum values, safer validation messages, and new optional features.
- **Major**: changes that break existing code using documented symbols (`polis.__all__` / `public API snapshots`) or serialized schema versions.

## Release version policy

Release selection uses SemVer's `MAJOR.MINOR.PATCH` line: a new additive Polis
line after `0.1.0` is `0.2.0`. Python package metadata and artifacts use the
corresponding canonical PEP 440 forms: normal development is `0.2.0.dev0`, a
candidate is `0.2.0rcN`, and the stable package is `0.2.0`. Every selected
package version has the exact matching Git tag `v<version>`; abbreviated,
local-version, equal, and lower forms are rejected by the release verifier.

`pyproject.toml` is the authoritative package-version source. The verifier
requires that source metadata, artifact names, embedded wheel/sdist metadata,
manifest, release-note heading, changelog heading, and requested tag describe
one exact identity.

## Serialized data compatibility

- Public analysis JSON is currently `schema_version = 1`.
- Any change to wire shape or identifier semantics is a **major** change and must be paired with migration guidance.

## How we track compatibility

- `scripts/verify_prerelease_candidate.py` executes the quality gates.
- `tests/fixtures/public_api_snapshot.json` records stable exports and schema versions.
- `tests/test_api_compatibility.py` fails when runtime exports or schema contracts drift without snapshot updates.
- Any snapshot update requires explicit issue-level review and release-note notes.
