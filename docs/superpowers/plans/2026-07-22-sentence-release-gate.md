# Installed-package Sentence Release Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove that a cleanly installed Polis wheel safely analyzes and minimally corrects individual Polish sentences through the public API using the complete qualified deterministic and vendored-LanguageTool stack.

**Architecture:** A repository-side evaluator owns corpus access, scorer-only gold data, distribution installation, subprocess orchestration, exact-edit scoring, freeze verification, and privacy-safe reports. A persistent runner executed by the clean installation owns one public `Analyzer` and exchanges one sentence request per JSON line, which reuses the single #77 stdio JVM for punctuation and contextual morphology. Development is evaluated first; only a passing report can freeze every executable input and atomically reserve the holdout before any holdout case is loaded.

**Tech Stack:** Python 3.12+, stdlib JSON/subprocess/venv/zipfile/tarfile/XML SAX, Polis public API, vendored LanguageTool 6.8 stdio, pytest, Ruff, mypy, Hatch/build.

## Global Constraints

- Evaluate only corpus-v3 records whose `unit` is exactly `sentence`.
- Analyzer subprocess input contains source text and frozen local runtime configuration; gold edits remain scorer-only.
- Exercise installed-wheel `Analyzer.analyze()`, `Analyzer.correct()`, and `CorrectionResult.apply_suggestions()`.
- Automatic exact-edit precision and changed-case correction accuracy must equal `1.00`.
- Reviewable exact-edit precision must be at least `0.90`; structured outcome validity must equal `1.00`.
- Each automatic and reviewable channel must propose at least one edit on each evaluated split.
- Protected hard negatives permit zero automatic changes and zero reviewable findings.
- All offsets use original-text Unicode code-point half-open ranges `[start, end)`.
- Warm in-runner p95 must be at most `100 ms`; warm end-to-end p95 at most `500 ms`.
- Combined peak RSS must be at most `1,073,741,824` bytes; swap growth and model calls must equal zero.
- The complete evaluation permits zero network sockets and no non-loopback or cloud communication.
- The wheel and sdist contain no corpus-v3 data, model weights, caches, Java products, private text, or optional runtime dependencies.
- Reports contain case identifiers, counts, hashes, source/category names, performance measurements, and decisions, but no source, expected output, original span, suggestion, raw response, or private path.
- Do not load any holdout case before an atomically created marker has validated the frozen configuration.
- Paragraphs, publication, model qualification, model training, and style rewriting remain outside #76.

---

### Task 1: Closed release-gate configuration and split-safe corpus access

**Files:**
- Create: `experiments/sentence_release_gate/__init__.py`
- Create: `experiments/sentence_release_gate/config.json`
- Create: `experiments/sentence_release_gate/gate.py`
- Test: `tests/test_sentence_release_gate.py`

**Interfaces:**
- Produces: `GateConfig`, `GoldEdit`, `SentenceCase`, `load_gate_config(path: Path) -> GateConfig`, `load_development_sentences(path: Path) -> tuple[SentenceCase, ...]`, `load_reserved_holdout_sentences(path: Path, marker: Path) -> tuple[SentenceCase, ...]`, and `sha256_path(path: Path) -> str`.
- `SentenceCase` exposes only `case_id`, `stratum`, `protected_negative`, `source`, `expected_output`, `gold_edits`, and `tags` to the repository-side scorer.

- [ ] **Step 1: Write failing closed-configuration and split-isolation tests**

```python
def test_gate_configuration_is_closed_sentence_only_and_pins_runtime() -> None:
    config = gate.load_gate_config(CONFIG)
    assert config.sentence_only is True
    assert config.source_policy_version == "1.1"
    assert config.corpus_sha256 == gate.sha256_path(CORPUS_JSON)
    assert config.corpus_xml_sha256 == gate.sha256_path(CORPUS_XML)
    assert config.model_calls_required == 0
    assert config.socket_count_maximum == 0

def test_development_loader_never_materializes_holdout_text(monkeypatch) -> None:
    seen: list[str] = []
    cases = gate.load_development_sentences(CORPUS_XML, on_materialized=seen.append)
    assert len(cases) == 69
    assert seen == [case.case_id for case in cases]
    assert all(case.split == "development" for case in cases)

def test_holdout_loader_requires_preexisting_valid_marker(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="reserved"):
        gate.load_reserved_holdout_sentences(CORPUS_JSON, tmp_path / "missing")
```

