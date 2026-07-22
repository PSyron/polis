# Distribution verification for M4-03

This document records the reproducible commands used to produce and validate the
PyPI-ready distribution artifacts.

## Release artifact generation

For exploratory local packaging, the commands below remain useful. A release
candidate instead follows `docs/prerelease-candidate.md`, which must build exactly
once and freeze `dist/release-manifest.json`:

```console
python -m build --no-isolation --outdir dist
python scripts/verify_distribution_artifacts.py --dist dist
```

`python -m build` must emit exactly one wheel and one source archive.

## Artifact metadata and content checks

- Verify metadata keys:
  - `License-Expression` is `MIT`
  - `License-File` is `LICENSE`
- Verify packaged long description uses markdown and package text is present.
- Verify artifact contents:
  - includes `LICENSE` in wheel and sdist
  - includes `PKG-INFO` / wheel `METADATA`
  - includes `src/polis` and packaged dataset files
  - excludes `tests/typecheck/` test fixtures

## Clean-install smoke test

The installed CLI owns a UTF-8 process boundary for stdin, stdout, and stderr. The
automated smoke check starts it with `PYTHONIOENCODING=cp1252`, passes Polish text,
decodes output as UTF-8, and verifies the exact text. This reproduces a legacy
Windows inherited-codec environment while keeping direct Python calls to `run()`
caller-owned. Text lines retain platform-native line endings (`LF` on POSIX and
`CRLF` on Windows); the cross-platform process contract fixes their encoding, not
the operating system's newline convention.

Run the portable verifier from the repository root:

```console
python scripts/verify_distribution_install.py --dist dist
```

The script verifies both the wheel and sdist. It creates temporary environments with
the platform's correct `bin` or `Scripts` layout and sets the inherited CP1252
environment through Python, so the same command is valid in POSIX shells, Windows
PowerShell, and `cmd.exe`.

## Checks covered by tests

- `tests/test_distribution_artifacts.py` verifies metadata and allow-listed file
  contents in built artifacts.
- `tests/test_release_distribution_installation.py` verifies isolated wheel/sdist
  installation and import/CLI smoke behavior, including the inherited-CP1252 UTF-8
  process boundary.
- `tests/test_privacy_dependency_audit.py` and `tests/test_dependency_licenses.py`
  validate release-audit constraints required before publication.

## Supported matrix notes

Issue #31 requires clean installation and smoke verification for the supported
release configurations. Current supported matrix is tracked in
`docs/architecture/decisions/0001-python-platform-licensing-policy.md`; this check
is executed for each environment in CI/milestone release workflow.

## Publication checklist output

Do not calculate an unrelated second set of publication hashes. Keep the frozen
manifest and all verifier output with the release notes. To upload only the two paths
listed by `artifacts[].filename` in `dist/release-manifest.json`, do not use a
`dist/*` wildcard, rebuild, rename, or modify them.

For example, the `0.2.0rc1` upload command names the frozen files explicitly:

```console
python -m twine upload \
  dist/polis_nlp-0.2.0rc1-py3-none-any.whl \
  dist/polis_nlp-0.2.0rc1.tar.gz
```

Run the uploader from the controlled release environment; it is intentionally not a
runtime or project development dependency.

After PyPI reports the release, verify its exact filenames and SHA-256 digests:

```console
python scripts/release_identity.py verify-published \
  --manifest dist/release-manifest.json
```

The post-publication command is intentionally network-backed and release-only. A
missing, extra, or digest-mismatched PyPI file is a blocker; preserve the failed
evidence and do not replace assets or move the tag.
