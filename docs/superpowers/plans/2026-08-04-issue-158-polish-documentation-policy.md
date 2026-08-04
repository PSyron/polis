# Polish-First Documentation Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement issue #158 by making Polish the default language for maintained project documentation, recording protected exceptions, and publishing an enforceable migration roadmap with atomic follow-up issues.

**Architecture:** Repository governance remains in `AGENTS.md` and `PROMPT.md`; a Polish migration roadmap explains which documentation classes move to Polish and which immutable, historical, machine-facing, or upstream assets retain their original language. A standard-library validator consumes an ordered JSON rule set and proves that every Git-tracked Markdown path receives exactly one effective disposition without reading protected content.

**Tech Stack:** Markdown, JSON, Python 3.12+ standard library, pytest, Git, GitHub Issues.

## Global Constraints

- Implement only GitHub issue #158; bulk translation is delegated to follow-up issues.
- Preserve every unimplemented requirement in `PROMPT.md`.
- Keep code, identifiers, schemas, CLI flags, configuration keys, protocol literals, and GitHub metadata in English.
- Keep `docs/superpowers/**`, accepted ADRs, frozen evaluation and release evidence, generated reports, `third_party/**`, and machine-readable fixtures in their original language and byte state.
- Preserve the single-repository runtime-first boundary and do not modify runtime, API, rules, correction policy, packaging contents, models, corpora, or holdouts.
- Keep one issue to one focused commit referencing #158; use a short-lived branch, independent review, and green CI before merge.
- Paweł Cyroń remains the sole credited author; add no automated-tool attribution or co-author trailer.

---

### Task 1: Add an executable documentation inventory contract

**Files:**
- Create: `tests/test_documentation_migration_inventory.py`
- Create: `scripts/validate_documentation_inventory.py`
- Create: `docs/project/documentation-migration-inventory.json`
- Create: `docs/project/DOCUMENTATION-ROADMAP.md`

**Interfaces:**
- Consumes: `git ls-files -- '*.md'` from the selected repository root and ordered rule objects from `documentation-migration-inventory.json`.
- Produces: `validate_inventory(root: Path, inventory_path: Path) -> list[str]`, CLI exit status `0` for complete coverage, and one effective disposition per tracked Markdown path.

- [ ] **Step 1: Write failing validator tests**

Add tests that:

```python
def test_repository_markdown_inventory_is_complete() -> None:
    result = run_validator(ROOT, INVENTORY)
    assert result.returncode == 0, result.stderr


def test_validator_rejects_an_unclassified_tracked_markdown(tmp_path: Path) -> None:
    repository = initialize_repository(tmp_path, ("notes/unclassified.md",))
    inventory = write_minimal_inventory(repository, rules=())
    result = run_validator(repository, inventory)
    assert result.returncode == 1
    assert "unclassified Markdown path: notes/unclassified.md" in result.stderr


def test_validator_uses_specific_protected_rules_before_broad_docs_rules(
    tmp_path: Path,
) -> None:
    repository = initialize_repository(
        tmp_path,
        ("docs/superpowers/plans/example.md", "docs/public-api.md"),
    )
    inventory = write_inventory_with_protected_precedence(repository)
    result = run_validator(repository, inventory, output_json=True)
    assert json.loads(result.stdout)["dispositions"] == {
        "retain_historical_evidence": 1,
        "translate_polish": 1,
    }
```

The production change each test catches is respectively: an incomplete repository inventory, fail-open handling of a new path, or incorrect precedence that sends protected plans into the translation wave.

- [ ] **Step 2: Run tests to verify RED**

Run:

```console
uv run --locked --extra dev pytest -q tests/test_documentation_migration_inventory.py
```

Expected: collection fails because `scripts/validate_documentation_inventory.py` and the inventory do not exist.

- [ ] **Step 3: Implement the minimal validator and ordered inventory**

Implement a closed JSON schema containing `schema_version`, `issue`, `policy_version`, and ordered `rules`. Each rule has a stable `id`, one `disposition`, a migration `wave`, and exact `paths` and/or directory `prefixes`. The validator must:

```python
def validate_inventory(root: Path, inventory_path: Path) -> list[str]:
    inventory = load_inventory(inventory_path)
    paths = tracked_markdown_paths(root)
    return [
        f"unclassified Markdown path: {path}"
        for path in paths
        if classify_path(path, inventory.rules) is None
    ]
```

Use first-match precedence and document it. Put `.github/**`, `third_party/**`, `docs/superpowers/**`, experiment/data research evidence, and named historical plans before broader `docs/**` translation rules. Do not open or hash any classified document; inspect paths only.

Write `DOCUMENTATION-ROADMAP.md` in Polish. It must describe the policy, precedence, protected categories, migration waves, verification command, and the follow-up-issue table populated in Task 3.

- [ ] **Step 4: Run tests to verify GREEN**

Run:

```console
uv run --locked --extra dev pytest -q tests/test_documentation_migration_inventory.py
uv run --locked --extra dev python scripts/validate_documentation_inventory.py
```

Expected: tests pass and the CLI reports complete Markdown classification with disposition counts.

### Task 2: Align repository governance and the active roadmap

**Files:**
- Modify: `AGENTS.md`
- Modify: `PROMPT.md`
- Modify: `docs/project/ROADMAP.md`
- Verify: `tests/test_product_charter_policy.py`
- Verify: `tests/test_architecture_policy.py`

