# GitHub Project Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Configure the repository and GitHub project metadata for issue-driven delivery of the Polis roadmap.

**Architecture:** Repository policy lives in versioned Markdown and GitHub issue forms. An idempotent standard-library Python bootstrap owns the exact milestone, label, and issue definitions, invokes `gh`, resolves dependency keys to created issue links, and verifies remote state after writes.

**Tech Stack:** Markdown, YAML issue forms, Python 3 standard library, GitHub CLI, GitHub REST API.

## Global Constraints

- GitHub metadata, technical documentation, issue bodies, and `AGENTS.md` use English.
- `PROMPT.md` remains the product source of truth, with product requirements unchanged.
- Repository-authored content must not name automated tooling or claim that it performs work.
- The repository owner is `PSyron`, and Paweł Cyroń is the sole credited author; do not add tool attribution, co-author trailers, or generation disclosures.
- The backlog contains exactly 32 independently verifiable roadmap issues across milestones M0-M4.
- Every roadmap issue has one milestone, one `type:*` label, one `area:*` label, and one `priority:*` label.
- Bootstrap operations are idempotent and stop on failed GitHub operations.
- No analyzer implementation, model selection, dependency selection, Python support range, or quality threshold is introduced by this plan.

---

### Task 1: Repository governance and issue forms

**Files:**
- Create: `.gitignore`
- Create: `AGENTS.md`
- Create: `.github/ISSUE_TEMPLATE/task.yml`
- Create: `.github/ISSUE_TEMPLATE/bug.yml`
- Create: `.github/ISSUE_TEMPLATE/decision.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Modify: `PROMPT.md`

**Interfaces:**
- Consumes: approved rules in `docs/superpowers/specs/2026-07-20-github-project-planning-design.md`.
- Produces: contributor policy and structured GitHub forms used by future issues and pull requests.

- [x] **Step 1: Confirm the validation starts red**

Run:

```bash
test -f .gitignore && test -f AGENTS.md && test -f .github/ISSUE_TEMPLATE/task.yml
```

Expected: non-zero exit because the files do not exist.

- [x] **Step 2: Create the governance files**

Create the files listed above with these exact responsibilities:

```text
.gitignore: Python/cache/build/editor/macOS/local-model/local-corpus exclusions
AGENTS.md: source precedence, issue workflow, scope, tests, privacy, handoff
task.yml: goal, rationale, scope, non-goals, acceptance, tests, docs, dependencies
bug.yml: observed/expected behavior, reproduction, regression test, privacy-safe logs
decision.yml: question, options, evidence, decision criteria, artifact
config.yml: blank issues disabled, security link to repository guidance
PULL_REQUEST_TEMPLATE.md: issue, scope, acceptance, tests, privacy, docs checklist
```

Change only the two tool-specific headings in `PROMPT.md` to use `agenta`; do not alter product requirements.

- [x] **Step 3: Validate structure and prohibited wording**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
required = [
    Path('.gitignore'), Path('AGENTS.md'),
    Path('.github/ISSUE_TEMPLATE/task.yml'),
    Path('.github/ISSUE_TEMPLATE/bug.yml'),
    Path('.github/ISSUE_TEMPLATE/decision.yml'),
    Path('.github/ISSUE_TEMPLATE/config.yml'),
    Path('.github/PULL_REQUEST_TEMPLATE.md'),
]
assert all(path.is_file() for path in required)
for path in required + [Path('PROMPT.md')]:
    forbidden = bytes((99, 111, 100, 101, 120)).decode()
    assert forbidden not in path.read_text().lower(), path
PY
```

Expected: exit 0 with no output.

### Task 2: Versioned roadmap, risks, and bootstrap data

**Files:**
- Create: `docs/project/ROADMAP.md`
- Create: `docs/project/RISKS.md`
- Create: `scripts/bootstrap_github.py`

**Interfaces:**
- Consumes: 32 roadmap entries and taxonomy from the approved design.
- Produces: `MILESTONES`, `LABELS`, and `ISSUES` constants; `--dry-run`, `--apply`, and `--verify` commands.

- [x] **Step 1: Write a failing bootstrap-data check**

Run:

```bash
python3 scripts/bootstrap_github.py --verify-data
```

Expected: failure because `scripts/bootstrap_github.py` does not exist.

- [x] **Step 2: Create roadmap and risk documentation**

