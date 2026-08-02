# Issue #146 Sentence Safety Gate v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the installed-package sentence safety gate exactly once against frozen safety corpus v2, publish only aggregate privacy-safe evidence, and resolve #76 according to the unchanged gates.

**Architecture:** A new `experiments/sentence_safety_gate_v2` package selectively copies process infrastructure from #115 while binding new corpus, approval, freeze, marker, and report identities. Development streams only 80 visible cases and must qualify twice before the runner atomically reserves and materializes the 160-case holdout once. Historical experiment files and all runtime behavior remain unchanged.

**Tech Stack:** Python 3.11+, standard library XML/JSON/hash/process APIs, installed Polis wheel/sdist, vendored LanguageTool 6.8 stdio, pytest, Ruff, mypy, GitHub Actions.

## Global Constraints

- Work only on GitHub issue #146 and finish with one focused commit referring to `#146`.
- Never open, print, copy, score, or rerun corpus-v3 or safety-corpus-v1 holdout evidence.
- Never display corpus-v2 holdout text, gold edits, per-case outcomes, or raw runtime responses.
- Reuse only #115 evaluator infrastructure; do not copy its configuration, reports, marker, results, hashes, or case-level evidence.
- Corpus ID is `polis_polish_correction_safety_corpus_v2`.
- Candidate digest is `c64f009f14f0cde8390a46acc24660305534576bc897f70e281ffebbbbca6f53`.
- Frozen digest is `53cfce6b9cbe3f188290a064b34527912ea8f2a85c9ed29a67984c5ef5caaa29`.
- Approval role is exactly `Polis architecture owner`; do not attribute the review personally to Paweł Cyroń.
- Development contains exactly 80 cases; holdout contains exactly 160 cases.
- Do not change analyzers, source policy, quality thresholds, public contracts, corpus content, or runtime behavior.
- If development, preflight, review, identity, or privacy validation fails, stop before reservation.
- After the v2 marker exists, the holdout is consumed even if execution fails or is interrupted; never retry it.
- Automatic gates remain precision `1.00`, correction accuracy `1.00`, and zero changed protected negatives.
- Reviewable gates remain precision at least `0.90`, structured validity `1.00`, and zero findings on protected negatives.
- Performance gates remain in-process p95 `<=100 ms`, installed-runner p95 `<=500 ms`, peak RSS `<=1 GiB`, zero swap/socket/model-call counts, one LanguageTool process start, and two stable repetitions.
- Both channels must be non-vacuous to receive a precision pass.
- Reports contain aggregate evidence only and never sentence text, edit text, private paths, or case identifiers.
- After holdout reservation, no command may load corpus-v2 raw records or
  case-level gold; post-result checks use hashes and aggregate metadata only.
- No new production dependency is permitted.

---

## File map

- Create `experiments/sentence_safety_gate_v2/__init__.py`: experiment package marker.
- Create `experiments/sentence_safety_gate_v2/gate.py`: v2 configuration, split-safe loading, scoring, freeze, reservation, admission, and privacy contracts.
- Create `experiments/sentence_safety_gate_v2/run_evaluation.py`: artifact audit, clean installation, runner orchestration, preflight, development freeze, one-shot execution, and aggregate reporting.
- Create `experiments/sentence_safety_gate_v2/config.json`: exact predeclared corpus/runtime/source/gate configuration.
- Create `experiments/sentence_safety_gate_v2/evaluated_source.json`: exact evaluated source/tree and protected-history identities.
- Create `experiments/sentence_safety_gate_v2/README.md`: commands, boundaries, and final aggregate verdict.
- Create after qualifying development `experiments/sentence_safety_gate_v2/frozen_gate.json` and `report.json`.
- Create exactly once before holdout access `experiments/sentence_safety_gate_v2/holdout.started`.
- Create `tests/test_sentence_safety_gate_v2.py`: synthetic contract, privacy, artifact, freeze, reservation, admission, and historical-preservation tests.
- Reuse unchanged `scripts/run_sentence_safety_case.py` as a hash-bound installed runner.
- Modify `docs/evaluation-dataset.md`, `docs/llm-quality-gates.md`, `docs/limitations.md`, and `docs/project/ROADMAP.md` only to record #146 identities and aggregate disposition.