- [ ] **Step 2: Run the focused tests and observe missing-module failures**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_sentence_release_gate.py -q`

Expected: FAIL because `experiments.sentence_release_gate` does not exist.

- [ ] **Step 3: Implement exact config validation and an XML SAX development loader**

```python
@dataclass(frozen=True, slots=True)
class SentenceCase:
    case_id: str
    stratum: str
    split: Literal["development", "holdout"]
    source: str
    expected_output: str
    gold_edits: tuple[GoldEdit, ...]
    tags: tuple[str, ...]

    @property
    def protected_negative(self) -> bool:
        return self.stratum == "hard_negative"

def load_development_sentences(
    path: Path, *, on_materialized: Callable[[str], None] | None = None
) -> tuple[SentenceCase, ...]:
    handler = _DevelopmentSentenceHandler(on_materialized=on_materialized)
    xml.sax.parse(path, handler)
    if not handler.cases:
        raise ValueError("development sentence split is empty")
    return tuple(handler.cases)
```

The SAX handler must inspect `split` and `unit` on the `<case>` start event, discard all character events for non-development or non-sentence cases, validate reviewed selected records and exact gold offsets, and only invoke `on_materialized` for selected development sentences. The reserved holdout loader must validate a marker object first, then use the existing schema-v3 JSON loader and return reviewed holdout sentences only.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_sentence_release_gate.py -q`

Expected: PASS for configuration and corpus-loading tests.

---

### Task 2: Persistent installed-package runner protocol

**Files:**
- Create: `scripts/run_sentence_release_case.py`
- Create: `tests/test_sentence_release_runner.py`

**Interfaces:**
- Consumes newline-delimited requests with exact keys `schema_version`, `request_id`, `operation`, and `text` after CLI arguments provide `--vendored-stdio`, `--expected-install-root`, and `--timeout-seconds`.
- Produces newline-delimited responses with exact public finding fields, automatic/reviewable channels, corrected text, explicitly selected text, suggestion outcomes, elapsed milliseconds, Python/child RSS, and model calls.

- [ ] **Step 1: Write failing protocol, import-origin, sentence-boundary, and privacy tests**

```python
def test_runner_reuses_one_analyzer_for_multiple_sentence_requests(tmp_path: Path) -> None:
    process = start_runner(fake_stdio=make_fake_stdio(tmp_path))
    first = exchange(process, request(1, "Wiem że wróciła."))
    second = exchange(process, request(2, "Rozmawiałem z Janem Nowak."))
    assert first["request_id"] == 1
    assert second["request_id"] == 2
    assert first["process_start_count"] == 1
    assert second["process_start_count"] == 1

@pytest.mark.parametrize("text", ("", "Pierwsze. Drugie."))
def test_runner_rejects_non_single_sentence_without_echoing_text(text: str) -> None:
    response = run_one(request(1, text))
    assert response["status"] == "invalid_request"
    assert text not in json.dumps(response, ensure_ascii=False)

def test_runner_rejects_repository_import_when_install_root_differs(tmp_path: Path) -> None:
    completed = invoke_runner(expected_install_root=tmp_path)
    assert completed.returncode != 0
    assert "sentence" not in completed.stderr
```

- [ ] **Step 2: Run tests and observe the missing runner failure**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_sentence_release_runner.py -q`

Expected: FAIL because the runner script is absent.

- [ ] **Step 3: Implement the bounded persistent runner using public API only**

```python
with Analyzer(
    AnalyzerConfig(
        vendored_language_tool_stdio_path=os.fspath(arguments.vendored_stdio),
        vendored_language_tool_timeout_seconds=arguments.timeout_seconds,
    )
) as analyzer:
    for raw_line in sys.stdin:
        request = validate_request(raw_line)
        analyzed = analyzer.analyze(request.text)
        correction = analyzer.correct(request.text)
        selected_ids = tuple(
            finding.id
            for finding in correction.skipped_findings
            if finding.suggestion is not None
        )
        selected_text = correction.apply_suggestions(selected_ids)
        write_response(build_response(request, analyzed, correction, selected_text))
