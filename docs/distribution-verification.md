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

Install both wheel and sdist in a fresh environment and run:

```console
python -m venv /tmp/polis-release-check
/tmp/polis-release-check/bin/pip install --no-deps dist/polis_nlp-<version>-py3-none-any.whl
/tmp/polis-release-check/bin/python -c "from importlib.metadata import version; print(version('polis-nlp'))"
/tmp/polis-release-check/bin/python -m polis.cli analyze --json "Zeby nauczyc sie polskiego."
```

Repeat for the sdist:

```console
/tmp/polis-release-check/bin/pip install --no-deps dist/polis_nlp-<version>.tar.gz
/tmp/polis-release-check/bin/python -m polis.cli analyze --json "Zeby nauczyc sie polskiego."
```

## Checks covered by tests

- `tests/test_distribution_artifacts.py` verifies metadata and allow-listed file
  contents in built artifacts.
- `tests/test_release_distribution_installation.py` verifies isolated wheel/sdist
  installation and import/CLI smoke behavior.
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