### Task 1: Add v2 configuration and development-only loader contracts

**Files:**
- Create: `experiments/sentence_safety_gate_v2/__init__.py`
- Create: `experiments/sentence_safety_gate_v2/gate.py`
- Create: `tests/test_sentence_safety_gate_v2.py`

**Interfaces:**
- Consumes: the v2 approval role/digest constants, generic immutable
  scoring/freeze/privacy primitives, and synthetic XML created inside the test
  temporary directory. It must not import or call the quality-gate selector.
- Produces: `GateConfig`, `QualityGates`, `SentenceCase`, `load_gate_config(path: Path) -> GateConfig`, and `load_development_sentences(path: Path, *, on_materialized: Callable[[str], None] | None = None) -> tuple[SentenceCase, ...]`.

- [ ] **Step 1: Add failing configuration and split-isolation tests**

Add tests that create synthetic 80-development/160-holdout XML without using committed case content. The materialization callback must receive only development IDs:

```python
def _synthetic_reviewed_xml() -> str:
    records = ['<?xml version="1.0" encoding="UTF-8"?>', "<corpus>"]
    for split, count in (("development", 80), ("holdout", 160)):
        prefix = "dev" if split == "development" else "holdout"
        for index in range(count):
            identifier = f"{prefix}-{index:03d}"
            records.extend(
                (
                    f'<case id="{identifier}" stratum="hard_negative" '
                    f'split="{split}" unit="sentence">',
                    f"<input>Poprawne zdanie syntetyczne {index}.</input>",
                    f"<expected_output>Poprawne zdanie syntetyczne {index}.</expected_output>",
                    '<review status="human-reviewed" '
                    'reviewer="Polis architecture owner" '
                    'reviewed_at="2026-08-02" '
                    'checklist_version="safety-corpus-review-v2"/>',
                    "</case>",
                )
            )
    records.append("</corpus>")
    return "\n".join(records)


def test_v2_development_loader_never_materializes_holdout(tmp_path: Path) -> None:
    corpus_xml = tmp_path / "synthetic-v2.xml"
    corpus_xml.write_text(_synthetic_reviewed_xml(), encoding="utf-8")
    materialized: list[str] = []

    cases = load_development_sentences(
        corpus_xml,
        on_materialized=materialized.append,
    )

    assert len(cases) == 80
    assert {case.split for case in cases} == {"development"}
    assert materialized == [f"dev-{index:03d}" for index in range(80)]
    assert not any(identifier.startswith("holdout-") for identifier in materialized)
```

Add a closed-schema configuration test asserting the v2 ID, both digests, approval path/hash, source-policy `1.2`, all unchanged numeric gates, and rejection of extra keys. Add a role test proving that `Paweł Cyroń` is rejected and only `Polis architecture owner` is accepted.

Add a test that changes the synthetic XML to 159 holdout `<case>` elements and
asserts `load_development_sentences()` rejects it. The SAX handler may count
holdout case start events, but it must ignore their fields, character data,
review records, and edits and must never invoke `on_materialized` for them.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
uv run --locked --extra dev pytest tests/test_sentence_safety_gate_v2.py \
  -k 'config or development_loader or owner_role' -q
```

Expected: collection fails because `experiments.sentence_safety_gate_v2.gate` does not exist.

- [ ] **Step 3: Implement a v2 adapter over generic gate primitives**

Import the generic immutable dataclasses, exact-edit scoring, runner-response
validation, hashing, freeze verification, and privacy helpers from
`experiments.sentence_safety_gate.gate`. Implement the v2-specific
`GateConfig`, `SentenceCase`, configuration parser, development XML handler,
approval checks, and loaders in the new module. Then:

- set corpus ID and candidate/frozen digests to the Global Constraints values;
- require corpus JSON, XML, and approval path/hash fields;
- require reviewer `Polis architecture owner`, date `2026-08-02`, and checklist `safety-corpus-review-v2` in the development XML handler;
- count exactly 160 holdout sentence case boundaries without retaining any
  holdout field or character content;
- reuse generic exact-edit, response validation, metric, freeze, and privacy
  code without copying it;
- wrap configuration mappings in immutable proxies and export only the
  interfaces used by the new experiment and tests.

Do not read or copy old configuration/report/marker files.

- [ ] **Step 4: Run focused tests and verify GREEN**

```bash
uv run --locked --extra dev pytest tests/test_sentence_safety_gate_v2.py \
  -k 'config or development_loader or owner_role' -q