```

Validate a 65,536-byte request limit, strict keys/types, monotonic request identifiers, exactly one segmented sentence, import origin below the clean-install root, an absolute executable, no proxy variables, and privacy-safe error codes. Serialize only documented public object properties; do not inspect analyzer private state. Derive process-count and child RSS evidence from OS process relationships.

- [ ] **Step 4: Run runner tests**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_sentence_release_runner.py -q`

Expected: PASS.

---

### Task 3: Exact scorer, channel invariants, privacy-safe evidence, and gates

**Files:**
- Modify: `experiments/sentence_release_gate/gate.py`
- Create: `experiments/sentence_release_gate/run_evaluation.py`
- Modify: `tests/test_sentence_release_gate.py`

**Interfaces:**
- Produces `validate_runner_response(source: str, raw: object) -> RunnerObservation`, `score_split(cases, observations, performance) -> SplitReport`, `gate_qualifies(report, config) -> bool`, `validate_privacy_safe_report(raw) -> Mapping[str, object]`, and `InstalledRunnerSession`.

- [ ] **Step 1: Add failing exact-edit, reconstruction, channel, non-vacuity, and privacy tests**

```python
def test_exact_scorer_ignores_reported_category_and_source() -> None:
    gold = gate.ExactEdit(4, 4, "", ",")
    actual = gate.ObservedEdit(4, 4, "", ",", "syntax", "rule:other")
    counts = gate.score_exact_edits((gold,), (actual,))
    assert counts == gate.EditCounts(tp=1, fp=0, fn=0)

def test_response_rejects_original_or_reconstruction_mismatch() -> None:
    with pytest.raises(ValueError, match="original"):
        gate.validate_runner_response("Zażółć.", response_with_edit(0, 1, "X", "Y"))
    with pytest.raises(ValueError, match="reconstruct"):
        gate.validate_runner_response("Wiem że.", response_with_wrong_corrected_text())

def test_zero_proposal_channel_fails_non_vacuous_gate() -> None:
    report = passing_split_report()
    report["reviewable"]["proposed_edits"] = 0
    assert not gate.gate_qualifies(report, CONFIG_OBJECT)

def test_report_rejects_text_and_private_paths() -> None:
    with pytest.raises(ValueError, match="raw analyzed text"):
        gate.validate_privacy_safe_report({"suggestion": "tajne"})
    with pytest.raises(ValueError, match="private path"):
        gate.validate_privacy_safe_report({"runner": "/Users/name/project"})
```

- [ ] **Step 2: Run the focused tests and observe missing scorer failures**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_sentence_release_gate.py -q`

Expected: FAIL for missing scorer interfaces.

- [ ] **Step 3: Implement structural validation and exact scoring**

```python
def score_exact_edits(
    gold: tuple[ExactEdit, ...], actual: tuple[ObservedEdit, ...]
) -> EditCounts:
    gold_keys = {item.exact_key for item in gold}
    actual_keys = {item.exact_key for item in actual}
    return EditCounts(
        tp=len(gold_keys & actual_keys),
        fp=len(actual_keys - gold_keys),
        fn=len(gold_keys - actual_keys),
    )

def gate_qualifies(report: Mapping[str, object], config: GateConfig) -> bool:
    return bool(
        automatic.proposed_edits > 0
        and automatic.precision == 1.0
        and automatic.correction_accuracy == 1.0
        and reviewable.proposed_edits > 0
        and reviewable.precision >= 0.90
        and report.structured_outcome_validity == 1.0
        and report.protected_automatic_changes == 0
        and report.protected_reviewable_findings == 0
        and performance.warm_in_process_p95_ms <= 100.0
        and performance.warm_e2e_p95_ms <= 500.0
        and performance.combined_loaded_rss_bytes <= 1_073_741_824
        and performance.swap_delta_bytes == 0
        and performance.model_calls == 0
        and performance.socket_count == 0
    )
