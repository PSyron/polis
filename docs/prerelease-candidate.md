# Prerelease candidate verification

Use this checklist to produce and validate an installable prerelease candidate. Read
`docs/release-lifecycle.md` first. The example shows the first `0.2.0` candidate;
replace values only with the next legal lifecycle step.

## 1) Prepare artifact

```console
uv run --locked --extra dev python scripts/verify_prerelease_candidate.py \
  --version 0.2.0rc1 \
  --tag v0.2.0rc1 \
  --previous-version 0.2.0.dev0 \
  --latest-stable 0.1.0 \
  --manifest dist/release-manifest.json \
  --check-pypi
```

This runs:

- fast quality tests,
- ruff checks,
- strict mypy,
- exactly one wheel + sdist build,
- artifact metadata checks,
- offline smoke verification,
- exact source/artifact/tag/notes/changelog identity checks,
- release-only PyPI version-reuse check,
- one SHA-256 manifest for the exact files to publish.

The script prints the hashes frozen in `dist/release-manifest.json`. The candidate
must already be the exact version declared in `pyproject.toml` and `uv.lock`, with
matching notes and changelog section. `--check-pypi` is a required release-only
network preflight, not an optional bypass. The script also checks every existing
local release tag and rejects stale artifacts or a pre-existing manifest before it
builds. The candidate source, notes, and version changes must already be committed;
any tracked or untracked worktree change is a blocker because artifacts must bind to
the manifest's exact source commit. Do not rerun the build after freezing it.

For milestone M4-03 distribution checks (wheel/sdist clean install and release
publication checklist), continue with `docs/distribution-verification.md`.

## 2) Install artifacts in clean test locations

```console
python scripts/verify_distribution_install.py --dist dist
```

This portable command verifies the frozen wheel and sdist through platform-native
temporary environments on POSIX and Windows. Do not rebuild either artifact.

## 3) Record evidence

Store command output, artifact names, and the manifest in milestone notes. Include:

- the single `python -m build` command output,
- `scripts/verify_distribution_artifacts.py` result,
- offline verification output (`tests/test_offline_verification.py`),
- public issue references.

Before the tag is created, repeat local identity verification without rebuilding:

```console
uv run --locked --extra dev python scripts/release_identity.py verify \
  --manifest dist/release-manifest.json \
  --dist dist
```

After creating the requested tag at the manifest's `source_commit`, bind it back to
the frozen evidence:

```console
uv run --locked --extra dev python scripts/release_identity.py verify-tagged \
  --tag v0.2.0rc1 \
  --manifest dist/release-manifest.json
```

## Known limits

- This checklist is scoped to local checks and current repository assumptions.
- Release publication and external upload are outside this candidate checklist.
