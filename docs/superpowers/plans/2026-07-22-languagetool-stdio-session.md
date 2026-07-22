# Vendored LanguageTool Stdio Session Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect one persistent vendored LanguageTool 6.8 stdio process to both punctuation and contextual-inflection rules for repeated Polish sentence analysis.

**Architecture:** A bounded cross-platform `LocalLanguageToolStdioSession` owns one lazily started child process and implements both existing transport protocols. `AnalyzerConfig` exposes one mutually exclusive vendored mode, while `Analyzer` owns and closes only sessions it constructs. Existing HTTP punctuation and standalone contextual stdio paths remain compatible.

**Tech Stack:** Python 3.12+, standard-library `subprocess`, `queue`, `threading`, JSON, pytest, Ruff, mypy, OpenJDK 17, vendored LanguageTool 6.8.

## Global Constraints

- Process exactly one Polish sentence at a time; paragraph evaluation is outside #77.
- Never invoke a shell, download an artifact, access a public endpoint, or include analyzed text in diagnostics.
- Keep source-policy version `1.1` unchanged.
- Punctuation findings remain automatic; contextual-inflection findings remain reviewable.
- Preserve existing HTTP and standalone contextual configuration behavior.
- Add no Python production dependency and package no Java artifact.
- Use original Unicode code-point half-open `[start, end)` offsets.
- Paweł Cyroń is the only credited author; add no automation attribution.
- Keep all #77 changes in one focused commit, as required by `AGENTS.md`.

---

### Task 1: Freeze configuration and ownership behavior

**Files:**
- Modify: `src/polis/analyzer.py`
- Modify: `tests/test_analyzer_languagetool_config.py`
- Modify: `tests/typecheck/stubs/polis/__init__.pyi`

**Interfaces:**
- Consumes: existing `AnalyzerConfig.from_toml(path)` and `ConfigurationError`.
- Produces: `AnalyzerConfig.vendored_language_tool_stdio_path`, `AnalyzerConfig.vendored_language_tool_timeout_seconds`, and validated TOML `[vendored_language_tool]`.

- [ ] **Step 1: Write failing constructor and TOML tests**

```python
def test_vendored_stdio_configuration_requires_one_absolute_executable(
    tmp_path: Path,
) -> None:
    runner = tmp_path / "run_stdio.sh"
    runner.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    runner.chmod(0o700)
    path = _config_file(
        tmp_path,
        "[vendored_language_tool]\n"
        f'stdio_path = "{runner}"\n'
        "timeout_seconds = 2.0\n",
    )

    config = AnalyzerConfig.from_toml(path)

    assert config.vendored_language_tool_stdio_path == str(runner)
    assert config.vendored_language_tool_timeout_seconds == 2.0
```

Add parameterized failures for a relative path, missing executable, non-positive
timeout, simultaneous `language_tool_url`, and simultaneous
`contextual_inflection_stdio_path`.

- [ ] **Step 2: Run the focused tests and confirm RED**

Run: `.venv/bin/pytest -q tests/test_analyzer_languagetool_config.py -k vendored`

Expected: failures because the config fields and TOML section do not exist.

- [ ] **Step 3: Add the minimal validated fields and TOML parsing**

Add fields with these exact defaults:

```python
vendored_language_tool_stdio_path: str | None = None
vendored_language_tool_timeout_seconds: float = 2.0
```

In `__post_init__`, validate the timeout with
`ContextualInflectionRuleConfig`, validate a configured path with the new
session path validator from Task 2 once available, and reject competing modes:

```python
configured_modes = sum(
    value is not None
    for value in (
        self.language_tool_url,
        self.contextual_inflection_stdio_path,
        self.vendored_language_tool_stdio_path,
    )
)
if self.vendored_language_tool_stdio_path is not None and configured_modes != 1:
    raise ValueError("vendored LanguageTool stdio mode is mutually exclusive")
```

Parse exactly `stdio_path` and optional `timeout_seconds` from
`[vendored_language_tool]`; reject an absent required path and non-mapping
section through the existing controlled configuration conversion.

- [ ] **Step 4: Update the public type stub and verify GREEN**

Add the two constructor fields and `close`, `__enter__`, and `__exit__` methods
to `tests/typecheck/stubs/polis/__init__.pyi`, then run:

`.venv/bin/pytest -q tests/test_analyzer_languagetool_config.py && .venv/bin/mypy src/polis/analyzer.py`

Expected: all selected tests pass and mypy reports no issues.

---

### Task 2: Implement the bounded persistent stdio transport

**Files:**
- Create: `src/polis/rules/languagetool_stdio.py`
- Modify: `src/polis/rules/__init__.py`
- Create: `tests/fixtures/fake_languagetool_stdio.py`
- Create: `tests/test_languagetool_stdio_session.py`

