# Runtime-First Product Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make the current Polis repository present a small offline runtime product while keeping research, evaluation, and historical evidence in the repository but outside the default library artifacts and fast product path.

**Architecture:** Keep Analyzer and the existing src/polis runtime contracts stable. Tighten the sdist policy, add executable artifact-content checks, explicitly separate product and research test paths, and preserve polis.evaluation as a compatibility namespace for the current 0.x development line while preventing further expansion of that namespace. LanguageTool remains an opt-in local adapter/build artifact and never a default dependency.

**Tech Stack:** Python 3.12+, uv 0.11.2, Hatchling, pytest 9, Ruff 0.15, strict mypy, GitHub Actions, wheel and source-distribution inspection.

## Global Constraints

- Keep one repository; use short-lived branches for changes.
- Preserve offline-only operation and do not add a network, model-server, Java, or model dependency to the default runtime.
- Preserve public finding identity, strict JSON serialization, half-open Unicode offsets, correction conflict behavior, privacy diagnostics, and controlled failure semantics.
- Treat model input as data, never as instructions.
- Do not claim a local model is production-qualified unless it passes the existing evidence gates.
- Do not rerun or tune against consumed M5 holdouts.
- Keep research and evaluation evidence in Git unless a separate retention decision explicitly approves deletion.
- Do not move or remove polis.evaluation code until import compatibility and documentation references have been checked.
- Use regression-first tests for behavior or packaging changes.
- Use one focused commit per task and reference issue #120 in each commit message.
- Keep code, identifiers, GitHub metadata, and technical documentation in English.
- Keep the supported Python floor at >=3.12 and uv exactly at 0.11.2.
- Do not introduce a general plugin registry, grammar DSL, document adapter, GUI, or stylistic rewriting as part of this plan.

## Scope guard

This is a coordinating plan for four independently reviewable deliverables:

1. artifact boundary and package-content verification;
2. product/research test and CI separation;
3. evaluation namespace compatibility and optional-adapter documentation;
4. issue/roadmap reconciliation.

Phase 1 is the first executable subproject. Do not begin Phase 2 until Phase 1 has a green focused test cycle. Do not remove or relocate polis.evaluation code in this plan; the compatibility ADR records the safe 0.x policy first. A future namespace extraction, if desired, requires its own implementation plan.

## File map

| File | Responsibility in this plan |
| --- | --- |
| pyproject.toml | sdist exclusions and pytest marker declarations |
| tests/test_distribution_artifacts.py | build-time assertions for wheel/sdist contents |
| scripts/verify_distribution_artifacts.py | CI-facing artifact verifier with the same exclusion policy |
| tests/test_fast_ci_workflow.py | executable contract for the fast workflow marker filter |
| scripts/validate_fast_ci_workflow.py | validator for the product-only pytest command |
| .github/workflows/fast-ci.yml | product-only fast CI command |
| docs/development/research-workflow.md | explicit commands and boundaries for research/evaluation runs |
| docs/architecture/decisions/0019-evaluation-namespace-compatibility.md | accepted 0.x compatibility policy for polis.evaluation |
| tests/test_package_smoke.py | compatibility smoke coverage for shipped imports |
| README.md | product-first positioning and artifact policy |
| docs/distribution-verification.md | release artifact inclusion/exclusion evidence |
| docs/evaluation-dataset.md | repository-only evaluation role and provenance |
| docs/offline-operation.md | default runtime versus optional LanguageTool behavior |
| docs/development/dependency-licenses.md | optional vendor/build artifact boundary |
| docs/limitations.md | supported claims and research-only limitations |
| docs/project/ROADMAP.md | product versus research sequencing after issue disposition |

## Task 0: Establish a clean baseline

**Files:**
- Read only: pyproject.toml, docs/superpowers/specs/2026-07-29-runtime-first-product-boundary-design.md, tests/test_distribution_artifacts.py, .github/workflows/fast-ci.yml
- No files are modified.