uv run --locked --extra dev ruff check \
  experiments/sentence_safety_gate_v2 tests/test_sentence_safety_gate_v2.py
uv run --locked --extra dev mypy experiments/sentence_safety_gate_v2/gate.py
```

Expected: focused tests and static checks pass without reading committed holdout gold.

- [ ] **Step 5: Amend the issue commit**

```bash
git add experiments/sentence_safety_gate_v2/__init__.py \
  experiments/sentence_safety_gate_v2/gate.py \
  tests/test_sentence_safety_gate_v2.py
git commit --amend --no-edit
```

### Task 2: Enforce approval-bound, durable one-shot admission

**Files:**
- Modify: `experiments/sentence_safety_gate_v2/gate.py`
- Modify: `tests/test_sentence_safety_gate_v2.py`

**Interfaces:**
- Consumes: `CorrectionCorpusCase`, `validate_safety_corpus()`,
  `select_safety_cases_for_purpose()`, `FreezeInputs`, `FrozenGate`,
  `GateConfig`, canonical v2 raw JSON, approval manifest, and the library v2
  quality-gate selector.
- Produces: private immutable `HoldoutReservation`,
  `reserve_holdout_once(...) -> HoldoutReservation`, and
  `load_reserved_holdout_sentences(corpus_path: Path, approval_path: Path,
  marker: Path, frozen_path: Path, inputs: FreezeInputs, *, reservation:
  HoldoutReservation) -> tuple[SentenceCase, ...]`.

- [ ] **Step 1: Add failing adversarial admission tests**

Use monkeypatches and synthetic JSON to prove ordering without opening the committed holdout:

```python
def test_v2_reservation_is_durable_before_quality_gate_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marker = tmp_path / "holdout.started"
    observed: list[bool] = []

    def guarded_selector(*args: object, **kwargs: object) -> tuple[object, ...]:
        observed.append(marker.is_file())
        return ()

    monkeypatch.setattr(gate, "select_safety_cases_for_purpose", guarded_selector)
    _prepare_valid_synthetic_freeze(tmp_path, marker)
    with pytest.raises(ValueError, match="160"):
        _load_synthetic_reserved_holdout(tmp_path, marker)

    assert observed == [True]
```

Add separate tests for missing approval evidence, candidate/frozen digest drift, changed review date, mismatched marker, failed fsync, existing marker, interrupted execution, and permanent second-run denial. The failed-fsync test must prove selection was never called.

The failed-`fsync` test must also attempt admission using the complete marker
left on disk and prove that the absence of a returned reservation capability
rejects before raw/approval reads or selector calls. The success test must call
admission twice with the same capability and prove the second call is rejected
before any raw/approval read or selector call.

- [ ] **Step 2: Run the tests and verify RED**

```bash
uv run --locked --extra dev pytest tests/test_sentence_safety_gate_v2.py \
  -k 'reservation or admission or repeat or fsync' -q
```

Expected: tests fail because the copied v1 loader neither accepts approval evidence nor calls the v2 selector with raw/manifest bindings.

- [ ] **Step 3: Implement fail-closed ordering**

Update `load_reserved_holdout_sentences()` to:

1. require a reservation capability created by the successful call to
   `reserve_holdout_once()` in the same process;
2. atomically consume that capability before any raw/approval read;
3. require a persisted marker matching both the capability and
   `verify_frozen_gate()`;
4. load raw JSON and approval JSON only after those checks;
5. validate raw JSON to `CorrectionCorpus`;
6. call `select_safety_cases_for_purpose(corpus, purpose="quality_gate", raw=raw, approval_manifest=approval)`;
7. require exactly 160 reviewed holdout cases before returning scorer objects.

Keep exclusive marker creation, file flush, file `fsync`, and POSIX
parent-directory `fsync`. Return the unforgeable single-use capability only
after every durability step succeeds. Never remove a marker after any error.

- [ ] **Step 4: Run admission tests and verify GREEN**

```bash
uv run --locked --extra dev pytest tests/test_sentence_safety_gate_v2.py \
  -k 'reservation or admission or repeat or fsync' -q
