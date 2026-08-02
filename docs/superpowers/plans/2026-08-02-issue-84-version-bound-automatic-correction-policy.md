# Issue #84: Version-bound automatic correction policy implementation plan

> Execute with `superpowers:subagent-driven-development` and
> `superpowers:test-driven-development` in the existing
> `codex/issue-84-runtime-policy` worktree.

**Goal:** Make automatic correction eligibility depend on the exact qualified
source, category, operation, behavior version, and source-policy version while
preserving Finding schema v1 and all currently qualified behavior.

**Architecture:** A new deep `polis.correction.policy` module owns immutable
policy identities and fail-closed eligibility. Registered deterministic rules
optionally expose versioned behavior metadata; the registry is the trusted
source-to-behavior association. `Analyzer` delegates correction eligibility to
the policy and records policy `1.2` in correction outcomes. Installed-runner
evidence observes the runtime version through protocol v2 without mutating the
historical policy-`1.1` report or holdout.

**Constraints:** One GitHub issue, one final focused commit. Do not change
`Finding`, analysis JSON schema v1, quality thresholds, evaluation corpora,
holdout state, model qualification, historical report bytes, or automatic
privilege membership. Use failing tests before each behavior change.

---

## Task 1: Introduce the exact correction-policy key

**Files**

- Create: `src/polis/correction/policy.py`
- Modify: `src/polis/correction/__init__.py`
- Create: `tests/test_automatic_correction_policy.py`

### Step 1: Write failing policy identity tests

Add tests for immutable, value-equal `SourceBehavior` and `SourcePolicyKey`
instances. Freeze the active source-policy version as `1.2` and assert that a
complete known key at its minimum confidence is eligible.

Add a parameterized regression that independently changes:

- source;
- category;
- operation;
- behavior version;
- source-policy version.

Every changed key must be ineligible. Add tests for confidence below threshold,
unknown entries, and `SourceKind.LLM` denial at confidence `1.0`.

Run:

```bash
uv run pytest tests/test_automatic_correction_policy.py -q
```

Expected: RED because the module does not exist.

### Step 2: Implement the smallest deep policy module

Implement frozen, slotted dataclasses with strict non-blank version/operation
validation. Keep active entries private and expose a narrow function such as:

```python
is_automatic_correction_eligible(
    finding: Finding,
    behavior: SourceBehavior | None,
    *,
    source_policy_version: str = SOURCE_POLICY_VERSION,
) -> bool
```

Construct the full key internally. Check `SourceKind.LLM` before lookup. A
missing behavior or any mismatched dimension returns `False`; invalid policy
construction raises locally during import/tests rather than broadening access.

Populate entries for exactly the nine currently automatic sources with their
existing categories and confidence thresholds. Use these exact identities:

| Source | Operation | Behavior version |
| --- | --- | --- |
| `rule:agreement.copula` | `replace.copula_form` | `agreement-copula/1.0` |
| `rule:spelling.jestes` | `replace.common_typo` | `spelling-jestes/1.0` |
| `rule:spelling.wlasnie` | `replace.common_typo` | `spelling-wlasnie/1.0` |
| `rule:spelling.zeby` | `replace.common_typo` | `spelling-zeby/1.0` |
| `rule:syntax.comma_space` | `normalize.comma_spacing` | `syntax-comma-space/1.0` |
| `rule:syntax.list_space` | `normalize.list_marker_spacing` | `syntax-list-space/1.0` |
| `rule:syntax.quote_space` | `normalize.quote_spacing` | `syntax-quote-space/1.0` |
| `rule:syntax.sentence_space` | `normalize.sentence_spacing` | `syntax-sentence-space/1.0` |
| `rule:languagetool.pl` | `check.allowlisted_comma` | `pl-6.8-five-rule-comma/1.0` |

The LanguageTool pair is therefore:

```text
check.allowlisted_comma / pl-6.8-five-rule-comma/1.0
```

Do not add reviewable sources.