**Interfaces:**
- Consumes: current branch codex/product-boundary and commit 2cdc32a.
- Produces: a recorded baseline for the implementation branch.

- [ ] **Step 1: Confirm the branch and worktree are clean**

Run:

~~~console
git status --short --branch
git log -1 --oneline
~~~

Expected: branch is codex/product-boundary, the worktree is clean, and HEAD is the committed architecture specification.

- [ ] **Step 2: Run the current fast suite before implementation**

Run:

~~~console
uv run --locked --extra dev pytest -m "not slow and not model"
~~~

Expected: exit 0. If this fails, record the exact failing test and stop the implementation sequence until the baseline is understood.

- [ ] **Step 3: Build and inspect the current artifacts into a temporary directory**

Run:

~~~console
uv run --locked --extra dev python -m build --no-isolation --outdir /tmp/polis-product-boundary-baseline
uv run --locked --extra dev python scripts/verify_distribution_artifacts.py --dist /tmp/polis-product-boundary-baseline
~~~

Expected: the existing license verifier passes. Record which repository-only paths currently appear in the sdist; these entries are the regression targets for Task 1.

- [ ] **Step 4: Commit**

No commit is created for this task. The baseline is evidence for the first implementation commit.

## Task 1: Enforce the product artifact boundary

**Files:**
- Modify: pyproject.toml
- Modify: tests/test_distribution_artifacts.py
- Modify: scripts/verify_distribution_artifacts.py
- Test: tests/test_distribution_artifacts.py

**Interfaces:**
- Consumes: Hatchling sdist configuration and the existing build/verification helpers.
- Produces: one shared policy expressed as testable excluded path prefixes for both wheel and sdist artifacts.

The first implementation must remove repository-only material from artifacts without changing runtime source files. The sdist exclusion policy must cover experiments, fine-tuning data, research fixtures, typecheck examples, vendored build trees, and Superpowers planning records. The repository tests remain available in GitHub checkout and are not required to be present inside a release sdist.

- [ ] **Step 1: Add failing artifact-content assertions**

In tests/test_distribution_artifacts.py, define the exact exclusion set:

~~~python
EXCLUDED_ARTIFACT_PREFIXES = (
    "experiments/",
    "data/finetuning/",
    "tests/",
    "third_party/",
    "docs/superpowers/",
)
~~~

Add a test that builds into tmp_path / "dist", lists wheel and sdist members, and asserts that no member contains any excluded prefix after removing the archive root prefix from sdist names. Keep assertions for LICENSE, MIT metadata, src/polis runtime files, and the required README.

Remove the current assertions that require tests/test_public_models.py and the evaluation dataset to appear in the sdist. Replace them with an assertion that no test or evaluation fixture path is shipped.

Use this test shape:

~~~python
def _without_sdist_root(name: str) -> str:
    parts = name.split("/", 1)
    return parts[1] if len(parts) == 2 else name