```

Expected: all tests pass and no committed corpus case is selected.

- [ ] **Step 5: Amend the issue commit**

```bash
git add experiments/sentence_safety_gate_v2/gate.py \
  tests/test_sentence_safety_gate_v2.py
git commit --amend --no-edit
```

### Task 3: Add aggregate-only installed evaluation orchestration

**Files:**
- Create: `experiments/sentence_safety_gate_v2/run_evaluation.py`
- Modify: `tests/test_sentence_safety_gate_v2.py`
- Reuse unchanged: `scripts/run_sentence_safety_case.py`

**Interfaces:**
- Consumes: Task 1/2 contracts and the unchanged installed JSONL runner.
- Produces: `ArtifactAudit`, `CaseRun`, `PerformanceEvidence`, `InstalledRunnerSession`, `audit_release_artifacts()`, `install_artifact_offline()`, `summarize_split()`, `authorize_and_load_holdout()`, `run_prepared_split()`, and CLI `main(argv: Sequence[str] | None = None) -> int`.

- [ ] **Step 1: Add failing privacy, artifact, and orchestration tests**

Add tests proving:

- wheel/sdist archives reject research data, models, JARs, and private files;
- clean installs import only from the temporary installation;
- the runner request contains only schema, request ID, operation, and source text;
- scorer gold never enters subprocess arguments, environment, stdin metadata, logs, or errors;
- final/development reports contain no `case_id`, `stratum`, text/edit fields, raw responses, or private paths;
- aggregate summaries retain exact channel/category/source counts and a stable repetition digest;
- holdout authorization recomputes the development decision before reservation;
- development failure cannot call `reserve_holdout_once()`.
- `--verify-result` validates only report/freeze/marker metadata and never calls
  either corpus loader or selector.

The central privacy assertion is:

```python
def test_v2_report_is_aggregate_only() -> None:
    report = _qualifying_synthetic_report()

    validated = validate_privacy_safe_report(report)
    encoded = json.dumps(validated, ensure_ascii=False, sort_keys=True)

    for forbidden in (
        "case_id",
        "stratum",
        "expected_output",
        "original",
        "suggestion",
        "corrected_text",
        "selected_text",
        "raw_response",
    ):
        assert forbidden not in encoded
```

- [ ] **Step 2: Run orchestration tests and verify RED**

```bash
uv run --locked --extra dev pytest tests/test_sentence_safety_gate_v2.py \
  -k 'report or artifact or installed or development_decision' -q
```

Expected: import fails because `run_evaluation.py` does not exist.

- [ ] **Step 3: Implement v2 orchestration over generic evaluator primitives**

Import `ArtifactAudit`, `CaseRun`, `PerformanceEvidence`,
`InstalledRunnerSession`, artifact/install helpers, installed-case execution,
and other generic public primitives from
`experiments.sentence_safety_gate.run_evaluation`. Implement only v2-specific
CLI, freeze-input assembly, aggregate report schema, development verification,
authorization, and result verification in the new module. Then:

- import only from the v2 gate module;
- freeze the approval manifest and `evaluated_source.json` in addition to existing inputs;
- use the v2 corpus paths from `GateConfig`, never hard-coded v1 paths;
- pass approval evidence into holdout admission;
- remove per-case evidence from serialized reports;
- replace it with aggregate counts and a canonical stable-repetition digest computed in memory;
- preserve offline installs, artifact audit, network denial, fallback, sandbox, socket/process/RSS/swap measurements, and exact gate semantics;
- make `--holdout` create the marker inside `authorize_and_load_holdout()` before any selection;
- add `--verify-result` as a metadata-only path that validates the final
  aggregate schema, frozen hashes, and marker identity without loading a
  corpus;
- keep all output/error messages privacy-safe.

- [ ] **Step 4: Run orchestration tests and verify GREEN**

```bash
uv run --locked --extra dev pytest tests/test_sentence_safety_gate_v2.py \
  -k 'report or artifact or installed or development_decision' -q
