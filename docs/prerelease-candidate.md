# Prerelease candidate verification

Use this checklist to produce and validate an installable `M3-06` prerelease candidate.

## 1) Prepare artifact

```console
uv run --locked --extra dev python scripts/verify_prerelease_candidate.py \
  --source-commit "$(git rev-parse HEAD)"
```

This runs:

- fast quality tests,
- ruff checks,
- strict mypy,
- wheel + sdist build,
- artifact metadata checks,
- offline smoke verification,
- one release manifest for the exact wheel and sdist it just built.

The script prints hashes for both artifacts and writes
`dist/release-manifest.json`. Before any candidate is published, retain that
exact build-once artifact set with its source commit:

The manifest binds the authoritative `pyproject.toml` version, matching artifact
names and embedded metadata, and SHA-256 digests. Do not rebuild after this
step: upload only the files named in `dist/release-manifest.json`.

Candidate naming is an explicit release-only operation. Supply the observed
local/remote tags, GitHub release tags, and package-index versions through the
release-only collector. Its fast tests use injected fakes and do not call a
network:

```console
uv run --locked --extra dev python scripts/release_identity.py candidate \
  --version 0.2.0rc1 --source-commit "$(git rev-parse HEAD)" \
  --latest-published 0.1.0 --release-only --remote origin \
  --github-repo PSyron/polis \
  --package-index-url https://pypi.org/pypi/polis-nlp/json
```

An existing local or remote tag, GitHub release, package-index version, or a
version no greater than the highest observed GitHub/package-index publication
is a release blocker. The supplied `--latest-published` value is cross-checked
against those observations; it cannot lower that boundary.

For milestone M4-03 distribution checks (wheel/sdist clean install and release
publication checklist), continue with `docs/distribution-verification.md`.

## 2) Install artifacts in clean test location (manual)

```console
python -m build --no-isolation
python -m pip install --no-deps --target /tmp/polis-candidate dist/*.whl
PYTHONPATH=/tmp/polis-candidate python - <<'PY'
import polis
print(polis.__version__)
print(polis.AnalyzerConfig())
PY
```

## 3) Record evidence

Store command output, the build-once manifest, artifact names, and hashes in
milestone notes. Include:

- `python -m build` command output,
- `scripts/verify_distribution_artifacts.py` result,
- offline verification output (`tests/test_offline_verification.py`),
- public issue references.

For every existing tag, run the byte-exact historical-evidence check before
preparing a new release:

```console
uv run --locked --extra dev python scripts/release_identity.py verify-history \
  --tag v0.1.0 --version 0.1.0
```

Fast CI runs the equivalent all-tag check through the release-identity tests;
use `verify-all-history` when running the check manually.

## Known limits

- This checklist is scoped to local checks and current repository assumptions.
- Release publication and external upload are outside `M3-06`.