### Step 3: Verify GREEN and local quality

Run:

```bash
uv run pytest tests/test_automatic_correction_policy.py -q
uv run ruff check src/polis/correction tests/test_automatic_correction_policy.py
uv run mypy src/polis/correction
```

Expected: all pass.

## Task 2: Bind trusted behavior metadata to registered rules

**Files**

- Modify: `src/polis/core/protocols.py`
- Modify: `src/polis/core/__init__.py`
- Modify: `src/polis/rules/__init__.py`
- Modify: `src/polis/rules/agreement.py`
- Modify: `src/polis/rules/spelling.py`
- Modify: `src/polis/rules/syntax.py`
- Modify: `src/polis/rules/languagetool.py`
- Modify: `src/polis/rules/contextual_inflection.py`
- Modify: `tests/test_protocols.py`
- Modify: `tests/test_rules.py`
- Modify: `tests/test_languagetool_rule.py`

### Step 1: Write failing protocol and registry tests

Test that:

- `VersionedRule` requires the existing rule shape plus `operation` and
  `behavior_version`;
- registry lookup returns exact `SourceBehavior` for a versioned registered
  source;
- lookup returns `None` for an ordinary unversioned third-party rule;
- an unknown source returns `None`;
- registration uniqueness and finding-source validation remain unchanged;
- LanguageTool exposes the exact frozen behavior identity.

Run the selected tests and confirm RED before changing production code.

### Step 2: Add optional versioned-rule metadata

Add `VersionedRule` without broadening the existing `Rule` protocol. Give each
built-in deterministic rule immutable class-level or read-only metadata.
Behavior versions are exact source-specific values ending in `/1.0`; do not use
one generic shared version that hides which rule changed.

Add registry lookup that derives `SourceBehavior` only from the registered rule
object after its source has been uniquely validated. Do not read metadata from
`Finding`, source-name parsing, configuration, or serialized input.

Contextual inflection and residual syntax may expose metadata for
observability, but remain absent from the automatic policy.

### Step 3: Verify the registry slice

Run:

```bash
uv run pytest tests/test_protocols.py tests/test_rules.py \
  tests/test_languagetool_rule.py -q
uv run ruff check src/polis/core src/polis/rules tests/test_protocols.py \
  tests/test_rules.py tests/test_languagetool_rule.py
uv run mypy src/polis/core src/polis/rules
```

Expected: all pass.

## Task 3: Route automatic correction through the complete key

**Files**

- Modify: `src/polis/analyzer.py`
- Modify: `tests/test_conservative_correction.py`
- Modify: `tests/test_analyzer_languagetool_config.py`
- Modify: `tests/test_suggestion_outcomes.py`

### Step 1: Write source-name-only and version-drift regressions

Add tests that construct or inject a deterministic rule with the same qualified
source and category but a changed operation or behavior version. Its finding
must remain unchanged in `skipped_findings`. Add a same-source unversioned rule
case and an exact-qualified behavior control case.

Retain explicit tests for every existing automatic built-in source and the
five-ID LanguageTool path. Confirm model-derived edits remain reviewable at
confidence `1.0`.

Run the focused tests and verify RED because analyzer lookup is source-only.

### Step 2: Replace analyzer-local policy lookup

Remove `_POLICY_BY_SOURCE`, `AutomaticCorrectionPolicy`, and the analyzer-local
policy literals. Resolve behavior through `DeterministicRuleRegistry`, call the
deep correction-policy function, then perform the existing conflict check.

Do not change normalization order, offsets, finding identity, explicit
selection, or exception behavior.

Add `source_policy_version` to `CorrectionResult` and populate it from the
active policy. Make every `SuggestionOutcome` receive the same policy version
explicitly from that source of truth.

### Step 3: Verify correction routing

Run:

```bash
uv run pytest tests/test_automatic_correction_policy.py \
  tests/test_conservative_correction.py \
  tests/test_analyzer_languagetool_config.py \
  tests/test_suggestion_outcomes.py -q
```

