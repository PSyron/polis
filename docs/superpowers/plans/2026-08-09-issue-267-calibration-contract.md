# Per-Key Calibration Contract and Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zbudować repository-only kontrakt i runner syntetycznej kalibracji dla 20 dokładnych kluczy polityki, bez tworzenia rzeczywistego zbioru, podpisanego wyboru progów ani holdoutu.

**Architecture:** Nowe moduły `calibration_*` pozostają prywatną warstwą `polis.evaluation`, korzystają z finalnego `Analyzer` wyłącznie przez wstrzykiwany callable i nigdy nie trafiają do wheel ani sdist. Kontrakt najpierw wiąże zamrożony snapshot 20×7 oraz reviewed manifest, następnie runner wykonuje jeden warm-up i pięć mierzonych powtórzeń, a raport rozstrzyga każdy exact key osobno przy globalnym fail-closed dla integralności, prywatności i deterministyczności.

**Tech Stack:** Python 3.12+, dataclasses, standard-library JSON/SHA-256, istniejące `polis.core.Finding`, pytest, Ruff, mypy, Hatch/uv.

## Global Constraints

- Issue: `#267`; parent: `#236`; decision source: merged `#265`.
- Dataset ID: `polis-a-b-calibration-v2-v1`; experiment ID: `polis-a-b-qualification-v2-v1`.
- Snapshot SHA-256: `92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92`.
- Snapshot row order: `[source, category, operation, behavior_version, source_policy_version, emitted_confidence, current_policy_state]`.
- Candidate threshold is exactly `emitted_confidence` or `none`; no grid search, rounding, or rule-confidence mutation.
- Minimum denominator per key: 20 `error` and 40 `correct`; one case counts for exactly one `primary_source_identity`.
- Protocol: one warm-up plus five measured repetitions; all five finding hashes must be identical.
- Profile: `active-baseline-v1`; per-key minimums are precision `1.0`, recall `0.7142857142857143`, F1 `0.8333333333333334`, span accuracy `0.7142857142857143`, correction accuracy `1.0`, false-alarm rate `0.0`.
- No real dataset, real calibration, threshold signature, marker, authorization, holdout, policy edit, runtime dependency, or product API change.
- Do not read, rerun, modify, or derive data from `experiments/a-b-one-shot/**` beyond the already public source-identity metadata frozen by #265.
- All `calibration_*.py`, `polis.evaluation.__main__`, configs, reports, datasets and experiment paths are repository-only and excluded from wheel/sdist.
- Maintained documentation is Polish; code, identifiers, schemas and CLI flags are English.
- One issue produces one focused final commit. Intermediate tasks create RED/GREEN evidence but do not commit separately.

---

## File Structure

- `src/polis/evaluation/calibration_models.py`: immutable types, enums and typed errors shared by the calibration modules.
- `src/polis/evaluation/calibration_sources.py`: exact 20×7 snapshot, canonical serialization, digest and live first-five-field drift validation.
- `src/polis/evaluation/calibration_contract.py`: strict config, threshold-profile and reviewed-manifest parsing.
- `src/polis/evaluation/calibration_dataset.py`: strict dataset/case parsing, Unicode range validation, provenance/review and 20+40 denominator checks.
- `src/polis/evaluation/calibration_scoring.py`: exact per-key matching, metrics and `candidate`/`fail_threshold`/`insufficient_evidence` outcomes.
- `src/polis/evaluation/calibration_report.py`: privacy-safe raw/normalized reports, canonical rebuild and threshold-selection candidate.
- `src/polis/evaluation/calibration_runner.py`: warm-up, five repetitions, deterministic hashes, global gates and file orchestration.
- `src/polis/evaluation/__main__.py`: source-checkout-only `run-calibration --config` dispatch next to the existing holdout command.
- `tests/calibration_test_helpers.py`: typed synthetic 20-key config/dataset/finding factories; no production constants duplicated outside assertions.
- `tests/test_calibration_sources.py`: snapshot order/digest/drift tests.
- `tests/test_calibration_contract.py`: strict schema, types, thresholds, manifest and canonical JSON tests.
- `tests/test_calibration_dataset.py`: roles, offsets, uniqueness, review/provenance and denominator boundaries.
- `tests/test_calibration_scoring.py`: per-key counts, metrics, exact threshold candidate and local verdicts.
- `tests/test_calibration_report.py`: privacy allowlist, finite values, normalization and byte-identical rebuild.
- `tests/test_calibration_runner.py`: warm-up/repetition ordering, nondeterminism, global failure and offline synthetic execution.
- `tests/test_calibration_module_cli.py`: source-checkout CLI and forbidden override tests.
- `pyproject.toml`: anchored wheel/sdist excludes for `/src/polis/evaluation/calibration_*.py`.
- `tests/test_distribution_artifacts.py`: built wheel/sdist absence assertions for the calibration surface.
- `docs/evaluation-dataset.md`: Polish description of repeatable, non-authorizing synthetic calibration tooling.
- `docs/project/documentation-migration-inventory.json`: exact historical-plan inventory entry.