uv run --locked --extra dev ruff check experiments/sentence_safety_gate_v2 \
  tests/test_sentence_safety_gate_v2.py
uv run --locked --extra dev mypy experiments/sentence_safety_gate_v2
```

Expected: all tests and static checks pass.

- [ ] **Step 5: Amend the issue commit**

```bash
git add experiments/sentence_safety_gate_v2/run_evaluation.py \
  tests/test_sentence_safety_gate_v2.py
git commit --amend --no-edit
```

### Task 4: Freeze configuration, source identity, documentation, and historical preservation

**Files:**
- Create: `experiments/sentence_safety_gate_v2/config.json`
- Create: `experiments/sentence_safety_gate_v2/evaluated_source.json`
- Create: `experiments/sentence_safety_gate_v2/README.md`
- Modify: `tests/test_sentence_safety_gate_v2.py`
- Modify: `docs/evaluation-dataset.md`
- Modify: `docs/llm-quality-gates.md`
- Modify: `docs/limitations.md`
- Modify: `docs/project/ROADMAP.md`

**Interfaces:**
- Consumes: exact source-policy `1.2`, v2 corpus/approval SHA-256 values, vendored runtime identities, active automatic sources, reviewable sources, and unchanged gates.
- Produces: a closed `config.json`, evaluated-source manifest, documented commands, and byte-for-byte protection for every historical artifact.

- [ ] **Step 1: Add failing exact-identity and historical-preservation tests**

Pin SHA-256 for all retained corpus-v3, safety-v1, #115 configuration, evaluated-source, frozen gate, marker, report, and documented result artifacts. Add tests proving none is modified by #146. Also assert:

```python
def test_v2_real_marker_is_absent_before_development() -> None:
    assert not Path("experiments/sentence_safety_gate_v2/holdout.started").exists()
```

Add documentation assertions for #146, sentence-only scope, unchanged gates, optional-research status, autonomous authorization, permanent repeat denial, and absence of production-model/paragraph claims.

- [ ] **Step 2: Run identity/documentation tests and verify RED**

```bash
uv run --locked --extra dev pytest tests/test_sentence_safety_gate_v2.py \
  -k 'real_config or retained or documentation or real_marker' -q
```

Expected: tests fail because the v2 config, source manifest, and README do not exist.

- [ ] **Step 3: Build the vendored runtime offline and collect exact identities**

```bash
POLIS_LT_OFFLINE=1 third_party/languagetool-pl/scripts/build.sh
sha256sum tests/fixtures/evaluation/polish_correction_safety_corpus_v2.json \
  tests/fixtures/evaluation/polish_correction_safety_corpus_v2.xml \
  tests/fixtures/evaluation/polish_correction_safety_corpus_v2.approval.json \
  third_party/languagetool-pl/manifest.json \
  third_party/languagetool-pl/scripts/run_stdio.sh \
  third_party/languagetool-pl/src/main/java/org/polis/languagetool/PolisStdioServer.java \
  third_party/languagetool-pl/target/languagetool-pl-stdio-0.1.0-SNAPSHOT.jar