Expected: all pass; qualified text outputs remain unchanged while every drift
case is reviewable.

## Task 4: Preserve public compatibility while exposing policy identity

**Files**

- Modify: `tests/typecheck/stubs/polis/__init__.pyi`
- Modify: `tests/typecheck/api_contract_examples.py`
- Modify: `tests/test_api_compatibility.py`
- Modify: `tests/test_public_models.py`
- Modify: `tests/fixtures/public_api_snapshot.json` only if the additive public
  `CorrectionResult` attribute is represented there

### Step 1: Add failing compatibility assertions

Assert that:

- `CorrectionResult.source_policy_version == "1.2"` is typed and public;
- `SuggestionOutcome.source_policy_version` agrees with its containing result;
- canonical `AnalysisResult.to_json()` output remains byte-identical for the
  existing fixture;
- strict Finding schema-v1 field sets remain unchanged;
- no correction-policy internals become package-root public API unless required
  by the implementation.

Run the selected runtime and typecheck tests; confirm the new result attribute
is RED while schema-v1 assertions already pass.

### Step 2: Update only the additive API surface

Update stubs and examples for the new `CorrectionResult` field. Do not add a
correction-result serializer and do not change `Finding`, its stable ID, or
analysis serialization.

### Step 3: Verify compatibility

Run:

```bash
uv run pytest tests/test_api_compatibility.py tests/test_public_models.py -q
uv run mypy tests/typecheck/api_contract_examples.py
```

Expected: all pass and schema v1 bytes remain stable.

## Task 5: Make installed runtime evidence observe policy `1.2`

**Files**

- Modify: `scripts/run_sentence_safety_case.py`
- Modify: `experiments/sentence_safety_gate/gate.py`
- Modify: `experiments/sentence_safety_gate/run_evaluation.py`
- Modify: `tests/test_sentence_safety_runner.py`
- Modify: `tests/test_sentence_safety_gate.py`
- Modify: `tests/test_sentence_safety_installation.py`
- Do not modify: `experiments/sentence_safety_gate/report.json`
- Do not modify: evaluation corpus, approval, freeze, reservation, or holdout
  files

### Step 1: Write failing protocol-v2 evidence tests

Add tests for:

- runner request/response schema version 2;
- required top-level `source_policy_version` in complete responses;
- response value taken from `CorrectionResult`;
- validator rejection of a missing, unknown, or config-mismatched version;
- repeated runtime observations disagreeing on version;
- report environment taking the validated observed runtime version;
- installed wheel response exposing `1.2`.

Keep a test proving the committed historical report remains valid report schema
version 1 and retains policy `1.1` bytes/identity.

Run the focused tests and verify RED before implementation.

### Step 2: Implement protocol and observation changes

Advance only the installed runner request/response protocol constant to 2 and
update its caller. Emit top-level runtime policy identity. Extend
`RunnerObservation` with the validated value and require all observations in a
new evaluation run to agree with each other and with its config.

Keep the evaluation report schema at 1. For newly generated reports, derive
`environment.source_policy_version` from observations after agreement checks;
do not copy it solely from config. Preserve historical report validation as a
separate path.

Do not execute `authorize_holdout`, `reserve_holdout_once`, a real runner over
the holdout split, or any command that can consume holdout state.

### Step 3: Verify evidence without consuming research data

Run only named tests that use synthetic responses, development fixtures, or
installed smoke cases:

```bash
uv run pytest tests/test_sentence_safety_runner.py \
  tests/test_sentence_safety_gate.py \
  tests/test_sentence_safety_installation.py -q
```

If repository markers would select a holdout-consuming test, run explicit node
IDs instead and document the exclusion. Expected: all selected tests pass; no
tracked evidence file changes.

## Task 6: Update policy documentation and architecture guards

**Files**

