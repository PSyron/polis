# Polis

Polis is an offline Python library for analysing Polish text and proposing
minimal, structured corrections. It provides deterministic analysis and a thin
CLI wrapper for manual and scripted use while the LLM-backed backend is developed.

## Conservative correction

`Analyzer.correct()` accepts either one sentence or a multi-sentence paragraph.
It applies only high-confidence, non-conflicting deterministic suggestions and
returns both the original and corrected text with applied and skipped findings.

```python
from polis import Analyzer, AnalyzerConfig

result = Analyzer(AnalyzerConfig()).correct("Zeby jutro,powiem o tym.")
assert result.corrected_text == "Żeby jutro, powiem o tym."
```

The method does not rewrite prose, send text over the network, or apply
low-confidence and model-generated suggestions automatically.
`await Analyzer.correct_async(...)` provides the same result and ordering for
event-loop applications. Optional specialist suggestions, when explicitly
injected, remain in `skipped_findings` and report a versioned outcome with their
actual one-call/two-call budget; no real specialist model is enabled by default.

## Vendored LanguageTool sentence path

For the currently supported sentence-only LanguageTool path, first build the
pinned Polish subset explicitly; Polis does not download Java, dependencies, or
artifacts at runtime:

```console
cd third_party/languagetool-pl
./scripts/build.sh
```

Configure the resulting absolute executable path:

```toml
[vendored_language_tool]
stdio_path = "/absolute/path/to/polis/third_party/languagetool-pl/scripts/run_stdio.sh"
timeout_seconds = 2.0
```

Use the analyzer as a context manager so its one persistent local child process
is stopped deterministically:

```python
from polis import Analyzer

with Analyzer.from_config("polis.toml") as analyzer:
    result = analyzer.correct("Wiem że wróciła.")

assert result.corrected_text == "Wiem, że wróciła."
```

`Analyzer.close()` provides the equivalent explicit shutdown. Source-policy
`1.1` automatically applies only the five qualified comma rules. Contextual
inflection remains reviewable and requires `apply_suggestions()`. Removing
`[vendored_language_tool]` disables this process-backed path completely.

## Development setup

The distribution is named `polis-nlp`; its Python import namespace is `polis`.
Polis requires Python 3.12 or newer and uv 0.11.2 exactly. Install that uv
release on macOS or Linux:

```console
curl -LsSf https://astral.sh/uv/0.11.2/install.sh | sh
```

On Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/0.11.2/install.ps1 | iex"
```

Confirm that `uv --version` reports `uv 0.11.2`, then reproduce the locked
development environment:

```console
uv sync --locked --extra dev
```

Run every check through the same locked environment:

```console
uv run --locked --extra dev pytest -m "not slow and not model"
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
uv run --locked --extra dev python -m build --no-isolation
```

As an additional local compatibility gate, outside fast CI, the standard-library
runner can be invoked separately:

```console
uv run --locked --extra dev python -m unittest discover -s tests -v
```

`uv.lock` pins the complete build and development dependency graph. Use
`uv lock --check` to verify that it agrees with `pyproject.toml`; intentionally
update it with `uv lock` whenever declared dependencies change.

## Continuous integration

Every push and pull request runs the fast quality suite on the representative
ADR-0001 matrix: Ubuntu x86_64 with CPython 3.12, 3.13, and 3.14; macOS arm64
with 3.12 and 3.14; and Windows x86_64 with 3.12 and 3.14. It reproduces the
locked development environment. The workflow maps policy name `x86_64` to the
`setup-python` input `x64` and passes `arm64` through unchanged. It runs pytest
with the fast marker selection, Ruff lint and format checks, strict mypy, and
builds and inspects both distribution artifacts for MIT license metadata and
`LICENSE` inclusion. Pytest also collects tests written as `unittest.TestCase`,
so a second unfiltered test invocation is intentionally absent.

This fast suite deliberately excludes slow tests, real-model tests, benchmarks,
release publishing, and any network-dependent product checks. Those workloads
require their own explicit jobs and remain outside the per-change gate. Mark
resource-intensive pytest cases with `@pytest.mark.slow` and tests requiring a
real local model with `@pytest.mark.model`; the local command above reproduces
CI's exact marker selection.

## Public models

Polis currently provides immutable analysis result models, deterministic,
strictly versioned JSON serialization, and runtime protocols for future
deterministic analyzers and local generation backends. The
[public analysis model contract](docs/public-api.md) documents field semantics,
[offline verification guide](docs/offline-operation.md),
Unicode offset rules, validation failures, and schema compatibility. The
 [quick start guide](docs/quick-start.md), [privacy guide](docs/privacy.md), and
[limitations](docs/limitations.md) explain current behavior and boundaries.
[compatibility and semver policy](docs/compatibility.md).
[privacy and dependency audit](docs/privacy-audit.md) documents release-gate evidence.
[Prerelease candidate checklist](docs/prerelease-candidate.md) documents the release-gate
verification path.
[Distribution verification](docs/distribution-verification.md) documents the
build-once release identity and post-publication digest checks. The append-only
[0.1.0 erratum](docs/release-notes/0.1.0-erratum.md) corrects published asset
digest evidence without rewriting that release.
The [protocol boundary](docs/architecture/protocols.md) documents how richer
orchestrators and adapter variants should be wired around the stable contracts.
[Changelog](CHANGELOG.md) tracks release history and [release notes](docs/release-notes/0.1.0.md)
document current support boundaries.

## Command-line interface

Polis also ships a thin CLI for manual or scripted analysis:

```console
python -m polis.cli analyze --json "Witaj,świecie."   # text argument
printf 'Witaj,świecie.\n' | python -m polis.cli analyze --stdin --json  # stdin input
python -m polis.cli analyze --file input.txt --json      # UTF-8 file input
```

Useful options:

- `--category`: repeatable finding category filter
- `--minimum-confidence`: minimum confidence threshold
- `--apply <finding-id> ...`: apply selected findings
- `--json`: emit structured JSON output
- For extension points and custom adapters, see [Customization guide](docs/customization.md).

Exit behavior:

- `0`: command succeeded
- `1`: analysis was valid but no applied selection could be executed
- `2`: configuration/input parsing failed in CLI validation

Privacy notes:

- Input text is not logged to error output and does not leave the process by
default.
- Validation and runtime errors are reported using operation-level codes and
safe context only.

## Evaluation data

The initial licensed Polish gold set is versioned with the package and checked
by a strict standard-library validator. Its schema, CC0 provenance, hard
negatives, and contribution rules are documented in
[the evaluation dataset guide](docs/evaluation-dataset.md).

## Dependency groups

The default installation has no production dependencies. The `dev` extra is
only for local development and includes the following permissively licensed
tools, each permitted by ADR-0001:

| Dependency | Minimum version | Purpose | License rationale |
| --- | --- | --- | --- |
| `build` | 1.3.0 | Build wheel and source-distribution artifacts. | MIT is on the approved allowlist. |
| `hatchling` | 1.27.0 | Build backend used from the locked environment. | MIT is on the approved allowlist. |
| `mypy` | 2.3.0 | Run strict static type checks. | MIT is on the approved allowlist. |
| `packaging` | 26.2 | Parse and compare PEP 440 release identities in developer-only release tooling. | Apache-2.0 OR BSD-2-Clause is on the approved allowlist. |
| `pytest` | 9.0.0 | Run the test suite. | MIT is on the approved allowlist. |
| `ruff` | 0.15.0 | Lint and format Python files. | MIT is on the approved allowlist. |

The build backend is `hatchling` 1.27.0 or newer. This lower bound is the first
Hatchling release with PEP 639 `license` and `license-files` support; Hatchling
is MIT-licensed and therefore approved by ADR-0001. The complete locked
transitive graph and its adoption decisions are recorded in the
[dependency-license review](docs/development/dependency-licenses.md).
