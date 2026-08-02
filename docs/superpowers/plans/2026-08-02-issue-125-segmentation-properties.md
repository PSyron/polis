# Generated Segmentation Reconstruction Properties Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic generated properties that guard paragraph and sentence span reconstruction without changing segmentation behaviour.

**Architecture:** A test module consumes #123's fixed 64-case Unicode generator and checks real segmenters' ordered half-open spans, source slices, and exact reconstruction. A test-local helper uses the harness's replay-safe assertion path; documentation records this structural-only guardrail.

**Tech Stack:** Python 3.12+, existing `polis.segmentation`, `tests.generative`, pytest, Ruff, and mypy.

## Global Constraints

- Implement only GitHub issue #125 and consume the already accepted #123 deterministic bounded harness.
- Preserve Unicode code-point half-open offsets `[start, end)`, exact original-text reconstruction, offline privacy, all public contracts, and authored linguistic regressions.
- Use only the harness default `unicode-structural-v1` generator, seed `95001`, and 64-case bounded budget; do not read ambient configuration or add a dependency.
- Generated failures must contain a stable invariant identifier and replay metadata, never generated or analyzed text.
- Do not change production segmentation behaviour; stop for a separate regression-first bug issue if a property exposes a defect.
- Do not change #119, corpora, holdouts, model qualification, production dependencies, attribution, or unrelated files.
- Finish as one focused commit referencing `#125`; do not push, create a PR, merge, comment on, or close an issue.

---

### Task 1: Add the generated structural guardrail and documentation

**Files:**

- Create: `tests/test_segmentation_properties.py`
- Modify: `docs/segmentation.md`
- Create: `docs/superpowers/specs/2026-08-02-issue-125-segmentation-properties-design.md`
- Create: `docs/superpowers/plans/2026-08-02-issue-125-segmentation-properties.md`

**Interfaces:**

- Consumes: `segment_paragraphs(text: str) -> tuple[Paragraph, ...]`, `segment_sentences(text: str) -> tuple[Sentence, ...]`, `generate_unicode_text_cases()`, `UNICODE_FAMILIES`, and `assert_structural_invariant(condition, invariant, replay)`.
- Produces: bounded pytest coverage for `segmentation.paragraph.*` and `segmentation.sentence.*` invariants plus documentation of its non-linguistic scope.

- [x] **Step 1: Write the failing generated-property test**

Create `tests/test_segmentation_properties.py` with this initial test body. The missing `_assert_generated_segmentation` is deliberate: it is the absent generated safeguard. The protected production mutation is any segmenter returning an omitted, reordered, out-of-bounds, or stale-text span while authored linguistic examples still pass.

```python
from __future__ import annotations

from polis.segmentation import segment_paragraphs, segment_sentences


def test_generated_paragraph_spans_reconstruct_the_original_source() -> None:
    _assert_generated_segmentation(kind="paragraph", segmenter=segment_paragraphs)


def test_generated_sentence_spans_reconstruct_the_original_source() -> None:
    _assert_generated_segmentation(kind="sentence", segmenter=segment_sentences)
```

- [x] **Step 2: Run the focused test and verify RED**

Run `uv run --locked --extra dev pytest tests/test_segmentation_properties.py -v`. Both tests must fail with `NameError` for `_assert_generated_segmentation`, proving the #123-generated structural safeguard does not yet exist. Record the command, failure type, and test count before adding the helper. If either real segmenter later fails a structural invariant, stop and report its replay metadata for a new regression-first bug issue.

- [x] **Step 3: Add the minimal replay-safe test helper**

Extend the test module with a `Callable[[str], tuple[Segment, ...]]` `segmenter` parameter and imports of `Segment`, `UNICODE_FAMILIES`, `assert_structural_invariant`, and `generate_unicode_text_cases`. For the default cases, first assert their family union equals `UNICODE_FAMILIES` with replay from `cases[-1]`. For every case and real returned segment, use `assert_structural_invariant` with invariant names `segmentation.<kind>.bounds`, `.contiguous`, `.slice`, `.coverage`, and `.reconstruction` to check `0 <= start <= end <= len(source)`, `start == previous_end`, `segment.text == source[start:end]`, final `previous_end == len(source)`, and joined segment text equal to source. Keep final coverage check so empty input and omitted-tail mutations are observable. Do not add a production helper or modify a segmenter.

- [x] **Step 4: Run focused and existing segmentation tests to verify GREEN**

Run `uv run --locked --extra dev pytest tests/test_segmentation_properties.py tests/test_segmentation.py -v`. Both generated properties and every authored segmentation regression must pass. A generated property failure is a stop condition; do not repair the segmenter in this issue.

- [x] **Step 5: Update segmentation documentation**

Add a `## Generated structural guardrail` section after parsing behaviour. State that #125 runs the #123 bounded synthetic generator through both segmenters; checks bounded, ordered, contiguous Unicode-code-point `[start, end)` spans, exact source slices, and exact reconstruction; covers all eight declared Unicode/line-ending families including empty input; reports only invariant plus replay metadata; and does not change heuristics or claim linguistic coverage. Link `development/generative-invariants.md` for the generator/replay contract.

- [x] **Step 6: Self-review and verify the issue boundary**

Run `git diff --check`, `git diff -- src/polis`, `git status --short`, and `rg -n "TBD|TODO" docs/segmentation.md tests/test_segmentation_properties.py`. Expect no whitespace errors, no `src/polis` diff, no placeholders, and only the four issue files changed. Review every acceptance criterion before commit.

- [x] **Step 7: Run required verification**

```bash
uv run --locked --extra dev pytest tests/test_segmentation_properties.py tests/test_segmentation.py -v
uv run --locked --extra dev pytest -m "not research and not slow and not model"
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
git diff --check
```

Every command must exit zero. Do not commit if a generated property finds a production segmentation defect; preserve replay metadata and stop.

- [x] **Step 8: Write the handoff report and create one focused commit**

Write `.superpowers/sdd/issue-125-agent-report.md` with design/plan paths, RED and GREEN evidence, changed files, all command results, acceptance review, self-review, and risks. Stage only the four issue files and commit `test: add segmentation reconstruction properties (#125)`. Keep the report untracked. Do not push, create a pull request, merge, or mutate GitHub.

## Plan self-review

- The task covers every #125 criterion: family union, empty input, replay-safe failures, both segmenters, authored-regression preservation, and documentation.
- There are no placeholders; every step names concrete files, checks, and commands.
- The test consumes exact #123 exports and existing segmentation types; it adds no public interface.
- Production repair is explicitly excluded and would require a separate bug issue.