- Modify: `docs/architecture/decisions/0008-hybrid-correction-policy.md`
- Modify: `docs/public-api.md`
- Modify: `docs/rules.md`
- Modify: `docs/llm-quality-gates.md`
- Modify: `docs/limitations.md`
- Modify: `docs/compatibility.md`
- Modify: `tests/test_hybrid_architecture_policy.py`
- Modify: documentation policy tests only where required

### Step 1: Update documentation

Add ADR-0008 implementation notes rather than rewriting its historical
decision. Update public API and rule descriptions from source-policy `1.1` to
the active `1.2` enforcement contract while clearly preserving the historical
qualification record. Keep limitations factual and do not claim broader
LanguageTool or model support.

Do not add tests that grep or freeze human prose. The behavior and API tests in
Tasks 1 through 5 are the executable architecture guards; existing repository
documentation-policy tests remain regression checks only.

### Step 2: Verify docs and architecture policy

Run:

```bash
uv run pytest tests/test_hybrid_architecture_policy.py \
  tests/test_languagetool_stdio_documentation.py -q
uv run ruff check .
uv run ruff format --check .
uv run mypy .
```

Expected: all pass.

## Task 7: Full verification, independent review, and one-commit handoff

### Step 1: Verify protected files are unchanged

Confirm no diff exists for:

- `experiments/sentence_safety_gate/report.json`;
- corpus and approval fixtures;
- holdout reservation/freeze artifacts;
- model or finetuning data.

Run `git diff --check` and inspect the complete diff.

### Step 2: Run the full fast product matrix

Use the repository's fast-CI selectors rather than real-model or holdout runs.
At minimum run:

```bash
uv run pytest -m "not research and not slow" -q
uv run ruff check .
uv run ruff format --check .
uv run mypy .
```

Also collect research tests without execution if needed to catch import errors:

```bash
uv run pytest -m research --collect-only -q
```

### Step 3: Independent reviews

Use separate subagents for:

1. spec and acceptance-criteria compliance;
2. code quality, API compatibility, and fail-closed security review.

Resolve every blocking or high-confidence finding with a new failing regression
test before implementation changes. Re-run the affected slice and full fast
matrix.

### Step 4: Produce one focused issue commit

Task implementers may create temporary reviewed commits as required by the SDD
workflow. Do not push before consolidation. After all reviews and verification,
resolve the explicit merge base, soft-reset only this short-lived feature branch
to that exact commit, and create one replacement commit so #84 remains one
focused commit while all working-tree content and staged changes are preserved:

```bash
ISSUE84_BASE=$(git merge-base main HEAD)
test "$ISSUE84_BASE" = "$(git rev-parse main)"
git reset --soft "$ISSUE84_BASE"
git commit -m "fix: bind automatic correction to behavior versions (#84)"
```

This history rewrite is limited to the unpushed `codex/issue-84-runtime-policy`
branch and preserves all files in the index. Do not add co-author or automation
attribution. Verify the resulting branch is exactly one commit ahead of `main`
and that the commit message references #84.

### Step 5: Publish and integrate

Push `codex/issue-84-runtime-policy`, open a focused PR linked to #84, wait for
all required CI checks, address review feedback, and merge only when green.
After merge, verify #84 acceptance criteria against `main`, close the issue with
one evidence-backed completion comment if GitHub did not close it, update local
`main`, and remove the completed worktree and safely deletable feature branch.

## Final acceptance checklist

- [ ] Complete five-dimensional policy key is enforced.
- [ ] Each individual version or identity drift fails closed.
- [ ] Existing qualified behavior remains automatic only at exact versions.
- [ ] Unknown and unversioned rules remain reviewable.
- [ ] Model edits remain reviewable regardless of confidence.
- [ ] `CorrectionResult` and suggestion outcomes expose policy `1.2`.
- [ ] Installed runtime evidence observes and validates policy identity.
- [ ] Finding and analysis JSON schema v1 are unchanged.
- [ ] Historical report, holdout, corpora, and thresholds are unchanged.
- [ ] Required focused, fast, lint, format, type, and collection checks pass.
- [ ] Branch contains one focused commit for #84.