## Task 1: Freeze the exact source snapshot

**Files:**
- Create: `tests/test_calibration_sources.py`
- Create: `src/polis/evaluation/calibration_models.py`
- Create: `src/polis/evaluation/calibration_sources.py`

**Interfaces:**
- Produces: `CalibrationSourceIdentity`, `CalibrationContractError`, `SOURCE_ROWS`, `SOURCE_SNAPSHOT_SHA256`, `canonical_source_bytes()`, `validate_live_sources()`.
- Consumes: `polis.evaluation.holdout_sources.current_sources` only for the current five-field runtime snapshot; no holdout dataset/report access.

- [ ] **Step 1: Write the RED snapshot contract**

```python
def test_source_snapshot_is_the_approved_ordered_20_by_7_contract() -> None:
    assert len(SOURCE_ROWS) == 20
    assert all(len(row) == 7 for row in SOURCE_ROWS)
    assert hashlib.sha256(canonical_source_bytes()).hexdigest() == (
        "92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92"
    )
    assert sum(row.current_policy_state == "automatic" for row in SOURCE_ROWS) == 8
    assert sum(row.current_policy_state == "review-only" for row in SOURCE_ROWS) == 12
```

Add parameterized RED cases for a missing row, duplicate row, reordering, category/operation/behavior/policy drift, confidence drift, state drift, `True`, `NaN` and infinity. Each calls `parse_source_rows(value)` and expects `CalibrationContractError`.

- [ ] **Step 2: Run RED and capture the controlled absent-feature failure**

Run: `uv run --locked --extra dev pytest tests/test_calibration_sources.py -q`

Expected: collection succeeds, then the test helper converts the missing module
into one explicit assertion failure `planned calibration sources module is
absent`; save the command, exit code and output under
`.omo/evidence/issue-267/task-1-red.txt`.

- [ ] **Step 3: Add immutable typed rows and canonical digest**

```python
@dataclass(frozen=True, slots=True)
class CalibrationSourceIdentity:
    source: str
    category: str
    operation: str
    behavior_version: str
    source_policy_version: str
    emitted_confidence: float
    current_policy_state: Literal["automatic", "review-only"]


def canonical_source_bytes(rows: tuple[CalibrationSourceIdentity, ...] = SOURCE_ROWS) -> bytes:
    payload = [
        [
            row.source,
            row.category,
            row.operation,
            row.behavior_version,
            row.source_policy_version,
            row.emitted_confidence,
            row.current_policy_state,
        ]
        for row in rows
    ]
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()
```

Define all 20 rows literally from the approved spec. `validate_live_sources()` compares the first five fields to `current_sources()` and rejects any exception or mismatch as `CalibrationContractError`; confidence and current policy state remain frozen contract fields and are checked again from observed findings/policy in later tasks.