`ROADMAP.md` must list every planning key, title, milestone, labels, dependencies, and completion rule. `RISKS.md` must assign each unresolved risk to an issue key and state impact plus mitigation.

- [x] **Step 3: Implement the idempotent bootstrap**

The script must expose this command contract:

```text
python3 scripts/bootstrap_github.py --verify-data
python3 scripts/bootstrap_github.py --dry-run --repo PSyron/polis
python3 scripts/bootstrap_github.py --apply --repo PSyron/polis
python3 scripts/bootstrap_github.py --verify --repo PSyron/polis
```

Use immutable records with these fields:

```python
@dataclass(frozen=True)
class Milestone:
    title: str
    description: str

@dataclass(frozen=True)
class Label:
    name: str
    color: str
    description: str

@dataclass(frozen=True)
class Issue:
    key: str
    title: str
    goal: str
    rationale: str
    scope: tuple[str, ...]
    non_goals: tuple[str, ...]
    acceptance: tuple[str, ...]
    tests: tuple[str, ...]
    documentation: tuple[str, ...]
    dependencies: tuple[str, ...]
    milestone: str
    labels: tuple[str, str, str]
```

`--verify-data` must assert five unique milestones, the complete label taxonomy, 32 unique issue keys and titles, valid dependency keys, acyclic dependencies, and the required label categories. `--apply` must look up exact names before creating or updating metadata. Issue bodies must resolve planning keys to Markdown links when dependencies already exist.

- [x] **Step 4: Run local data validation and dry run**

Run:

```bash
python3 scripts/bootstrap_github.py --verify-data
python3 scripts/bootstrap_github.py --dry-run --repo PSyron/polis
```

Expected: both commands exit 0; dry run reports 5 milestones, 20 taxonomy labels, and 32 issues without writing remote state.

### Task 3: Apply GitHub metadata

**Files:**
- No repository file changes.

**Interfaces:**
- Consumes: authenticated `gh`, repository `PSyron/polis`, and validated bootstrap definitions.
- Produces: five milestones, normalized labels, and 32 open roadmap issues on GitHub.

- [x] **Step 1: Confirm target and authentication**

Run:

```bash
gh auth status
gh repo view PSyron/polis --json nameWithOwner,hasIssuesEnabled,visibility
git config user.name
git config user.email
```

Expected: authenticated as `PSyron`; repository resolves to `PSyron/polis` with issues enabled; Git identity belongs to Paweł Cyroń.

- [x] **Step 2: Apply the metadata**

Run:

```bash
python3 scripts/bootstrap_github.py --apply --repo PSyron/polis
```

Expected: exit 0; output distinguishes created, updated, and unchanged resources and reports no duplicate exact titles.

- [x] **Step 3: Verify remote state**

Run:

```bash
python3 scripts/bootstrap_github.py --verify --repo PSyron/polis
```

Expected: exit 0 and summary `5 milestones, 20 taxonomy labels, 32 roadmap issues verified`.

### Task 4: Final repository verification and commit

**Files:**
- Modify: `docs/superpowers/specs/2026-07-20-github-project-planning-design.md`
- Create: `docs/superpowers/plans/2026-07-20-github-project-bootstrap.md`

**Interfaces:**
- Consumes: completed local files and verified GitHub metadata.
- Produces: a reviewable planning commit containing only repository bootstrap assets.

- [x] **Step 1: Record the no-name rule in the design**

Add the approved rule that repository-authored content must not name automated tooling or claim it performs work.

- [x] **Step 2: Validate all local assets**

Run:

```bash
python3 scripts/bootstrap_github.py --verify-data
python3 scripts/bootstrap_github.py --verify --repo PSyron/polis
git check-ignore .DS_Store .venv model.gguf benchmarks/results.json
rg -ni '[cC][oO][dD][eE][xX]' --glob '!.git/**' .
git diff --check
```

Expected: bootstrap checks pass; all sample artifacts are ignored; `rg` returns exit 1 with no matches; `git diff --check` returns no output.

- [x] **Step 3: Review scope and commit**

Run:

```bash
git status --short
git diff --stat
git add .gitignore AGENTS.md PROMPT.md .github docs/project scripts/bootstrap_github.py docs/superpowers
git diff --cached --check
git commit -m "chore: bootstrap GitHub project planning"
```

Expected: commit succeeds and excludes `.DS_Store`.
