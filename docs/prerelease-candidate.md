# Prerelease candidate verification

Use this checklist to produce and validate an installable `M3-06` prerelease candidate.

## 1) Prepare artifact

```console
uv run --locked --extra dev python scripts/verify_prerelease_candidate.py
```

This runs:

- fast quality tests,
- ruff checks,
- strict mypy,
- wheel + sdist build,
- artifact metadata checks,
- offline smoke verification.

The script prints hashes for both artifacts.

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

Store command output, artifact names, and hashes in milestone notes. Include:

- `python -m build` command output,
- `scripts/verify_distribution_artifacts.py` result,
- offline verification output (`tests/test_offline_verification.py`),
- public issue references.

## Known limits

- This checklist is scoped to local checks and current repository assumptions.
- Release publication and external upload are outside `M3-06`.