```

Validate disjoint configured channels, all exact offsets and original slices, non-overlap, `analyze()`/`correct()` finding consistency, automatic reconstruction, explicit-selection reconstruction, source allowlists, stable repeated output hashes, valid outcome enums, and model-generated findings remaining reviewable.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_sentence_release_gate.py tests/test_sentence_release_runner.py -q`

Expected: PASS.

---

### Task 4: Cryptographic freeze and one-shot holdout reservation

**Files:**
- Modify: `experiments/sentence_release_gate/gate.py`
- Modify: `experiments/sentence_release_gate/run_evaluation.py`
- Modify: `tests/test_sentence_release_gate.py`

**Interfaces:**
- Produces `freeze_gate(inputs: FreezeInputs, destination: Path) -> FrozenGate`, `verify_frozen_gate(...) -> FrozenGate`, and `reserve_holdout_once(frozen_path: Path, marker_path: Path, inputs: FreezeInputs) -> None`.

- [ ] **Step 1: Add failing mutation and reservation-order tests**

```python
def test_freeze_detects_every_executable_input_mutation(tmp_path: Path) -> None:
    frozen = gate.freeze_gate(freeze_inputs(tmp_path), tmp_path / "frozen.json")
    evaluator = freeze_inputs(tmp_path).evaluator
    evaluator.write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        gate.verify_frozen_gate(frozen.path, freeze_inputs(tmp_path))

def test_reservation_precedes_holdout_loader_and_is_one_shot(tmp_path: Path) -> None:
    marker = tmp_path / "holdout.started"
    gate.reserve_holdout_once(FROZEN, marker, INPUTS)
    assert marker.exists()
    with pytest.raises(FileExistsError, match="already reserved"):
        gate.reserve_holdout_once(FROZEN, marker, INPUTS)
```

