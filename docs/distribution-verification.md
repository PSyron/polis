# Distribution verification for M4-03

This document records the reproducible commands used to produce and validate the
PyPI-ready distribution artifacts.

## Release artifact generation

From a clean `main` checkout:

```console
python -m build --no-isolation --outdir dist
python scripts/verify_distribution_artifacts.py --dist dist
```

`python -m build` must emit exactly one wheel and one source archive.

After the build and before any upload, create one immutable manifest from those
exact two files:

```console
python scripts/release_identity.py manifest \
  --source-commit "$(git rev-parse HEAD)" --dist dist \
  --output dist/release-manifest.json
```

The command rejects artifacts whose filename or embedded package metadata does
not equal the canonical `pyproject.toml` version. It records each SHA-256 in the
manifest; do not run another build before upload.

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

Keep command outputs, wheel/sdist names, and SHA-256 checksums with the release notes.
Use:

```console
python - <<'PY'
import hashlib
from pathlib import Path

for name in sorted(Path('dist').glob('*')):
    digest = hashlib.sha256(name.read_bytes()).hexdigest()
    print(f"{name.name} {digest}")
PY
```

Upload only the two files listed in `dist/release-manifest.json`. After GitHub
Release and package-index publication, obtain the reported artifact digests in
a JSON object mapping filename to lowercase SHA-256, then compare them with the
same manifest:

```console
python scripts/release_identity.py verify-published \
  --manifest dist/release-manifest.json \
  --published-digests published-digests.json
```

The comparison requires an exact filename/digest set. A mismatch is an
append-only release incident: do not move a tag or replace a published asset.
Record an erratum that cites the immutable tag and the published digests instead.
`docs/release-notes/0.1.0-erratum.md` is the precedent for this procedure.