def test_built_distributions_exclude_repository_only_material(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "build",
            "--no-isolation",
            "--outdir",
            str(dist),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr
    wheel = next(dist.glob("*.whl"))
    sdist = next(dist.glob("*.tar.gz"))
    with zipfile.ZipFile(wheel) as archive:
        wheel_names = archive.namelist()
    with tarfile.open(sdist) as archive:
        sdist_names = archive.getnames()
    for name in wheel_names:
        assert not name.startswith(EXCLUDED_ARTIFACT_PREFIXES)
    for name in sdist_names:
        normalized = _without_sdist_root(name)
        assert not normalized.startswith(EXCLUDED_ARTIFACT_PREFIXES)
~~~

Run:

~~~console
uv run --locked --extra dev pytest tests/test_distribution_artifacts.py::test_built_distributions_exclude_repository_only_material -v
~~~

Expected: FAIL because the current sdist contains at least one excluded repository path.

- [ ] **Step 2: Implement the minimal Hatchling exclusion policy**

In pyproject.toml, extend tool.hatch.build.targets.sdist.exclude with:

~~~toml
"/data/finetuning",
"/experiments",
"/tests",
"/third_party",
"/docs/superpowers",
~~~

Preserve existing exclusions and the wheel target packages = ["src/polis"]. Do not exclude src/polis/evaluation in this task; its compatibility decision is handled in Task 3.

- [ ] **Step 3: Mirror the policy in the executable verifier**

In scripts/verify_distribution_artifacts.py, define the same excluded prefixes as a tuple of strings. Add a helper that normalizes sdist members by removing the archive root directory. Make verify_wheel and verify_sdist reject any excluded member with a message naming the artifact and path.

Use this validation shape in both archive paths:

~~~python
def _assert_no_excluded_members(
    names: list[str], *, artifact: Path, sdist: bool
) -> None:
    for raw_name in names:
        name = _without_sdist_root(raw_name) if sdist else raw_name
        if name.startswith(EXCLUDED_ARTIFACT_PREFIXES):
            raise SystemExit(f"{artifact}: excluded repository path: {name}")
~~~

The verifier must continue to check exactly one wheel and one sdist, MIT metadata, and LICENSE inclusion. It must remain usable as a standalone command from a clean checkout.

- [ ] **Step 4: Run the focused artifact tests**

Run:

~~~console
uv run --locked --extra dev pytest tests/test_distribution_artifacts.py -v
uv run --locked --extra dev python -m build --no-isolation --outdir /tmp/polis-product-boundary-task-1
uv run --locked --extra dev python scripts/verify_distribution_artifacts.py --dist /tmp/polis-product-boundary-task-1
~~~

Expected: all focused tests pass; the verifier reports that artifacts declare MIT metadata, contain LICENSE, and contain no excluded repository-only paths.

- [ ] **Step 5: Commit**

~~~console
git add pyproject.toml tests/test_distribution_artifacts.py scripts/verify_distribution_artifacts.py
git commit -m "build: enforce runtime artifact boundary (#120)"
~~~

## Task 2: Separate product and research test paths

**Files:**
- Modify: pyproject.toml
- Modify: .github/workflows/fast-ci.yml
- Modify: scripts/validate_fast_ci_workflow.py
- Modify: tests/test_fast_ci_workflow.py
- Modify: research test modules listed below
- Create: docs/development/research-workflow.md
- Test: tests/test_fast_ci_workflow.py and the marker collection commands

**Interfaces:**
- Consumes: the existing slow/model pytest markers and the current fast CI workflow contract.
- Produces: a research marker and a documented product-only fast command:
  uv run --locked --extra dev pytest -m "not research and not slow and not model".

Add the research marker to pyproject.toml:

~~~toml
"research: tests that require research corpora, benchmark runners, recorded qualification, or optional research runtimes",
~~~

Mark the following modules with module-level pytestmark = pytest.mark.research because they depend on research corpora, benchmark evidence, or model/qualification work:

- tests/test_correction_corpus_v3.py
- tests/test_evaluation_dataset.py
- tests/test_finetuning_dataset.py
- tests/test_inflection_candidate_benchmark.py
- tests/test_languagetool_benchmark.py
- tests/test_languagetool_corpus_quality.py
- tests/test_languagetool_stdio_benchmark.py
- tests/test_languagetool_vendor_benchmark.py
- tests/test_llm_benchmark.py
- tests/test_nlp_dependency_evaluation.py
- tests/test_performance_baseline.py
- tests/test_qlora_benchmark.py
- tests/test_quality_baseline.py
- tests/test_real_llm_benchmark.py
- tests/test_residual_syntax_evaluation.py
- tests/test_role_prompt_benchmark.py
- tests/test_role_prompt_experiment.py
- tests/test_safety_corpus.py
- tests/test_sentence_category_routing.py
- tests/test_sentence_safety_gate.py
- tests/test_sentence_safety_installation.py
- tests/test_sentence_safety_runner.py
- tests/test_sentence_syntax_qualification.py
- tests/test_two_pass_prompt_contract.py
- tests/test_two_pass_qwen35_benchmark.py
- tests/test_languagetool_rule_inventory.py

Do not mark public contract, deterministic rule, privacy, packaging, offline, or vendor-provenance tests as research when they do not load research-only assets. Keep existing slow/model markers where they describe runtime cost or real-model access.

- [ ] **Step 1: Add the failing workflow contract test**

In tests/test_fast_ci_workflow.py, add an assertion that the workflow contains exactly this product-only command:

~~~python
assert 'pytest -m "not research and not slow and not model"' in workflow
~~~

Update the invalid-workflow test fixture so removing research from the marker expression is rejected by scripts/validate_fast_ci_workflow.py.

Run:

~~~console
uv run --locked --extra dev pytest tests/test_fast_ci_workflow.py -v
~~~

Expected: FAIL because the current workflow does not exclude research.

- [ ] **Step 2: Add and apply the research marker**

Add the marker declaration to pyproject.toml. Add pytest imports and module-level marks to the exact research test list above. Do not alter test logic.

Run:

~~~console
uv run --locked --extra dev pytest --collect-only -q -m research
uv run --locked --extra dev pytest --collect-only -q -m "not research and not slow and not model"
~~~

Expected: both commands collect tests; the two sets are disjoint for the marked modules.

- [ ] **Step 3: Update the fast CI validator and workflow**

Change .github/workflows/fast-ci.yml to run:

~~~yaml
- name: Run pytest suite
  run: uv run --locked --extra dev pytest -m "not research and not slow and not model"
~~~

Update scripts/validate_fast_ci_workflow.py to require the exact three-part exclusion and to reject an unfiltered or research-inclusive command. Update tests/test_fast_ci_workflow.py for the new contract while preserving all platform matrix and action-pin assertions.

- [ ] **Step 4: Document the two execution paths**

Create docs/development/research-workflow.md with:

- the product-only fast command;
- the research command uv run --locked --extra dev pytest -m research;
- the command for explicit slow/model runs;
- the fact that research results do not qualify a production model automatically;
- the prohibition on rerunning or tuning against consumed one-shot holdouts;
- the provenance locations for corpora, reports, and optional LanguageTool evidence;
- the rule that research code may consume public result models but runtime analysis must not import research runners.

Update README.md's CI section to link to this document and describe the product-only fast filter.

- [ ] **Step 5: Run the focused CI and marker checks**

Run:

~~~console
uv run --locked --extra dev pytest tests/test_fast_ci_workflow.py -v
uv run --locked --extra dev pytest -m "not research and not slow and not model"
uv run --locked --extra dev pytest -m research --collect-only -q
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
~~~

Expected: workflow contract, product-only tests, research collection, Ruff lint, and formatting all pass.

- [ ] **Step 6: Commit**

~~~console
git add pyproject.toml .github/workflows/fast-ci.yml scripts/validate_fast_ci_workflow.py tests/test_fast_ci_workflow.py docs/development/research-workflow.md README.md tests/test_correction_corpus_v3.py tests/test_evaluation_dataset.py tests/test_finetuning_dataset.py tests/test_inflection_candidate_benchmark.py tests/test_languagetool_benchmark.py tests/test_languagetool_corpus_quality.py tests/test_languagetool_stdio_benchmark.py tests/test_languagetool_vendor_benchmark.py tests/test_llm_benchmark.py tests/test_nlp_dependency_evaluation.py tests/test_performance_baseline.py tests/test_qlora_benchmark.py tests/test_quality_baseline.py tests/test_real_llm_benchmark.py tests/test_residual_syntax_evaluation.py tests/test_role_prompt_benchmark.py tests/test_role_prompt_experiment.py tests/test_safety_corpus.py tests/test_sentence_category_routing.py tests/test_sentence_safety_gate.py tests/test_sentence_safety_installation.py tests/test_sentence_safety_runner.py tests/test_sentence_syntax_qualification.py tests/test_two_pass_prompt_contract.py tests/test_two_pass_qwen35_benchmark.py tests/test_languagetool_rule_inventory.py
git commit -m "test: separate product and research paths (#120)"
~~~

## Task 3: Record the 0.x evaluation namespace compatibility decision

**Files:**
- Create: docs/architecture/decisions/0019-evaluation-namespace-compatibility.md
- Modify: docs/architecture/README.md
- Modify: docs/evaluation-dataset.md
- Modify: docs/public-api.md
- Modify: tests/test_package_smoke.py
- Modify: tests/test_api_compatibility.py
- Test: tests/test_package_smoke.py and tests/test_api_compatibility.py

**Interfaces:**
- Consumes: current polis.evaluation imports, public API snapshot, and the runtime-first product boundary specification.
- Produces: an accepted compatibility rule for the current 0.x line.

Use the conservative decision: retain polis.evaluation as an import-compatible, repository-evaluation namespace for the current 0.x development line; do not add new runtime features to it; do not promise it as the primary product interface; do not remove it from the wheel in this plan. Large research fixtures remain excluded from artifacts by Task 1.

- [ ] **Step 1: Add the compatibility regression test**

In tests/test_api_compatibility.py, add a test that imports polis.evaluation and verifies the existing documented validator symbols remain importable. Use the existing public API snapshot style and avoid asserting implementation details.

Example:

~~~python
def test_evaluation_namespace_remains_compatible_for_the_0x_line() -> None:
    import polis.evaluation as evaluation

    assert callable(evaluation.load_dataset)
    assert callable(evaluation.validate_dataset)
~~~

Run:

~~~console
uv run --locked --extra dev pytest tests/test_api_compatibility.py::test_evaluation_namespace_remains_compatible_for_the_0x_line -v
~~~

Expected: PASS before the documentation change; the test freezes the compatibility requirement.

- [ ] **Step 2: Record ADR-0019**

Create docs/architecture/decisions/0019-evaluation-namespace-compatibility.md with:

- status Accepted;
- the 0.x compatibility guarantee for existing evaluator imports;
- the distinction between repository evaluation and the supported runtime product;
- the artifact rule that large corpora, holdouts, reports, experiments, and training assets are not shipped;
- the condition for a future extraction: import inventory, migration/deprecation path, documentation update, and a separate issue/plan;
- the explicit rejection of silently removing polis.evaluation during packaging cleanup.

Add ADR-0019 to docs/architecture/README.md.

- [ ] **Step 3: Update evaluation and public API documentation**

In docs/evaluation-dataset.md, state that the evaluator and corpora are repository tooling and provenance assets, while the supported runtime consumes public result models and does not depend on holdout access.

In docs/public-api.md, remove any wording that implies polis.evaluation is the primary text-analysis API. Keep links to evaluation methodology as repository development documentation.

- [ ] **Step 4: Run compatibility and documentation tests**

Run:

~~~console
uv run --locked --extra dev pytest tests/test_package_smoke.py tests/test_api_compatibility.py -v
uv run --locked --extra dev ruff check src/polis tests/test_package_smoke.py tests/test_api_compatibility.py
uv run --locked --extra dev mypy src tests/test_package_smoke.py tests/test_api_compatibility.py
~~~

Expected: existing imports and public API compatibility checks pass with no new runtime dependency.

- [ ] **Step 5: Commit**

~~~console
git add docs/architecture/decisions/0019-evaluation-namespace-compatibility.md docs/architecture/README.md docs/evaluation-dataset.md docs/public-api.md tests/test_package_smoke.py tests/test_api_compatibility.py
git commit -m "docs: record evaluation namespace compatibility (#120)"
~~~

## Task 4: Make the optional LanguageTool boundary explicit

**Files:**
- Modify: tests/test_distribution_artifacts.py
- Modify: tests/test_offline_verification.py
- Modify: docs/offline-operation.md
- Modify: docs/development/dependency-licenses.md
- Modify: docs/limitations.md
- Modify: docs/distribution-verification.md
- Test: tests/test_distribution_artifacts.py and tests/test_offline_verification.py

**Interfaces:**
- Consumes: existing LanguageTool adapter seams, vendor artifact checks, and offline verification.
- Produces: explicit evidence that default Polis operation does not require Java, a LanguageTool process, a model, or network access.

- [ ] **Step 1: Add failing default-runtime boundary checks**

Add a test in tests/test_offline_verification.py that constructs Analyzer with default deterministic configuration, blocks socket.create_connection, and verifies analysis completes without resolving the vendored executable or starting a LanguageTool process. Use dependency injection or monkeypatch at the existing session seam rather than inspecting private implementation state.

Use this test shape, adapting the existing analyzer fixture names if needed:

~~~python
def test_default_analyzer_does_not_start_optional_languagetool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_started(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("optional LanguageTool must remain disabled")

    monkeypatch.setattr(
        "polis.rules.languagetool_stdio.LocalLanguageToolStdioSession.from_executable",
        fail_if_started,
    )
    analyzer = Analyzer(AnalyzerConfig(use_local_heuristic_backend=False))
    result = analyzer.analyze("Witaj, świecie.")
    assert result.text == "Witaj, świecie."
~~~

Add artifact assertions that reject compiled/vendor output names such as .jar, target/, maven repositories, and model-weight extensions in both wheel and sdist.

Run:

~~~console
uv run --locked --extra dev pytest tests/test_offline_verification.py tests/test_distribution_artifacts.py -v
~~~

Expected: the default-runtime test passes if the existing behavior already satisfies the contract; the new artifact assertion should fail only if build output contains a prohibited vendor artifact.

- [ ] **Step 2: Document the three LanguageTool states**

Update docs/offline-operation.md and docs/limitations.md to distinguish:

1. default runtime: no LanguageTool, Java, model, or network;
2. optional loopback HTTP mode: caller-supplied local process only;
3. optional vendored stdio mode: caller explicitly builds and supplies the pinned local executable.

State that the vendored source tree is a repository build artifact excluded from wheel and sdist. Preserve the current five-rule qualification and sentence-only limitation.

- [ ] **Step 3: Align license and distribution evidence**

Update docs/development/dependency-licenses.md and docs/distribution-verification.md so the LGPL LanguageTool source, OpenJDK, Java artifacts, and generated build output are clearly outside default Python distribution artifacts. Do not change the accepted license policy or claim that LanguageTool is a Python production dependency.

- [ ] **Step 4: Run focused offline and vendor checks**

Run:

~~~console
uv run --locked --extra dev pytest tests/test_offline_verification.py tests/test_languagetool_vendor_artifacts.py tests/test_languagetool_vendor_runtime.py tests/test_distribution_artifacts.py -v
uv run --locked --extra dev python -m build --no-isolation --outdir /tmp/polis-product-boundary-task-4
uv run --locked --extra dev python scripts/verify_distribution_artifacts.py --dist /tmp/polis-product-boundary-task-4
~~~

Expected: default analysis succeeds with network blocked, vendor provenance checks remain green, and artifacts contain no Java/vendor build output.

- [ ] **Step 5: Commit**

~~~console
git add tests/test_distribution_artifacts.py tests/test_offline_verification.py docs/offline-operation.md docs/development/dependency-licenses.md docs/limitations.md docs/distribution-verification.md
git commit -m "docs: clarify optional LanguageTool boundary (#120)"
~~~

## Task 5: Publish the runtime-first product documentation

**Files:**
- Modify: README.md
- Modify: docs/quick-start.md
- Modify: docs/public-api.md
- Modify: docs/limitations.md
- Modify: docs/distribution-verification.md
- Modify: docs/evaluation-dataset.md
- Test: tests/test_package_smoke.py and distribution documentation checks

**Interfaces:**
- Consumes: artifact, CI, evaluation namespace, and LanguageTool decisions from Tasks 1–4.
- Produces: consistent product messaging that does not overclaim model quality, paragraph coverage, or broad LanguageTool correction.

- [ ] **Step 1: Add documentation assertions for the core claims**

Extend the existing documentation-oriented tests or add a focused test in tests/test_package_smoke.py that reads README.md and asserts it contains the required product claims:

~~~python
required_phrases = (
    "offline",
    "LanguageTool",
    "No tested local model has qualified",
)
for phrase in required_phrases:
    assert phrase in readme
~~~

Use the repository's existing wording conventions if the exact capitalization differs; the test must assert the claim, not a marketing sentence.

- [ ] **Step 2: Rewrite the README product entry point**

Make the first sections of README.md answer:

- what Polis does today;
- what the default install includes;
- what correction behavior is automatic versus reviewable;
- what is explicitly not supported;
- where research/evaluation workflows live;
- how optional LanguageTool is enabled without implying a core dependency.

Keep the existing quick-start commands valid.

- [ ] **Step 3: Align linked documentation**

Update docs/quick-start.md, docs/public-api.md, docs/limitations.md, docs/evaluation-dataset.md, and docs/distribution-verification.md so they agree on:

- runtime versus repository-only material;
- no qualified production local model;
- sentence-only and narrow LanguageTool coverage;
- no DOCX/GUI/style rewrite;
- wheel/sdist exclusions;
- polis.evaluation compatibility for 0.x.

- [ ] **Step 4: Run documentation and package smoke checks**

Run:

~~~console
uv run --locked --extra dev pytest tests/test_package_smoke.py tests/test_distribution_artifacts.py -v
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
~~~

Expected: documentation claims and package checks pass with no formatting or lint errors.

- [ ] **Step 5: Commit**

~~~console
git add README.md docs/quick-start.md docs/public-api.md docs/limitations.md docs/evaluation-dataset.md docs/distribution-verification.md tests/test_package_smoke.py
git commit -m "docs: publish runtime-first product boundary (#120)"
~~~

## Task 6: Reconcile the issue tracker and roadmap

**Files:**
- Modify: docs/project/ROADMAP.md
- Modify: docs/project/RISKS.md
- External metadata: GitHub issues #76, #84, #85, #86, #87, #88, #89, #90, #92, #93, #95, #96, #97, #98, #99, #100, #119, #120

**Interfaces:**
- Consumes: the verified product boundary from Tasks 1–5.
- Produces: an issue graph that distinguishes product work from research evidence without closing unfinished work or rerunning holdouts.

- [ ] **Step 1: Update the roadmap text locally**

In docs/project/ROADMAP.md, preserve all unimplemented requirements but add an explicit product/research split:

- product release gates cover runtime safety, packaging, contracts, privacy, and deterministic behavior;
- model qualification and majority-coverage experiments remain research evidence;
- M6 internal architecture is not an implicit dependency of the product release;
- paragraph adapters, GUI, and stylistic rewriting remain out of scope.

Update docs/project/RISKS.md with the risks of evaluation namespace compatibility, artifact leakage, and research gates blocking product work.

- [ ] **Step 2: Prepare exact GitHub dispositions**

Keep product-facing:

- #84 as a P0 correction-policy issue;
- #95 as a P1 invariant-hardening issue.

Keep as future internal product work but outside the immediate release critical path:

- #96, #97, #98, and #99.

Reclassify as research/release-evidence work without closing:

- #76, #85, #86, #87, #88, #89, #90, #92, #93, and #119.

Do not remove blockers by editing dependency language alone. Do not change any consumed holdout, report, or result.

- [ ] **Step 3: Review issue edits before applying them**

Generate the proposed label/milestone/body changes with gh issue view and a local text record. Confirm that each issue has one clear goal, explicit scope, and no claim that an unqualified model is production-ready.

The final issue edits must use a quoted body file or stdin when Markdown contains code formatting. Do not inline shell-quoted issue bodies.

- [ ] **Step 4: Apply only the approved metadata changes**

Use gh issue edit for labels, milestone, and body updates. Do not close any issue in this task. Add dependency notes only where they reflect the accepted product/research split.

- [ ] **Step 5: Commit the repository roadmap changes**

~~~console
git add docs/project/ROADMAP.md docs/project/RISKS.md
git commit -m "docs: reconcile product and research roadmap (#120)"
~~~

## Task 7: Full verification and handoff

**Files:**
- No new source files.
- Review: all files changed by Tasks 1–6.

**Interfaces:**
- Consumes: all completed task commits and the issue/roadmap disposition.
- Produces: a verified branch ready for review or pull request creation.

- [ ] **Step 1: Run the product fast suite**

Run:

~~~console
uv run --locked --extra dev pytest -m "not research and not slow and not model"
~~~

Expected: exit 0 with no product test failures.

- [ ] **Step 2: Run static quality checks**

Run:

~~~console
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
~~~

Expected: all commands exit 0.

- [ ] **Step 3: Build and inspect both artifacts**

Run:

~~~console
rm -rf /tmp/polis-product-boundary-final
uv run --locked --extra dev python -m build --no-isolation --outdir /tmp/polis-product-boundary-final
uv run --locked --extra dev python scripts/verify_distribution_artifacts.py --dist /tmp/polis-product-boundary-final
uv run --locked --extra dev python scripts/verify_distribution_install.py --dist /tmp/polis-product-boundary-final
~~~

Expected: exactly one wheel and one sdist pass metadata, exclusion, clean-install, offline smoke, and CLI JSON checks.

- [ ] **Step 4: Run the offline and compatibility gates**

Run:

~~~console
uv run --locked --extra dev pytest tests/test_offline_verification.py tests/test_api_compatibility.py tests/test_package_smoke.py -v
~~~

Expected: default analysis works without network/model/Java and polis.evaluation compatibility remains intact.

- [ ] **Step 5: Run the complete repository test path separately**

Run:

~~~console
uv run --locked --extra dev pytest -m research --collect-only -q
~~~

If the owner explicitly wants research tests executed, run the relevant marked subset with the required local assets and record hardware/runtime/provenance. Do not run a consumed holdout or use its results for tuning.

- [ ] **Step 6: Check the final diff and branch state**

Run:

~~~console
git diff --check main..HEAD
git status --short --branch
git log --oneline --decorate main..HEAD
~~~

Expected: no whitespace errors, no untracked generated artifacts, and each commit maps to one #120 task.

- [ ] **Step 7: Prepare the handoff**

The handoff must include:

- issue #120 and acceptance status;
- changed files grouped by task;
- exact commands and results;
- whether product or research tests were run;
- known limitation that no local model is production-qualified;
- any unresolved polis.evaluation compatibility or issue metadata decisions;
- the next permitted action: review, PR, or the next implementation task.

## Acceptance mapping

| Spec requirement | Plan task |
| --- | --- |
| One repository and branch workflow | Tasks 0 and 7 |
| Small stable runtime interface | Tasks 3 and 5 |
| Research remains reproducible but not shipped | Tasks 1, 2, and 6 |
| Wheel/sdist artifact inspection | Tasks 1 and 7 |
| Product-only fast CI | Task 2 |
| polis.evaluation compatibility before removal | Task 3 |
| Optional LanguageTool boundary | Task 4 |
| No default Java/model/network dependency | Tasks 4 and 7 |
| Public result, correction, privacy, and offset stability | Tasks 3, 4, and 7 |
| Explicit M5/M6 disposition | Task 6 |
| Documentation and roadmap consistency | Tasks 3, 4, 5, and 6 |

## Commit sequence

1. build: enforce runtime artifact boundary (#120)
2. test: separate product and research paths (#120)
3. docs: record evaluation namespace compatibility (#120)
4. docs: clarify optional LanguageTool boundary (#120)
5. docs: publish runtime-first product boundary (#120)
6. docs: reconcile product and research roadmap (#120)

Each commit must pass the focused test cycle for its task. The final branch must pass the complete product fast suite, static checks, artifact inspection, clean-install smoke, and offline verification before review.
