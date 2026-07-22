# LanguageTool Polish Rule Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inventory and qualify additional deterministic LanguageTool 6.8 Polish rules for one-sentence correction without broadening production behavior.

**Architecture:** An explicit experiment-only stdio operation exposes unfiltered upstream matches. A gold-isolated Python scorer normalizes every replacement, evaluates rules independently and combined, and freezes only a non-empty precision-1.00 allowlist before any one-shot holdout.

**Tech Stack:** Java 17, LanguageTool 6.8, newline-delimited JSON stdio, Python 3.12+, pytest, existing corpus-v3 evaluation models.

## Global Constraints

- Preserve the default `check` response and two-rule allowlist exactly.
- Process sentence cases only; paragraphs are out of scope.
- Keep routing inputs free of IDs, labels, tags, expected output, and gold spans.
- Count every replacement offered by a rule; never select with gold.
- Require per-rule and combined precision 1.00 with zero protected-negative changes.
- Keep raw text/responses and runtime artifacts outside committed evidence.

---

### Task 1: Isolate the Java inspection operation

**Files:**
- Modify: `third_party/languagetool-pl/src/main/java/org/polis/languagetool/PolisStdioServer.java`
- Modify: `tests/test_languagetool_vendor_artifacts.py`
- Modify: `tests/test_languagetool_vendor_runtime.py`

- [x] Add failing static and opt-in runtime tests proving `inspect` emits a rule outside the two-rule allowlist while default `check` cannot emit it.
- [x] Run the focused tests and confirm the operation is absent.
- [x] Add the closed `inspect` request, response marker, and unfiltered check path without modifying synthesis or default filtering.
- [x] Build offline and require both isolation tests to pass.

### Task 2: Implement gold-isolated inventory and exact scoring

**Files:**
- Create: `experiments/languagetool_rule_inventory/__init__.py`
- Create: `experiments/languagetool_rule_inventory/config.json`
- Create: `experiments/languagetool_rule_inventory/experiment.py`
- Create: `experiments/languagetool_rule_inventory/run_benchmark.py`
- Create: `tests/test_languagetool_rule_inventory.py`

- [x] Add failing tests for sentence-only loading, routing-input leakage, closed inspection responses, UTF-16 conversion, all-replacement normalization, per-rule TP/FP/FN, combined conflicts, and protected negatives.
- [x] Run the focused tests and confirm the experiment package is absent.
- [x] Implement immutable inputs, the persistent local stdio client, normalization, scoring, and identifier-only observations.
- [x] Require focused pytest, Ruff, and mypy to pass.

### Task 3: Freeze selection, privacy, and holdout-once policy

**Files:**
- Modify: `experiments/languagetool_rule_inventory/experiment.py`
- Modify: `experiments/languagetool_rule_inventory/run_benchmark.py`
- Modify: `tests/test_languagetool_rule_inventory.py`

- [x] Add failing tests for at-least-one-TP selection, precision 1.00, zero protected changes, combined validation, configuration hashing, private reports, atomic freezing, and one-shot holdout reservation.
- [x] Implement the minimal deterministic selector and guards.
- [x] Rerun all inventory tests and require complete success.

### Task 4: Run development and record the decision

**Files:**
- Create: `experiments/languagetool_rule_inventory/README.md`
- Create: `experiments/languagetool_rule_inventory/report.json`
- Create: `docs/architecture/decisions/0014-qualify-or-reject-broader-polish-rules.md`
- Modify: `docs/project/ROADMAP.md`
- Modify: `docs/limitations.md`

- [x] Build the pinned module offline and run the 69-case development inventory.
- [x] Freeze and run holdout once only if a non-empty allowlist passes every development gate.
- [x] Record exact rule metrics, performance/resources, privacy evidence, and the #43 consequence.
- [x] Run full Ruff, format, mypy, pytest, distribution, and opt-in LanguageTool checks.
- [x] Create and push one focused commit `research: inventory Polish LanguageTool rules (#70)` and close #70 only with complete evidence.