**Interfaces:**
- Consumes: `LanguageToolTransport.check()` and `ContextMorphologyTransport.synthesize_context()` protocols.
- Produces: `LocalLanguageToolStdioSession.from_executable(path, timeout_seconds)`, both protocol methods, `close()`, and context-manager methods.

- [ ] **Step 1: Write failing public-contract and lazy-reuse tests**

The fake server increments `process_sequence` once at startup and
`request_sequence` per input record. It returns compatible LanguageTool metadata
for check requests and a minimal valid `synthesize_context` object for synthesis.

```python
def test_session_starts_lazily_and_reuses_one_process(fake_command: tuple[str, ...]) -> None:
    session = LocalLanguageToolStdioSession(fake_command, timeout_seconds=1.0)
    assert session.process_start_count == 0

    first = session.check("To jest test.", language="pl-PL", timeout_seconds=1.0)
    second = session.check("Wiem że wróci.", language="pl-PL", timeout_seconds=1.0)

    assert session.process_start_count == 1
    assert first["process_sequence"] == second["process_sequence"] == 1
    assert second["request_sequence"] == first["request_sequence"] + 1
    session.close()
```

Add independent failing tests for synthesis shape, serialized calls from two
threads, invalid language, request larger than `65_536` bytes, response larger
than `1_048_576` bytes, invalid UTF-8, invalid JSON, non-object JSON, timeout,
EOF, broken pipe, use after close, and idempotent close.

- [ ] **Step 2: Run the session tests and confirm RED**

Run: `.venv/bin/pytest -q tests/test_languagetool_stdio_session.py`

Expected: import failure because `languagetool_stdio.py` does not exist.

- [ ] **Step 3: Implement session state and bounded reader**

Use these constants and state fields:

```python
_MAX_REQUEST_BYTES = 65_536
_MAX_RESPONSE_BYTES = 1_048_576
_EOF = object()

self._command: tuple[str, ...]
self._default_timeout_seconds: float
self._process: subprocess.Popen[bytes] | None = None
self._responses: queue.Queue[bytes | object] = queue.Queue(maxsize=1)
self._exchange_lock = threading.Lock()
self._closed = False
self._broken = False
self.process_start_count = 0
```

Start with `shell=False`, binary pipes, `stderr=subprocess.DEVNULL`, and no
environment mutation. The daemon reader performs:

```python
raw = stdout.readline(_MAX_RESPONSE_BYTES + 1)
if not raw:
    responses.put(_EOF)
    return
responses.put(raw)
```

On timeout or protocol failure, mark broken and terminate the process before
raising a generic exception. Never include request or response contents in an
exception.

- [ ] **Step 4: Implement both protocol methods**

`check()` writes:

```python
{"language": "pl-PL", "text": text}
```

`synthesize_context()` writes:

```python
{
    "operation": "synthesize_context",
    "language": "pl-PL",
    "text": text,
    "spans": [{"start": start, "end": end} for start, end in spans],
}
```

Decode strict UTF-8, parse JSON, require a mapping, and return a typed mapping.

- [ ] **Step 5: Verify GREEN and refactor without changing behavior**

Run:

`.venv/bin/pytest -q tests/test_languagetool_stdio_session.py && .venv/bin/ruff check src/polis/rules/languagetool_stdio.py tests/test_languagetool_stdio_session.py && .venv/bin/mypy src/polis/rules/languagetool_stdio.py`

Expected: all checks pass.

---

### Task 3: Wire one owned session into both sentence rules

**Files:**
- Modify: `src/polis/analyzer.py`
- Modify: `tests/test_analyzer_languagetool_config.py`
- Modify: `tests/test_contextual_inflection_rule.py`
- Modify: `tests/test_conservative_correction.py`

**Interfaces:**
- Consumes: `LocalLanguageToolStdioSession`, existing rule transports, and source-policy `1.1`.
- Produces: one shared registry transport, explicit owned lifecycle, and unchanged injected-transport ownership.

- [ ] **Step 1: Add failing integration and lifecycle tests**

```python
def test_vendored_session_serves_automatic_and_reviewable_sources(
    fake_shared_transport: FakeSharedTransport,
) -> None:
    analyzer = Analyzer(
        AnalyzerConfig(),
        language_tool_transport=fake_shared_transport,
        contextual_inflection_transport=fake_shared_transport,
    )

    punctuation = analyzer.correct("Wiem że wróciła.")
    inflection = analyzer.correct("Rozmawiałem z Janem Nowak po przerwie.")

    assert punctuation.corrected_text == "Wiem, że wróciła."
    assert str(punctuation.applied_findings[0].source) == "rule:languagetool.pl"
    assert inflection.corrected_text == inflection.original_text
    assert str(inflection.skipped_findings[0].source) == (
        "rule:languagetool.contextual_inflection"
    )
```