- [ ] **Step 4: Run GREEN and static checks**

Run: `uv run --locked --extra dev pytest tests/test_calibration_sources.py -q`

Run: `uv run --locked --extra dev ruff check src/polis/evaluation/calibration_models.py src/polis/evaluation/calibration_sources.py tests/test_calibration_sources.py && uv run --locked --extra dev mypy src/polis/evaluation/calibration_models.py src/polis/evaluation/calibration_sources.py tests/test_calibration_sources.py`

Expected: all exit 0 and the canonical digest is exactly
`92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92`.

- [ ] **Step 5: Record the task checkpoint without committing**

Save RED/GREEN/static transcripts and `git diff --check` to `.omo/evidence/issue-267/task-1-*`. Do not commit; #267 receives one final commit after Task 6.

## Task 2: Parse strict config, reviewed manifest and calibration dataset

**Files:**
- Create: `tests/calibration_test_helpers.py`
- Create: `tests/test_calibration_contract.py`
- Create: `tests/test_calibration_dataset.py`
- Create: `src/polis/evaluation/calibration_contract.py`
- Create: `src/polis/evaluation/calibration_dataset.py`
- Modify: `src/polis/evaluation/calibration_models.py`

**Interfaces:**
- Produces: `CalibrationConfig`, `CalibrationThresholds`, `CalibrationManifest`, `CalibrationCase`, `CalibrationDataset`, `ExpectedFinding`, `parse_calibration_config(bytes)`, `parse_calibration_manifest(bytes)`, `load_calibration_dataset_bytes(bytes, manifest, config)`.
- Consumes: `SOURCE_ROWS`, `SOURCE_SNAPSHOT_SHA256`, canonical JSON helper local to the calibration contract.

- [ ] **Step 1: Write RED strict-schema tests**

Use a typed helper that generates 20 keys × (20 error + 40 correct) cases in
memory. It serializes rows without duplicating constants:

```python
def source_rows_json() -> list[list[str | float]]:
    return [
        [
            row.source,
            row.category,
            row.operation,
            row.behavior_version,
            row.source_policy_version,
            row.emitted_confidence,
            row.current_policy_state,
        ]
        for row in SOURCE_ROWS
    ]
```

Freeze config fields:

```python
{
  "schema_id": "polis.a-b-calibration.config",
  "schema_version": 1,
  "experiment_id": "polis-a-b-qualification-v2-v1",
  "dataset_id": "polis-a-b-calibration-v2-v1",
  "source_snapshot_sha256": "92717cdeb73445bc0add5eadc6f3ab1b4569a792168c9e1a08cc182eac481b92",
  "source_rows": source_rows_json(),
  "threshold_profile": "active-baseline-v1",
  "thresholds": {
    "precision": 1.0,
    "recall": 0.7142857142857143,
    "f1": 0.8333333333333334,
    "exact_span_accuracy": 0.7142857142857143,
    "exact_correction_accuracy": 1.0,
    "correct_sentence_false_alarm_rate": 0.0
  },
  "warmup_repetitions": 1,
  "measured_repetitions": 5,
  "minimum_error_cases_per_key": 20,
  "minimum_correct_cases_per_key": 40,
  "paths": {
    "dataset": ".omo/sealed/a-b-calibration-v2-v1/cases.json",
    "manifest": "experiments/a-b-qualification-v2/calibration.dataset.manifest.json",
    "raw_report": "experiments/a-b-qualification-v2/calibration.report.json",
    "normalized_report": "experiments/a-b-qualification-v2/calibration.normalized-report.json",
    "threshold_selection": "experiments/a-b-qualification-v2/threshold-selection.json"
  }
}
```

Add one test per unknown/missing field, wrong schema/ID, noncanonical JSON, non-finite number, `bool` used as integer, snapshot mismatch, path escape/absolute path and repetition/minimum override.