```

Expected corpus raw hashes begin with the already verified values:

- JSON `9c9b1cf1103dfaa096dd113948e0b47bfb26d5722ebe5edce1250e9889a59f69`;
- XML `676bc630e6644aecd30daf166c50ebe9c8558fd5714e74081722b0c4123ecb3a`;
- approval `8a21b3d291eb0542b484db318350678bde39cbf549451eb6f35cfd995ba39d77`.

Abort on any mismatch.

- [ ] **Step 4: Write the closed configuration with `apply_patch`**

Use experiment ID `polis_sentence_safety_gate_v2_2026_08_02`, source-policy
`1.2`, the collected hashes, `macos-arm64-v1`, and every numeric gate from
Global Constraints. Configure these exact automatic sources:

- `rule:agreement.copula`;
- `rule:spelling.jestes`;
- `rule:spelling.wlasnie`;
- `rule:spelling.zeby`;
- `rule:syntax.comma_space`;
- `rule:syntax.list_space`;
- `rule:syntax.quote_space`;
- `rule:syntax.sentence_space`;
- `rule:languagetool.pl`.

Configure these exact reviewable sources:

- `rule:syntax.missing_reflexive`;
- `rule:syntax.missing_correlative`;
- `rule:languagetool.contextual_inflection`.

The lists must be non-empty and disjoint. `load_gate_config()` must reject
every missing, extra, or changed identity.

Write `evaluated_source.json` with schema version, issue `146`, base commit, staged tree identity from `git write-tree`, and SHA-256 records for evaluator, gate, installed runner, analyzer/source policy, corpus JSON/XML/approval, config, and protected-history manifest.

- [ ] **Step 5: Write boundary documentation**

Document separate `--preflight`, `--development`, `--verify-development`, and `--holdout` commands. State that `--holdout` is authorized only after all preceding commands and independent review pass, that it runs once without prompting, and that no recovery command exists.

- [ ] **Step 6: Run configuration/documentation tests and verify GREEN**

```bash
uv run --locked --extra dev pytest tests/test_sentence_safety_gate_v2.py \
  -k 'real_config or retained or documentation or real_marker' -q
test ! -e experiments/sentence_safety_gate_v2/holdout.started
git diff --check
```

Expected: tests pass, historical hashes match, marker is absent, and diff is clean.

- [ ] **Step 7: Amend the issue commit**

```bash
git add experiments/sentence_safety_gate_v2/config.json \
  experiments/sentence_safety_gate_v2/evaluated_source.json \
  experiments/sentence_safety_gate_v2/README.md \
  tests/test_sentence_safety_gate_v2.py \
  docs/evaluation-dataset.md docs/llm-quality-gates.md \
  docs/limitations.md docs/project/ROADMAP.md
git commit --amend --no-edit
```

### Task 5: Complete all reversible verification and run development

**Files:**
- Create after success: `experiments/sentence_safety_gate_v2/report.json`
- Create after success: `experiments/sentence_safety_gate_v2/frozen_gate.json`
- Modify only v2 experiment/tests/docs if a reversible evaluator defect is found.

**Interfaces:**
- Consumes: exact committed evaluator, runner, config, corpus/approval, source policy, runtime, wheel, and sdist identities.
- Produces: a qualifying aggregate development report and frozen input hashes; produces no marker and no holdout score.

- [ ] **Step 1: Prove marker absence and run focused tests**

```bash
test ! -e experiments/sentence_safety_gate_v2/holdout.started
uv run --locked --extra dev pytest tests/test_sentence_safety_gate_v2.py \
  tests/test_distribution_artifacts.py \
  tests/test_product_collection_guard.py -q
```

Expected: all pass and no holdout selection occurs.

- [ ] **Step 2: Run full reversible static verification**

```bash
uv run --locked --extra dev pytest -m "not research and not slow and not model" -q
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
POLIS_LT_VENDOR_INTEGRATION=1 uv run --locked --extra dev pytest \
  tests/test_languagetool_vendor_runtime.py -q
```

Expected: all checks pass. If any fails, use systematic debugging and stay before reservation.

- [ ] **Step 3: Build fresh distributions in a new directory**

```bash
test ! -e "$PWD/.superpowers/issue-146-dist"
mkdir -p "$PWD/.superpowers/issue-146-dist"
uv run --locked --extra dev python -m build --no-isolation \
  --outdir "$PWD/.superpowers/issue-146-dist"
```

Expected: the new ignored directory contains exactly one wheel and one sdist.

- [ ] **Step 4: Run preflight without reservation**

```bash
uv run --locked --extra dev python \
  -m experiments.sentence_safety_gate_v2.run_evaluation \
  --preflight \
  --config experiments/sentence_safety_gate_v2/config.json \
  --dist "$PWD/.superpowers/issue-146-dist" \
  --vendored-stdio "$PWD/third_party/languagetool-pl/scripts/run_stdio.sh"