**Interfaces:**
- Consumes: accepted issue #158, ADR-0020, and the active M6 issue state.
- Produces: Polish-first repository instructions, current branch/PR workflow, and an active roadmap summary that distinguishes M6 from archived M0-M5 evidence.

- [ ] **Step 1: Rewrite `AGENTS.md` as concise Polish governance**

Preserve source precedence, attribution, issue workflow, architecture, quality, dependency, and handoff rules. Add explicit rules for:

```text
- aktywnie utrzymywana dokumentacja autorska jest po polsku;
- kod, identyfikatory, kontrakty maszynowe i metadane GitHub pozostają po angielsku;
- jeden repozytorium zawiera runtime i badania, lecz wheel/sdist nie dziedziczą materiałów badawczych;
- zużyte holdouty i zamrożone dowody są niezmienne;
- korekty pozostają konserwatywne i fail-closed.
```

- [ ] **Step 2: Update `PROMPT.md` without removing requirements**

Add the same language boundary under the agent instructions or documentation section. Replace the early-stage direct-to-`main` workflow with short-lived issue branches and reviewed PRs as the default current workflow. Point planning to `docs/project/ROADMAP.md` and executable acceptance criteria to GitHub issues.

- [ ] **Step 3: Reconcile the active roadmap summary**

Keep the historical M0-M5 tables unchanged as archive evidence. Replace the completed `#120 -> #84 -> #95` active product lane with the current M6 sequence rooted at #149 and link `DOCUMENTATION-ROADMAP.md` as the separate language-migration plan. Do not introduce dependencies between #158 and #149-#155 or the optional research lane.

- [ ] **Step 4: Verify governed-policy checks**

Run:

```console
uv run --locked --extra dev pytest -q tests/test_product_charter_policy.py tests/test_architecture_policy.py
uv run --locked --extra dev python scripts/validate_documentation_inventory.py
```

Expected: all tests and the inventory contract pass.

### Task 3: Publish atomic translation follow-up issues

**Files:**
- Modify: `docs/project/DOCUMENTATION-ROADMAP.md`

**Interfaces:**
- Consumes: the migration waves and protected-category boundary from Tasks 1-2.
- Produces: ordered GitHub issues with `type:docs`, one area label, one priority label, milestone `Runtime 0.x Hardening`, and explicit dependency on #158 where appropriate.

- [ ] **Step 1: Create the README/public-entry issue first**

Create an issue titled `Translate the README and public entry-point guides into Polish` covering only `README.md`, `docs/quick-start.md`, and `docs/limitations.md`, including build/packaging verification because README and limitations ship in distributions.

- [ ] **Step 2: Create independently reviewable later waves**

Create separate issues for:

```text
1. active roadmap and risk-register governance;
2. public API, customization, rules, segmentation, and compatibility guides;
3. privacy and offline guarantees;
4. dependency, distribution, and release documentation;
5. architecture index, Polish ADR summaries, and active design guides without modifying accepted ADRs;
6. maintained evaluation and quality guides;
7. maintained LLM contracts and research workflow guides.
```

Each body must restate protected exclusions and must not authorize corpus, report, holdout, runtime, or source-policy changes.

- [ ] **Step 3: Record the created issue numbers and order**

Replace the migration roadmap's pending entries with the actual issue links, labels, milestone, scope, dependencies, and verification boundary.

- [ ] **Step 4: Re-run inventory validation**

Run:

```console
uv run --locked --extra dev python scripts/validate_documentation_inventory.py
git diff --check
```

Expected: complete classification and no whitespace errors.

### Task 4: Verify, review, and publish issue #158

**Files:**
- Verify all files changed by Tasks 1-3.

**Interfaces:**
- Consumes: the complete issue diff and #158 acceptance checklist.
- Produces: one verified commit, one pushed branch, one reviewed PR, green CI, and issue closure through the merged PR.

- [ ] **Step 1: Run focused and full verification**

Run:

```console
uv run --locked --extra dev pytest -q tests/test_documentation_migration_inventory.py tests/test_product_charter_policy.py tests/test_architecture_policy.py
uv run --locked --extra dev pytest -q -m "not research and not slow and not model"
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
uv run --locked --extra dev python -m build --no-isolation
uv run --locked --extra dev python scripts/verify_distribution_artifacts.py --dist dist
uv run --locked --extra dev python scripts/verify_distribution_install.py --dist dist
uv run --locked --extra dev python scripts/validate_documentation_inventory.py
git diff --check
```

Expected: every command succeeds with no failures or policy violations.

- [ ] **Step 2: Review the complete diff against #158**

Confirm every acceptance criterion has evidence, every Markdown path is classified, protected files are byte-unchanged, and no runtime or packaging-content file changed.

- [ ] **Step 3: Commit and publish**

```console
git add AGENTS.md PROMPT.md docs/project/ROADMAP.md \
  docs/project/DOCUMENTATION-ROADMAP.md \
  docs/project/documentation-migration-inventory.json \
  docs/superpowers/plans/2026-08-04-issue-158-polish-documentation-policy.md \
  scripts/validate_documentation_inventory.py \
  tests/test_documentation_migration_inventory.py
git commit -m "docs: adopt Polish-first documentation policy (#158)"
git push -u origin codex/issue-158-polish-doc-policy
```

Open a ready PR with `Closes #158`, wait for all required checks, obtain independent review, and merge only after the full matrix is green.