For manifest/dataset, assert exact schema, CC0-1.0, public provenance, `review_status=approved`, `reviewed_case_count == case_count`, canonical digest/size, unique IDs, one primary source, Unicode `[start,end)` surface match, and roles exactly `error` or `correct`.

- [ ] **Step 2: Run RED**

Run: `uv run --locked --extra dev pytest tests/test_calibration_contract.py tests/test_calibration_dataset.py -q`

Expected: failures identify absent parsers and types, not malformed fixtures.

- [ ] **Step 3: Implement closed dataclasses and parsers**

```python
@dataclass(frozen=True, slots=True)
class CalibrationConfig:
    experiment_id: str
    dataset_id: str
    source_rows: tuple[CalibrationSourceIdentity, ...]
    threshold_profile: str
    thresholds: CalibrationThresholds
    warmup_repetitions: int
    measured_repetitions: int
    minimum_error_cases_per_key: int
    minimum_correct_cases_per_key: int
    paths: CalibrationPaths

@dataclass(frozen=True, slots=True)
class CalibrationCase:
    id: str
    role: Literal["error", "correct"]
    primary_source_identity: str
    text: str
    expected_findings: tuple[ExpectedFinding, ...]
```

Require `type(value) is int` for integer fields and `type(value) in (int, float) and math.isfinite(value)` for numeric fields. Re-encode every parsed root with canonical JSON plus LF and require byte equality before accepting it.

Compute denominator counts by `(primary_source_identity, role)`; reject 19/40, 20/39, unknown keys and any case counted more than once. Correct cases require zero expected findings; error cases require exactly one finding whose source equals the primary key.

- [ ] **Step 4: Run GREEN plus denominator boundary selection**

Run: `uv run --locked --extra dev pytest tests/test_calibration_contract.py tests/test_calibration_dataset.py -q`

Run: `uv run --locked --extra dev pytest tests/test_calibration_dataset.py -q -k 'minimum or duplicate or unicode or review or canonical'`

Expected: all pass; the second command executes real boundary cases, not an empty selection.

- [ ] **Step 5: Record checkpoint without committing**

Save tests, parser error samples and a 1200-case in-memory manifest summary. Confirm no `cases.json`, config, report or experiment file was created.

## Task 3: Compute independent per-key metrics and threshold candidates

**Files:**
- Create: `tests/test_calibration_scoring.py`
- Create: `src/polis/evaluation/calibration_scoring.py`
- Modify: `src/polis/evaluation/calibration_models.py`

**Interfaces:**
- Produces: `CalibrationCounts`, `CalibrationMetrics`, `KeyOutcome`, `score_calibration(dataset, findings_by_case, config)`.
- Consumes: parsed cases, the first measured repetition, exact `Finding` objects and frozen source rows.

- [ ] **Step 1: Write RED exact-matching and verdict tests**

```python
def test_each_key_receives_an_independent_candidate_at_emitted_confidence() -> None:
    outcomes = score_calibration(dataset, perfect_findings, config)
    assert len(outcomes) == 20
    assert all(item.verdict == "candidate" for item in outcomes)
    assert [item.minimum_confidence for item in outcomes] == [
        row.emitted_confidence for row in SOURCE_ROWS
    ]
```

Add cases where one source has one false positive, one missing expected finding, wrong span, wrong suggestion, missing emitted-confidence observation, multiple confidence values, confidence drift, or missing provider. Assert only that source becomes `fail_threshold` or `insufficient_evidence`; all others remain unchanged. A prediction from another source on a primary case is still charged to its own source, never hidden by the primary key.

- [ ] **Step 2: Run RED**

Run: `uv run --locked --extra dev pytest tests/test_calibration_scoring.py -q`

Expected: failures point to missing scoring implementation.

- [ ] **Step 3: Implement one-to-one matching and metrics**

```python
@dataclass(frozen=True, slots=True)
class KeyOutcome:
    identity: CalibrationSourceIdentity
    counts: CalibrationCounts
    metrics: CalibrationMetrics
    observed_confidence: float | None
    minimum_confidence: float | None
    verdict: Literal["candidate", "fail_threshold", "insufficient_evidence"]
```