Add tests that an owned fake session is closed exactly once by context-manager
exit, an injected transport is not closed, built-in spelling survives a broken
session, and two analyzer calls share the same owned object.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `.venv/bin/pytest -q tests/test_analyzer_languagetool_config.py tests/test_contextual_inflection_rule.py tests/test_conservative_correction.py -k 'vendored or ownership or shared'`

Expected: failures because analyzer wiring and lifecycle are absent.

- [ ] **Step 3: Extend analyzer injection and registry construction**

Add the optional constructor parameter:

```python
language_tool_transport: LanguageToolTransport | None = None
```

When vendored config is present, construct one owned session and assign it to
both local variables before `_make_default_registry()`. Change the helper to:

```python
def _make_default_registry(
    config: AnalyzerConfig,
    language_tool_transport: LanguageToolTransport | None = None,
    contextual_inflection_transport: ContextMorphologyTransport | None = None,
) -> DeterministicRuleRegistry:
```

Register `LocalLanguageToolRule` whenever URL mode or a punctuation transport is
present. Register `ContextualInflectionRule` whenever a contextual transport is
present. Do not construct a second process in vendored mode.

- [ ] **Step 4: Add owned close and context management**

```python
def close(self) -> None:
    if self._owned_language_tool_session is not None:
        self._owned_language_tool_session.close()

def __enter__(self) -> Analyzer:
    return self

def __exit__(self, *args: object) -> None:
    self.close()
```

Ensure injected transports are never stored as owned. Verify source-policy
version remains exactly `1.1` and no new source enters `_AUTOMATIC_CORRECTION_POLICY`.

- [ ] **Step 5: Run all analyzer and rule tests**

Run:

`.venv/bin/pytest -q tests/test_analyzer_languagetool_config.py tests/test_languagetool_rule.py tests/test_contextual_inflection_rule.py tests/test_conservative_correction.py tests/test_suggestion_outcomes.py`

Expected: all tests pass.

---

### Task 4: Benchmark the real persistent vendored process

**Files:**
- Create: `experiments/languagetool_stdio_session/__init__.py`
- Create: `experiments/languagetool_stdio_session/config.json`
- Create: `experiments/languagetool_stdio_session/run_benchmark.py`
- Create: `experiments/languagetool_stdio_session/report.json`
- Create: `experiments/languagetool_stdio_session/README.md`
- Modify: `tests/test_languagetool_vendor_runtime.py`
- Create: `tests/test_languagetool_stdio_benchmark.py`

**Interfaces:**
- Consumes: corpus-v3 development sentences, installed analyzer behavior, pinned vendored runner.
- Produces: privacy-safe deterministic report and pass/fail decision for latency, memory, reuse, swap, and sockets.

- [ ] **Step 1: Write failing benchmark contract tests**

Require config schema 1, corpus and artifact hashes, `69` sentence development
cases, one warmup pass plus two measured passes, `500 ms` warm p95, `1 GiB`
combined RSS, zero swap growth, exactly one process start, and no raw text keys.

```python
def test_report_proves_one_process_and_repeatable_findings() -> None:
    report = load_report(REPORT)
    assert report["summary"]["process_start_count"] == 1
    assert report["summary"]["repeatable_case_count"] == 69
    assert report["summary"]["socket_count"] == 0
    assert report["decision"]["qualified"] is True
```

- [ ] **Step 2: Confirm RED**

Run: `.venv/bin/pytest -q tests/test_languagetool_stdio_benchmark.py`

Expected: failure because the experiment package and report do not exist.

- [ ] **Step 3: Implement the source-only benchmark**

Load only development sentence cases. Use one analyzer in a context manager.
Hash normalized finding records for repeatability, but include only case ID,
finding count, hash, latency, and input character count in evidence. Measure RSS
with `ps -o rss=`, swap before/after with `sysctl vm.swapusage` on macOS, and
socket count with `lsof -nP -a -p PID -i` when available. If a required target
measurement is unavailable, fail the qualification rather than inventing zero.

- [ ] **Step 4: Add opt-in real integration assertions**

Extend `tests/test_languagetool_vendor_runtime.py` under
`POLIS_LT_VENDOR_INTEGRATION=1` to assert one process handles punctuation then
context synthesis, findings keep their policy channels, no socket is open, and
context exit terminates the process.

- [ ] **Step 5: Run and record the real benchmark**

Run:

```console
POLIS_LT_VENDOR_INTEGRATION=1 .venv/bin/python -m experiments.languagetool_stdio_session.run_benchmark \
  --config experiments/languagetool_stdio_session/config.json \
  --output experiments/languagetool_stdio_session/report.json
```

Expected: a privacy-safe qualified report or a measured failed gate. If a gate
fails, open a focused follow-up issue and do not weaken the frozen threshold.

---

### Task 5: Document public operation and removal

**Files:**
- Modify: `README.md`
- Modify: `examples/polis.toml`
- Modify: `docs/customization.md`
- Modify: `docs/offline-operation.md`
- Modify: `docs/public-api.md`
- Modify: `docs/privacy.md`
- Modify: `docs/performance-baseline.md`
- Modify: `docs/limitations.md`
- Modify: `docs/project/ROADMAP.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: verified config and benchmark report.
- Produces: exact sentence-only setup, lifecycle, performance, privacy, and removal documentation.

- [ ] **Step 1: Add documentation contract assertions**

Extend the most relevant existing documentation test to require the literal
section name `[vendored_language_tool]`, `stdio_path`, `Analyzer.close()`,
sentence-only wording, source-policy `1.1`, and the measured report values.

- [ ] **Step 2: Confirm the documentation test fails**

Run the selected test directly and verify it fails on missing new text.

- [ ] **Step 3: Update documentation from measured evidence**

Document the context-manager example, explicit build prerequisite, no implicit
downloads, one persistent child process, automatic versus reviewable sources,
timeouts, clean shutdown, removal by deleting the TOML section, absence from
wheel/sdist, exact measured latency/RSS, and sentence-only limitation. Do not
claim general grammar, model, or paragraph support.

- [ ] **Step 4: Verify documentation and package boundaries**

Run documentation tests plus:

`rg -n 'vendored_language_tool|Analyzer.close|source-policy.*1.1' README.md examples docs`

Expected: all statements agree with the implemented configuration and report.

---

### Task 6: Complete issue verification and publish one focused commit

**Files:**
- All #77 files above.

**Interfaces:**
- Consumes: complete implementation and evidence.
- Produces: verified commit on `main`, updated and closed #77, unblocked #76.

- [ ] **Step 1: Run fresh static and complete test verification**

```console
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy .
.venv/bin/pytest
```

Expected: Ruff and mypy report zero errors; pytest reports zero failures with
only documented optional skips.

- [ ] **Step 2: Run real vendored, offline, and distribution gates**

```console
POLIS_LT_VENDOR_INTEGRATION=1 .venv/bin/pytest -q tests/test_languagetool_vendor_runtime.py
.venv/bin/pytest -q tests/test_offline_verification.py
.venv/bin/python -m build --no-isolation --outdir /tmp/polis-issue77-dist
.venv/bin/python scripts/verify_distribution_artifacts.py --dist /tmp/polis-issue77-dist
.venv/bin/python scripts/verify_distribution_install.py --dist /tmp/polis-issue77-dist
```

Expected: every command exits zero, and artifacts contain no Java build product
or optional dependency.

- [ ] **Step 3: Audit requirements, attribution, and diff**

Check every #77 acceptance item against test output or the report. Run
`git diff --check`, inspect all changed files, and search the change set for
co-author trailers, generation disclosures, model weights, caches, private
text, and unexpected artifacts.

- [ ] **Step 4: Create the single issue commit and push**

```console
git add CHANGELOG.md README.md examples/polis.toml \
  docs/customization.md docs/limitations.md docs/offline-operation.md \
  docs/performance-baseline.md docs/privacy.md docs/project/ROADMAP.md \
  docs/public-api.md \
  docs/superpowers/specs/2026-07-22-languagetool-stdio-session-design.md \
  docs/superpowers/plans/2026-07-22-languagetool-stdio-session.md \
  experiments/languagetool_stdio_session \
  src/polis/analyzer.py src/polis/rules/__init__.py \
  src/polis/rules/languagetool_stdio.py \
  tests/fixtures/fake_languagetool_stdio.py \
  tests/test_analyzer_languagetool_config.py \
  tests/test_contextual_inflection_rule.py \
  tests/test_conservative_correction.py \
  tests/test_languagetool_stdio_benchmark.py \
  tests/test_languagetool_stdio_session.py \
  tests/test_languagetool_vendor_runtime.py \
  tests/typecheck/stubs/polis/__init__.pyi
git commit -m "feat: integrate vendored LanguageTool stdio session (#77)"
git push origin main
```

- [ ] **Step 5: Close #77 only after remote verification**

Update every acceptance checkbox with measured evidence, comment with commit,
commands, results, known limitations, and next action, then close #77. Remove
`status:blocked` from #76 and make #77 an explicit dependency before resuming
the installed-package sentence release gate.