- [ ] **Step 2: Run tests and observe missing freeze failures**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_sentence_release_gate.py -q`

Expected: FAIL because freeze interfaces are absent.

- [ ] **Step 3: Implement canonical hashes and exclusive marker creation**

```python
def reserve_holdout_once(
    frozen_path: Path, marker_path: Path, inputs: FreezeInputs
) -> None:
    frozen = verify_frozen_gate(frozen_path, inputs)
    try:
        with marker_path.open("x", encoding="utf-8") as stream:
            json.dump(frozen.as_dict(), stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
    except FileExistsError as error:
        raise FileExistsError("holdout run is already reserved") from error
```

Hash config, evaluator, gate module, installed runner, analyzer source policy, JSON/XML corpus, LT bridge/runner/manifest, exact JAR/dependency tree, wheel, and sdist. The CLI holdout branch must reserve before calling the holdout loader and must refuse a development report whose decision is not qualified.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_sentence_release_gate.py -q`

Expected: PASS.

---

### Task 5: Clean distribution installation, content audit, offline and failure evidence

**Files:**
- Modify: `pyproject.toml`
- Modify: `experiments/sentence_release_gate/run_evaluation.py`
- Modify: `tests/test_distribution_artifacts.py`
- Create: `tests/test_sentence_release_installation.py`

**Interfaces:**
- Produces `audit_release_artifacts(wheel: Path, sdist: Path) -> ArtifactAudit`, `install_artifact_offline(artifact: Path, destination: Path) -> Path`, and evaluator modes `--build`, `--development`, `--holdout`, and `--fallback`.

- [ ] **Step 1: Add failing tests proving corpus and runtime products are absent**

```python
@pytest.mark.parametrize("artifact_kind", ("wheel", "sdist"))
def test_release_artifact_excludes_gate_data_and_optional_runtime(artifact_kind: str) -> None:
    names = built_artifact_names(artifact_kind)
    assert not any("polish_correction_corpus_v3" in name for name in names)
    assert not any(name.endswith((".jar", ".gguf", ".safetensors")) for name in names)
    assert not any("target/dependency" in name or "/.cache/" in name for name in names)

def test_clean_wheel_runner_imports_only_installed_polis(tmp_path: Path) -> None:
    result = run_installed_smoke_from_external_cwd(tmp_path)
    assert result["status"] == "complete"
    assert result["model_calls"] == 0
```

- [ ] **Step 2: Build artifacts and observe the sdist corpus exclusion failure**

Run: `/Users/syron/Developer/polis/.venv/bin/python -m build --no-isolation --outdir /tmp/polis-issue-76-red-dist`

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_distribution_artifacts.py tests/test_sentence_release_installation.py -q`

Expected: FAIL because the current sdist includes evaluation corpus-v3 or the installed runner is absent.

- [ ] **Step 3: Exclude evaluation-only corpus and implement offline installation orchestration**

```toml
[tool.hatch.build.targets.sdist]
exclude = [
  "/tests/typecheck",
  "/tests/fixtures/evaluation/polish_correction_corpus_v3.json",
  "/tests/fixtures/evaluation/polish_correction_corpus_v3.xml",
  "/third_party/languagetool-pl",
]
```

Build with `python -m build --no-isolation`; install with `python -m pip install --no-index --no-deps --disable-pip-version-check`; launch from a temporary cwd outside the repository with repository `PYTHONPATH` removed. Audit every archive member against an allowlist and forbidden suffixes/names, and stream-scan every regular member for private home paths. Run the runner and JVM inside a macOS sandbox that denies all network operations, corroborate zero sockets with `lsof`, unset all proxy variables, record swap before/after, and run a failing-executable case that retains built-in spelling findings while optional sources emit none.

- [ ] **Step 4: Run installation, packaging, fallback, and offline tests**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_distribution_artifacts.py tests/test_sentence_release_installation.py tests/test_offline_verification.py -q`

Expected: PASS.

---

### Task 6: Development gate, freeze, then one-shot holdout

**Files:**
- Create: `experiments/sentence_release_gate/README.md`
- Create after qualifying development: `experiments/sentence_release_gate/frozen_gate.json`
- Create after reservation: `experiments/sentence_release_gate/holdout.started`
- Create: `experiments/sentence_release_gate/report.json`
- Modify: `tests/test_sentence_release_gate.py`

**Interfaces:**
- The committed report has top-level `schema_version`, `experiment_id`, `configuration_sha256`, `environment`, `artifact_audit`, `fallback`, `development`, `holdout`, and `decision` objects.

- [ ] **Step 1: Build the exact vendored runtime offline and exact distributions**

Run: `third_party/languagetool-pl/scripts/build.sh --offline`

Run: `/Users/syron/Developer/polis/.venv/bin/python -m build --no-isolation --outdir /tmp/polis-sentence-release-dist`

Expected: both commands exit 0 and generated hashes match config.

- [x] **Step 2: Run development using the clean wheel installation**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/python -m experiments.sentence_release_gate.run_evaluation --config experiments/sentence_release_gate/config.json --dist /tmp/polis-sentence-release-dist --vendored-stdio "$PWD/third_party/languagetool-pl/scripts/run_stdio.sh" --development --output experiments/sentence_release_gate/report.json --freeze experiments/sentence_release_gate/frozen_gate.json`

Expected: exit 0 only if both channels are non-vacuous and every development quality, safety, performance, offline, and package gate passes.

Recorded checkpoint: development qualified and the closed report was frozen
before the authorized holdout.

Pre-holdout hardening: platform capability preflight and every reversible
install/smoke/fallback/runner setup step execute before reservation. The native
socket audit must observe a known socket and reject `lsof` errors rather than
reporting them as zero.

- [x] **Step 3: If and only if development qualified, reserve and evaluate holdout once**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/python -m experiments.sentence_release_gate.run_evaluation --config experiments/sentence_release_gate/config.json --dist /tmp/polis-sentence-release-dist --vendored-stdio "$PWD/third_party/languagetool-pl/scripts/run_stdio.sh" --holdout --frozen experiments/sentence_release_gate/frozen_gate.json --holdout-marker experiments/sentence_release_gate/holdout.started --output experiments/sentence_release_gate/report.json`

Expected: marker is created before corpus holdout access; exit 0 only if the independent holdout gates pass.

Recorded result: the one-shot holdout ran once and failed automatic
full-correction accuracy (`0.80` versus required `1.00`). The marker is retained;
the holdout cannot be rerun or used for tuning.

- [x] **Step 4: Add committed-evidence assertions after the report exists**

```python
def test_committed_holdout_evidence_is_private_and_records_failed_gate() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert gate.validate_privacy_safe_report(report) == report
    assert report["development"]["decision"]["qualified"] is True
    assert report["holdout"]["decision"]["qualified"] is False
    assert report["holdout"]["automatic"]["correction_accuracy"] == 0.8
    assert report["decision"] == {"qualified": False, "scope": "sentence_only"}
    assert report["environment"]["model_calls_per_sentence"] == 0.0
```

- [ ] **Step 5: Run evidence tests**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_sentence_release_gate.py tests/test_sentence_release_installation.py -q`

Expected: PASS.

---

### Task 7: Sentence-only public documentation and full issue verification

**Files:**
- Modify: `README.md`
- Modify: `docs/public-api.md`
- Modify: `docs/offline-operation.md`
- Modify: `docs/quality-baseline.md`
- Modify: `docs/performance-baseline.md`
- Modify: `docs/privacy.md`
- Modify: `docs/limitations.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/release-checklist.md`
- Modify: `PROMPT.md`
- Modify: `tests/test_sentence_release_gate.py`

**Interfaces:**
- Documentation points to `experiments/sentence_release_gate/report.json` and states exactly which sentence sources are automatic versus reviewable, how explicit selection works, how to configure the vendored executable, and that no model or paragraph path is qualified.

- [ ] **Step 1: Add failing documentation assertions**

```python
def test_sentence_release_documentation_does_not_overclaim() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in DOCS)
    assert "sentence-only" in combined
    assert "apply_suggestions" in combined
    assert "no qualified production model" in combined
    assert "paragraph correction is not release-qualified" in combined