Match exact source/category/span/original/suggestion once per expected finding. Count unmatched predictions as FP and unmatched gold as FN. Use `None`, not `0.0`, for undefined ratios. `candidate` requires complete 20/40 evidence, one finite observed confidence equal to the frozen emitted value, and every `active-baseline-v1` threshold. Complete data below a metric gives `fail_threshold`; missing/ambiguous confidence or unavailable provider gives `insufficient_evidence`.

- [ ] **Step 4: Run GREEN and mutation-focused tests**

Run: `uv run --locked --extra dev pytest tests/test_calibration_scoring.py -q`

Run: `uv run --locked --extra dev pytest tests/test_calibration_scoring.py -q -k 'false_positive or confidence or independent or undefined'`

Expected: all pass and exactly one key changes in every local-failure fixture.

- [ ] **Step 5: Record checkpoint without committing**

Store a privacy-safe 20-row synthetic outcome summary containing only IDs, counts, metrics, candidate values and verdicts.

## Task 4: Produce deterministic privacy-safe reports

**Files:**
- Create: `tests/test_calibration_report.py`
- Create: `src/polis/evaluation/calibration_report.py`
- Modify: `src/polis/evaluation/calibration_models.py`

**Interfaces:**
- Produces: `raw_report_bytes(result)`, `normalized_report_bytes(raw)`, `threshold_selection_bytes(result)`, `parse_raw_report(bytes)`.
- Consumes: `KeyOutcome`, run identities and the five repetition hashes.

- [ ] **Step 1: Write RED report/privacy tests**

Assert exact top-level allowlists and nested allowlists. Reject any accepted string containing the synthetic text sentinel, gold, original, suggestion, absolute workspace path, home path or PII sentinel. Parameterize `NaN`, `Infinity`, `-Infinity`, unknown fields and booleans masquerading as counts.

```python
def test_normalized_rebuild_is_byte_identical() -> None:
    first = normalized_report_bytes(parse_raw_report(raw_report_bytes(result)))
    second = normalized_report_bytes(parse_raw_report(first))
    assert second == first
    assert first.endswith(b"\n")
```

Threshold selection contains exactly the 20 frozen identities, emitted confidence, denominators, metrics and `candidate`/`fail_threshold`/`insufficient_evidence`; it is explicitly unsigned and non-authorizing in this issue.

- [ ] **Step 2: Run RED**

Run: `uv run --locked --extra dev pytest tests/test_calibration_report.py -q`

Expected: failures identify absent report API.

- [ ] **Step 3: Implement canonical allowlisted reports**

Serialize with UTF-8, sorted keys, compact separators, `allow_nan=False` and one LF. Raw report may contain finite timing/resource aggregates; normalized report removes them. Neither report contains case IDs or case-level data. Validate the generated object through the same strict parser before writing bytes.

- [ ] **Step 4: Run GREEN and privacy adversarial cases**

Run: `uv run --locked --extra dev pytest tests/test_calibration_report.py -q`

Run: `uv run --locked --extra dev pytest tests/test_calibration_report.py -q -k 'privacy or nonfinite or rebuild or unknown'`

Expected: all pass and every sentinel is absent from raw, normalized and threshold-selection bytes.

- [ ] **Step 5: Record checkpoint without committing**

Save hashes of three synthetic reports and the byte-identical rebuild proof; remove temporary report files.

## Task 5: Orchestrate one warm-up and five deterministic repetitions

**Files:**
- Create: `tests/test_calibration_runner.py`
- Create: `src/polis/evaluation/calibration_runner.py`
- Modify: `src/polis/evaluation/calibration_models.py`

