# Fast CI Quality Checks Implementation Plan

**Goal:** Run the locked, deterministic quality gate for every push and pull
request on the representative CPython and platform matrix defined by ADR-0001.

**Architecture:** One GitHub Actions workflow fans out the exact non-Cartesian
matrix and uses the same locked uv commands documented for local development.
A standard-library validator enforces the workflow contract and can check both
YAML syntax and the security-sensitive action references without a CI-only
parser dependency.

**Tech Stack:** GitHub Actions, pinned `actions/checkout`, pinned
`actions/setup-python`, pinned `astral-sh/setup-uv`, uv 0.11.2, pytest, Ruby
Psych (local YAML syntax validation).

## Global Constraints

- Use `ubuntu-24.04` x86_64 with CPython 3.12, 3.13, and 3.14;
  `macos-15` arm64 with 3.12 and 3.14; and `windows-2025` x86_64 with 3.12
  and 3.14.
- Map policy architecture `x86_64` to the `setup-python` input `x64`; pass
  `arm64` through unchanged.
- Run on both `push` and `pull_request`; do not add slow, real-model,
  benchmark, publishing, or release jobs.
- Register `slow` and `model` pytest markers and select
  `-m "not slow and not model"` in the per-change suite.
- Use uv 0.11.2 exactly and the existing `uv.lock` development environment.
- Pin every external action to a full commit SHA and record its MIT review.
- Build wheel and sdist and verify PEP 639 license metadata and the `LICENSE`
  artifact in both distributions.
- Keep the implementation focused on issue #4 and preserve Paweł Cyroń as the
  only credited author.

---

### Task 1: Specify the workflow contract before adding the workflow

**Files:**

- Create: `tests/test_fast_ci_workflow.py`
- Create: `scripts/validate_fast_ci_workflow.py`

- [ ] **Step 1: Write a failing contract test.**

```python
def test_fast_ci_contract_is_valid() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_fast_ci_workflow.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2: Run the test before the workflow exists.**

Run: `uv run --locked --extra dev pytest tests/test_fast_ci_workflow.py -v`

Expected: FAIL because `.github/workflows/fast-ci.yml` is absent.

- [ ] **Step 3: Implement the smallest validator that checks syntax and the
  exact workflow contract.**

The validator invokes Ruby's standard Psych parser for syntax, then verifies
the required triggers, seven matrix entries, full-SHA action references,
locked uv setup, every quality command, build artifacts, license metadata,
and explicit fast-suite exclusions.

- [ ] **Step 4: Re-run the contract test.**

Run: `uv run --locked --extra dev pytest tests/test_fast_ci_workflow.py -v`

Expected: FAIL until the workflow is created.

### Task 2: Add the deterministic fast workflow and its action review

**Files:**

- Create: `.github/workflows/fast-ci.yml`
- Modify: `docs/development/dependency-licenses.md`
- Modify: `README.md`

- [ ] **Step 1: Add a single matrix job.**

Use `matrix.include` for exactly the seven ADR-0001 runner, architecture, and
CPython combinations.  Check out the source, install the selected CPython,
install uv 0.11.2 with cache enabled, synchronize `--locked --extra dev`, then
run filtered pytest, Ruff lint, Ruff formatting, strict mypy, and the
build-and-artifact verification command. Pytest collects `unittest.TestCase`,
so the workflow must not run a second unfiltered test command.

- [ ] **Step 2: Verify the built artifacts in the same job.**

After `python -m build --no-isolation`, inspect the wheel METADATA and the
sdist PKG-INFO for `License-Expression: MIT` and `License-File: LICENSE`, and
assert that each archive contains `LICENSE`.

- [ ] **Step 3: Record workflow action review and scope.**

Document the exact immutable action commits, MIT license evidence, and their
roles.  Document that fast CI deliberately excludes slow, model, benchmark,
and release activity.

### Task 3: Demonstrate failure detection and complete verification

**Files:**

- Test: `tests/test_fast_ci_workflow.py`
- Test: `scripts/validate_fast_ci_workflow.py`

- [ ] **Step 1: Validate the final workflow locally.**

Run: `uv run --locked --extra dev python scripts/validate_fast_ci_workflow.py`

Expected: `fast CI workflow contract is valid`.

- [ ] **Step 2: Prove that a deliberate contract failure is rejected.**

Copy the workflow to a temporary path, change `ubuntu-24.04` to
`ubuntu-latest`, and run the validator with `--workflow`; it must return a
non-zero status and identify the missing expected matrix entry.

- [ ] **Step 3: Run the complete local quality gate.**

Run: `uv lock --check && uv run --locked --extra dev pytest -m "not slow and not model" && uv run --locked --extra dev ruff check . && uv run --locked --extra dev ruff format --check . && uv run --locked --extra dev mypy . && uv run --locked --extra dev python -m build --no-isolation`

Expected: every command exits with status 0.

As an additional local compatibility gate, run
`uv run --locked --extra dev python -m unittest discover -s tests -v`; this is
not part of the fast workflow because it cannot apply pytest marker selection.

- [ ] **Step 4: Make the focused commit.**

Run: `git commit -m "ci: configure fast quality checks (#4)"`