```

- [ ] **Step 2: Run the assertion and observe missing release-evidence wording**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_sentence_release_gate.py -q`

Expected: FAIL until documentation references exact sentence evidence and limitations.

- [ ] **Step 3: Update documentation with measured values and commands**

Document the exact installed-wheel command, source-policy `1.1`, automatic/reviewable split, development and holdout edit metrics, protected-negative counts, cold/warm p50/p95, throughput, RSS, swap, sockets, zero model calls, artifact audit, offline fallback, and residual recall limitations. Preserve #43 and #64 as open requirements and do not claim PyPI publication.

- [ ] **Step 4: Run all quality checks and real integration**

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/ruff check .`

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/ruff format --check .`

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/mypy .`

Run: `PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest -q`

Run: `POLIS_LT_VENDOR_INTEGRATION=1 PYTHONPATH="$PWD/src:$PWD" /Users/syron/Developer/polis/.venv/bin/pytest tests/test_languagetool_vendor_runtime.py -q`

Run: `/Users/syron/Developer/polis/.venv/bin/python scripts/verify_distribution_artifacts.py --dist /tmp/polis-sentence-release-dist`

Run: `/Users/syron/Developer/polis/.venv/bin/python scripts/verify_distribution_install.py --dist /tmp/polis-sentence-release-dist`

Expected: all commands exit 0, the complete fast suite reports no failures, and real vendored integration passes.

- [ ] **Step 5: Audit all #76 acceptance criteria against concrete evidence**

Check each issue checkbox against the report, artifact listing, test output, frozen hashes, marker creation order, and documentation. If any evidence is absent or a gate failed, leave #76 open and record the exact failing metric without weakening the threshold.

- [ ] **Step 6: Commit the one focused issue change**

```bash
git add pyproject.toml PROMPT.md README.md CHANGELOG.md docs experiments/sentence_release_gate scripts/run_sentence_release_case.py tests
git commit -m "test: add installed sentence release gate (#76)"
```

Expected: one commit authored only by Paweł Cyroń, with no co-author or tooling attribution.