**Interfaces:**
- Produces: `run_calibration(config_path: Path, *, analyzer_factory: Callable[[], AnalyzerCallable] | None = None) -> int` and pure `run_synthetic_calibration(config, manifest, dataset, analyzer) -> CalibrationRunResult`.
- Consumes: contract/dataset/scoring/report modules; production default creates the configured `Analyzer` only after config, manifest and source snapshot admission pass.

- [ ] **Step 1: Write RED lifecycle tests**

Use a call recorder to assert 1200 warm-up calls followed by exactly 6000 measured calls. Assert five identical hashes on stable output. Mutate only repetition 5 and require `CalibrationIntegrityError("calibration findings changed between measured repetitions")`, with no reports written.

Add pre-access tests proving malformed config, manifest digest drift, source drift and denominator failures call neither analyzer factory nor dataset analyzer. Add an analyzer exception and a socket guard; both must fail globally without a partial threshold selection.

- [ ] **Step 2: Run RED**

Run: `uv run --locked --extra dev pytest tests/test_calibration_runner.py -q`

Expected: failures identify missing lifecycle functions.

- [ ] **Step 3: Implement deterministic orchestration**

```python
def run_synthetic_calibration(
    config: CalibrationConfig,
    manifest: CalibrationManifest,
    dataset: CalibrationDataset,
    analyzer: Callable[[str], tuple[Finding, ...]],
) -> CalibrationRunResult:
    for _ in range(config.warmup_repetitions):
        for case in dataset.cases:
            analyzer(case.text)
    measured = tuple(_measure_once(dataset, analyzer) for _ in range(5))
    hashes = tuple(findings_sha256(dataset, findings) for findings in measured)
    if len(set(hashes)) != 1:
        raise CalibrationIntegrityError(
            "calibration findings changed between measured repetitions"
        )
    outcomes = score_calibration(dataset, measured[0], config)
    return CalibrationRunResult(
        repetition_hashes=hashes,
        outcomes=outcomes,
    )
```

`CalibrationRunResult` jest zamrożonym dataclass z polami
`repetition_hashes: tuple[str, ...]` oraz
`outcomes: tuple[KeyOutcome, ...]`.

File orchestration reads canonical config/manifest/dataset, validates all identities and digests, executes in memory, then writes each report with exclusive create and file plus parent-directory fsync. Existing outputs reject replacement; calibration is repeatable only through a new configured output directory before any signed selection exists.

- [ ] **Step 4: Run GREEN and offline manual driver**

Run: `uv run --locked --extra dev pytest tests/test_calibration_runner.py -q`

Run a minimal Python driver with `socket.socket.connect`, `connect_ex` and `socket.create_connection` patched to raise. Feed the synthetic 1200-case dataset and assert 20 outcomes, five equal hashes, zero network attempts and no plaintext in report bytes.

Expected: tests and driver exit 0.

- [ ] **Step 5: Record checkpoint without committing**

Store the lifecycle call counts, five hashes and socket-attempt count. Delete all temporary output directories.

## Task 6: Add source-checkout CLI, packaging boundary and documentation

**Files:**
- Create: `tests/test_calibration_module_cli.py`
- Modify: `src/polis/evaluation/__main__.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_distribution_artifacts.py`
- Modify: `docs/evaluation-dataset.md`
- Modify: `docs/project/documentation-migration-inventory.json`

**Interfaces:**
- Produces: `python -m polis.evaluation run-calibration --config <canonical-relative-path>` in a source checkout only.
- Preserves: existing `run-holdout` behavior and normal installed `polis` API/CLI.

- [ ] **Step 1: Write RED CLI and artifact-boundary tests**

Assert module help lists `run-calibration` and `run-holdout`. The calibration command accepts only `--config`; reject `--dataset`, `--source`, `--threshold`, `--repetitions`, `--output` and `--replace` before dispatch.

Build wheel and sdist in a temporary directory and assert no member matches:

```python
name == "polis/evaluation/__main__.py"
or name.startswith("polis/evaluation/calibration_")
or "/src/polis/evaluation/calibration_" in name
or "polis-a-b-calibration-v2-v1" in name
or "polis-a-b-qualification-v2-v1" in name
```

