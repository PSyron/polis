# Issue #3 Package Scaffold Implementation Plan

**Goal:** Provide an installable `polis` package and reproducible local quality checks without implementing analysis behavior.

**Architecture:** Use a conventional `src/` layout whose initial modules mirror the architectural boundaries defined in `PROMPT.md`. Keep every module empty except for package metadata, so future issues can introduce interfaces without inheriting behavior. Centralize packaging, test, lint, formatting, and type-check configuration in `pyproject.toml`.

**Tech Stack:** Python 3.12+, uv, Hatchling, pytest, Ruff, mypy, build.

## Global Constraints

- Declare `requires-python = ">=3.12"` with no upper bound.
- Classify Python 3.12, 3.13, and 3.14; declare `license = "MIT"` and `license-files = ["LICENSE"]`.
- Keep production dependencies empty and add no analyzer, NLP, model, or runtime behavior.
- Keep modules aligned with `core`, `segmentation`, `rules`, `llm`, `analysis`, `correction`, `evaluation`, and `cli` responsibilities.
- Document every build and development dependency, including its license rationale.
- Publish the `polis-nlp` distribution while retaining the `polis` import namespace.
- Consume a committed `uv.lock` in every documented development command.
- Require and document uv `0.11.2` exactly as the external bootstrap tool.

---

### Task 1: Establish import and metadata expectations

**Files:**
- Create: `tests/test_package_smoke.py`

**Interfaces:**
- Consumes: installed distribution metadata for `polis`
- Produces: smoke coverage for the package root and focused package modules

- [x] Write tests that import `polis`, each focused module, and assert that distribution metadata reports version `0.0.0` and MIT licensing.
- [x] Run `pytest tests/test_package_smoke.py -v` and confirm it fails because the package is absent.

### Task 2: Create the package and reproducible tooling

**Files:**
- Create: `pyproject.toml`
- Create: `src/polis/__init__.py`
- Create: `src/polis/core/__init__.py`
- Create: `src/polis/segmentation/__init__.py`
- Create: `src/polis/rules/__init__.py`
- Create: `src/polis/llm/__init__.py`
- Create: `src/polis/analysis/__init__.py`
- Create: `src/polis/correction/__init__.py`
- Create: `src/polis/evaluation/__init__.py`
- Create: `src/polis/cli/__init__.py`

**Interfaces:**
- Produces: the `polis-nlp` distribution at version `0.0.0` and importable focused modules

- [x] Configure Hatchling with PEP 639 license metadata, Python compatibility metadata, empty production dependencies, and an explicit development group.
- [x] Configure pytest discovery, Ruff linting and formatting, and strict mypy checks for `src` and `tests`.
- [x] Lock the complete build and development graph and review every resolved license.
- [x] Add focused empty package modules and a root `__version__` derived from installed distribution metadata.
- [x] Install the project with its development group and run the smoke tests to confirm they pass.

### Task 3: Document setup and verify distribution artifacts

**Files:**
- Modify: `README.md`

- [x] Document editable development installation, each dependency group, and each declared dependency’s purpose and permissive-license rationale.
- [x] Build wheel and source distribution, inspect their core metadata for `License-Expression: MIT` and `License-File: LICENSE`, and verify that each artifact includes `LICENSE`.
- [x] Create a fresh temporary virtual environment, install the built wheel, and verify `import polis` and its declared version.
- [x] Run the complete pytest, Ruff lint, Ruff format-check, mypy, and unittest commands.
- [x] Review the diff against all issue acceptance criteria, then make the focused issue commit.