test ! -e experiments/sentence_safety_gate_v2/holdout.started
```

Expected: all native/privacy/resource capabilities qualify and marker remains absent.

- [ ] **Step 5: Run the 80-case development audit twice and freeze**

```bash
uv run --locked --extra dev python \
  -m experiments.sentence_safety_gate_v2.run_evaluation \
  --development \
  --config experiments/sentence_safety_gate_v2/config.json \
  --dist "$PWD/.superpowers/issue-146-dist" \
  --vendored-stdio "$PWD/third_party/languagetool-pl/scripts/run_stdio.sh" \
  --output experiments/sentence_safety_gate_v2/report.json \
  --freeze experiments/sentence_safety_gate_v2/frozen_gate.json
```

Expected: exactly 80 development cases, two stable repetitions, every gate passes, aggregate-only report and freeze are written, and marker remains absent. If the command exits non-zero, stop; do not tune analyzer/corpus/config/thresholds and do not run holdout.

- [ ] **Step 6: Verify frozen development evidence without evaluation**

```bash
uv run --locked --extra dev python \
  -m experiments.sentence_safety_gate_v2.run_evaluation \
  --verify-development \
  --config experiments/sentence_safety_gate_v2/config.json \
  --dist "$PWD/.superpowers/issue-146-dist" \
  --vendored-stdio "$PWD/third_party/languagetool-pl/scripts/run_stdio.sh" \
  --output experiments/sentence_safety_gate_v2/report.json \
  --freeze experiments/sentence_safety_gate_v2/frozen_gate.json
test ! -e experiments/sentence_safety_gate_v2/holdout.started
```

Expected: hashes and gates verify without running cases or creating a marker.

- [ ] **Step 7: Record aggregate development evidence and amend**

Update the v2 README/docs with aggregate channel metrics, performance, artifacts, environment, and the statement that no holdout access occurred. Then:

```bash
git add experiments/sentence_safety_gate_v2/report.json \
  experiments/sentence_safety_gate_v2/frozen_gate.json \
  experiments/sentence_safety_gate_v2/README.md \
  docs/evaluation-dataset.md docs/llm-quality-gates.md docs/limitations.md \
  docs/project/ROADMAP.md
git commit --amend --no-edit
```

### Task 6: Review and execute the irreversible holdout exactly once

**Files:**
- Create exactly once: `experiments/sentence_safety_gate_v2/holdout.started`
- Modify: `experiments/sentence_safety_gate_v2/report.json`
- Modify: aggregate documentation listed in Task 4.

**Interfaces:**
- Consumes: independently reviewed qualifying development report, exact frozen inputs, persisted marker path, and issue #146 authorization.
- Produces: one immutable marker, one aggregate holdout verdict, and no repeat capability.

- [ ] **Step 1: Obtain independent pre-holdout review**

Use `superpowers:requesting-code-review` against the design, this plan, issue #146, and every acceptance criterion. The reviewer must confirm:

- no holdout materialization occurred;
- marker is absent;
- development qualified under unchanged gates;
- raw corpus and approval evidence are required for admission;
- report schema is aggregate-only;
- all historical hashes match;
- command ordering creates and persists the marker before selection;
- the exact commit contains no analyzer, source-policy, threshold, corpus, or public-contract change.

Resolve every important finding with TDD and repeat full reversible verification. Do not proceed on a conditional verdict.

- [ ] **Step 2: Reverify frozen evidence immediately before reservation**

Run the exact `--verify-development` command from Task 5 Step 6, then:

```bash
test ! -e experiments/sentence_safety_gate_v2/holdout.started
git diff --check
```

Expected: verification passes and marker is absent.

- [ ] **Step 3: Run the holdout command exactly once**

```bash
uv run --locked --extra dev python \
  -m experiments.sentence_safety_gate_v2.run_evaluation \
  --holdout \
  --config experiments/sentence_safety_gate_v2/config.json \
  --dist "$PWD/.superpowers/issue-146-dist" \
  --vendored-stdio "$PWD/third_party/languagetool-pl/scripts/run_stdio.sh" \
  --output experiments/sentence_safety_gate_v2/report.json \
  --frozen experiments/sentence_safety_gate_v2/frozen_gate.json \
  --holdout-marker experiments/sentence_safety_gate_v2/holdout.started