- [ ] **Step 2: Run RED**

Run: `uv run --locked --extra dev pytest tests/test_calibration_module_cli.py tests/test_distribution_artifacts.py -q`

Expected: CLI surface and calibration excludes fail before implementation; all existing holdout exclusions remain green.

- [ ] **Step 3: Implement CLI dispatch and anchored excludes**

Refactor `__main__.run()` to select the runner by parsed command without changing holdout error handling. Add exact anchored excludes to both Hatch targets:

```toml
"/src/polis/evaluation/calibration_*.py",
```

Do not add calibration modules to `EXPECTED_SOURCE_MEMBERS`; instead keep the expected packaged count at 45 and extend absence assertions. Document in Polish that #267 tooling is synthetic/repeatable/non-authorizing and repository-only; no real calibration dataset exists yet.

- [ ] **Step 4: Run full verification and manual surface QA**

Run:

```text
uv lock --check
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
uv run --locked --extra dev pytest tests/test_calibration_sources.py tests/test_calibration_contract.py tests/test_calibration_dataset.py tests/test_calibration_scoring.py tests/test_calibration_report.py tests/test_calibration_runner.py tests/test_calibration_module_cli.py -q
uv run --locked --extra dev pytest tests/test_distribution_artifacts.py tests/test_release_distribution_installation.py tests/test_evaluation_module_cli.py -q
uv run --locked --extra dev pytest -q -m "not research"
```

Build twice and require byte-identical wheel/sdist hashes. Install the wheel with `--no-deps` into a clean Python 3.12 environment; normal `python -m polis.cli analyze --json "To jest test."` must work, while `python -m polis.evaluation run-calibration --help` must fail because the repository-only module is absent.

- [ ] **Step 5: Self-review the complete issue against #265/#267**

Confirm all spec requirements assigned to #267 have a test, no placeholder remains, types/signatures match across tasks, protected #243 paths and `src/polis/correction/policy.py` have empty diffs, and no real dataset/config/report/threshold/marker exists.

- [ ] **Step 6: Create the one focused commit**

```text
git add src/polis/evaluation/calibration_*.py src/polis/evaluation/__main__.py tests/calibration_test_helpers.py tests/test_calibration_*.py tests/test_distribution_artifacts.py pyproject.toml docs/evaluation-dataset.md docs/project/documentation-migration-inventory.json docs/superpowers/plans/2026-08-09-issue-267-calibration-contract.md
git commit -m "feat(evaluation): add per-key calibration runner (#267)"
```

The commit author is Paweł Cyroń and contains no co-author or tool trailer.

- [ ] **Step 7: Independent review, CI, merge and cleanup**

Run fresh exact-SHA goal, code-quality, security/privacy, context/history and hands-on QA lanes. Address findings test-first and rerun every applicable lane after any SHA change. Push one branch, open one focused PR, require Fast CI green, merge only the approved tree, verify GitHub signature and parents, run post-merge QA, close #267 and remove only its feature/review worktrees and branches.

## Self-Review Result

- Spec coverage: #267 covers only the first delivery slice from #265; real data creation, calibration execution, signed selection, preregistration, one-shot and policy reconciliation remain explicitly deferred.
- Placeholder scan: każdy krok zawiera konkretne pliki, interfejs, komendę,
  oczekiwany wynik i zamknięty zakres implementacji.
- Type consistency: the plan uses one `CalibrationSourceIdentity`, one parsed `CalibrationConfig`, one `CalibrationDataset`, one `KeyOutcome` and one `CalibrationRunResult` path from contract through runner and reports.
- Packaging boundary: the new runtime is source-checkout-only by anchored wheel/sdist exclusion; normal installed Polis remains unchanged.
- Safety boundary: the consumed #243 holdout is neither read nor rerun, and no new real data or irreversible artifact is produced by #267.