```

Expected: the marker is durably persisted before exactly 160 holdout cases are selected. Exit `0` means all gates passed; exit `1` means a valid non-qualifying result. Any exit or interruption consumes the holdout permanently. Never invoke this command again.

- [ ] **Step 4: Validate the marker and report without loading holdout**

Run a metadata-only validation command implemented by `--verify-result`:

```bash
uv run --locked --extra dev python \
  -m experiments.sentence_safety_gate_v2.run_evaluation \
  --verify-result \
  --config experiments/sentence_safety_gate_v2/config.json \
  --dist "$PWD/.superpowers/issue-146-dist" \
  --output experiments/sentence_safety_gate_v2/report.json \
  --frozen experiments/sentence_safety_gate_v2/frozen_gate.json \
  --holdout-marker experiments/sentence_safety_gate_v2/holdout.started
```

Expected: marker/freeze/report identities and aggregate schema verify without any corpus selection.

- [ ] **Step 5: Record the aggregate verdict and amend**

Document only aggregate metrics, hashes, performance/privacy evidence, marker identity, and verdict. If qualified, mark #76 ready to close; otherwise state that #76 remains open and no tuning/retry is permitted.

```bash
git add experiments/sentence_safety_gate_v2/holdout.started \
  experiments/sentence_safety_gate_v2/report.json \
  experiments/sentence_safety_gate_v2/README.md \
  docs/evaluation-dataset.md docs/llm-quality-gates.md docs/limitations.md \
  docs/project/ROADMAP.md
git commit --amend --no-edit
```

### Task 7: Final verification, publication, and issue disposition

**Files:**
- Modify only #146 files if final review finds a defect that does not require rerunning holdout.

**Interfaces:**
- Consumes: immutable final marker/report and all implementation/evidence.
- Produces: one reviewed commit, green PR/CI, closed #146, and #76 disposition matching the verdict.

- [ ] **Step 1: Run all post-result checks that cannot rerun holdout**

```bash
uv run --locked --extra dev pytest tests/test_sentence_safety_gate_v2.py \
  tests/test_distribution_artifacts.py tests/test_product_collection_guard.py -q
uv run --locked --extra dev pytest -m "not research and not slow and not model" -q
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
git diff --check
```

Expected: all pass. These commands may verify metadata and hashes but must not call the holdout selector.

- [ ] **Step 2: Prove protected files are unchanged and one commit remains**

```bash
git diff --name-only origin/main -- \
  experiments/sentence_safety_gate \
  tests/fixtures/evaluation/polish_correction_safety_corpus_v1.json \
  tests/fixtures/evaluation/polish_correction_safety_corpus_v1.xml \
  tests/fixtures/evaluation/polish_correction_safety_corpus_v1.approval.json \
  tests/fixtures/evaluation/polish_correction_corpus_v3.json \
  tests/fixtures/evaluation/polish_correction_corpus_v3.xml
git rev-list --count origin/main..HEAD
git status --short
```

Expected: protected diff is empty, commit count is `1`, and worktree is clean.

- [ ] **Step 3: Obtain final independent review**

Use `superpowers:requesting-code-review` against issue #146, the design, this plan, final diff, aggregate report, and all acceptance criteria. Resolve only findings that do not alter or rerun the consumed holdout. A finding requiring new holdout evidence is a permanent limitation, not permission to retry.

- [ ] **Step 4: Push, open PR, wait for CI, and merge**

Push `codex/issue-146-sentence-safety-gate-v2`, open a ready PR against `main`, wait until every GitHub Actions check passes, and squash merge so #146 remains one focused commit. Do not close issues before merge and verification.

- [ ] **Step 5: Publish issue results**

Post the privacy-safe aggregate report summary to #146 and #76 with config, corpus, artifact, frozen-report, marker, and final-report digests. Then:

- close #146 as a completed one-shot experiment;
- close #76 only if every gate passed;
- otherwise leave #76 open and record that the v2 holdout is consumed;
- remove `status:blocked` from #76 only when its final state and dependency metadata require it;
- update local `main` and verify the merged files and GitHub states.

- [ ] **Step 6: Final handoff**

Report every acceptance criterion, development and holdout aggregate metrics, all frozen identities, historical-preservation proof, tests, commit, PR, CI, merge, #146/#76 state, limitations, and the next permitted action. Never include case-level evidence.
