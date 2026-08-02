# Deterministic Unicode Property Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the versioned, bounded, synthetic Unicode generator and privacy-safe replay contract required by issue #123.

**Architecture:** A test-only helper derives each case independently from SHA-256 of an explicit generator version, seed, and case index. Immutable cases hide generated text from representations, and one assertion helper emits only a validated invariant name plus replay metadata.

**Tech Stack:** Python 3.12+, standard-library `dataclasses`, `hashlib`, and `re`; pytest; Ruff; mypy.

## Global Constraints

- Implement only GitHub issue #123; later #95 children own all structural properties that consume this harness.
- Preserve public contracts, offline privacy, Unicode half-open offsets `[start, end)`, fail-closed correction policy, and existing linguistic behavior.
- Generated data must be synthetic, deterministic, time-bounded, and reproducible using generator version `unicode-structural-v1`, seed `95001`, and case index.
- Use `DEFAULT_CASES = 64` and `MAX_CASES = 256`; do not read an ambient seed or budget in this issue.
- Failure messages and object representations must not print generated/analyzed text.
- Add no production dependency, production module, model/holdout evaluation, corpus change, abstraction without a current test consumer, co-author, automation attribution, or tool signature.
- One issue equals one focused commit and one separate PR.

---

### Task 1: Implement and document the deterministic test harness

**Files:**
- Create: `tests/generative.py`
- Create: `tests/test_generative_harness.py`
- Create: `docs/development/generative-invariants.md`
- Verify: `docs/superpowers/specs/2026-08-02-deterministic-unicode-property-harness-design.md`
- Verify: `docs/superpowers/plans/2026-08-02-issue-123-deterministic-unicode-harness.md`

**Interfaces:**
- Consumes: Python standard-library SHA-256 and the accepted issue #123/design constraints.
- Produces: `GENERATOR_VERSION`, `DEFAULT_SEED`, `DEFAULT_CASES`, `MAX_CASES`, `UNICODE_FAMILIES`, `Replay`, `SyntheticTextCase`, `generate_unicode_text_cases`, and `assert_structural_invariant` for later #95 test children.

- [ ] **Step 1: Write the failing test for the missing test-support API**

Create `tests/test_generative_harness.py`. Import every produced symbol from
`tests.generative`, then add focused tests with these observable expectations:

```python
from __future__ import annotations

import pytest

from tests.generative import (
    DEFAULT_CASES,
    DEFAULT_SEED,
    GENERATOR_VERSION,
    MAX_CASES,
    UNICODE_FAMILIES,
    Replay,
    assert_structural_invariant,
    generate_unicode_text_cases,
)


def test_generated_cases_are_reproducible_and_seeded() -> None:
    first = generate_unicode_text_cases(seed=DEFAULT_SEED, count=DEFAULT_CASES)
    repeated = generate_unicode_text_cases(seed=DEFAULT_SEED, count=DEFAULT_CASES)
    different = generate_unicode_text_cases(seed=DEFAULT_SEED + 1, count=DEFAULT_CASES)

    assert first == repeated
    assert tuple(case.text for case in first) != tuple(case.text for case in different)
    assert len(first) == DEFAULT_CASES
    assert first[0].text == ""
    assert first[0].families == frozenset()


def test_default_run_covers_every_supported_unicode_family() -> None:
    cases = generate_unicode_text_cases()

    assert frozenset().union(*(case.families for case in cases)) == UNICODE_FAMILIES
    for case in cases:
        assert case.replay.generator_version == GENERATOR_VERSION
        assert case.replay.seed == DEFAULT_SEED


@pytest.mark.parametrize("count", [1, 8, MAX_CASES])
def test_generator_returns_the_exact_bounded_count(count: int) -> None:
    cases = generate_unicode_text_cases(count=count)

    assert len(cases) == count
    assert [case.replay.case_index for case in cases] == list(range(count))


@pytest.mark.parametrize("count", [0, -1, MAX_CASES + 1])
def test_generator_rejects_out_of_range_budgets(count: int) -> None:
    with pytest.raises(ValueError):
        generate_unicode_text_cases(count=count)


@pytest.mark.parametrize("count", [True, 1.5, "1"])
def test_generator_rejects_non_integer_budgets(count: object) -> None:
    with pytest.raises(TypeError):
        generate_unicode_text_cases(count=count)  # type: ignore[arg-type]


@pytest.mark.parametrize("seed", [-1, 2**64])
def test_generator_rejects_out_of_range_seeds(seed: int) -> None:
    with pytest.raises(ValueError):
        generate_unicode_text_cases(seed=seed)


@pytest.mark.parametrize("seed", [True, 1.5, "1"])
def test_generator_rejects_non_integer_seeds(seed: object) -> None:
    with pytest.raises(TypeError):
        generate_unicode_text_cases(seed=seed)  # type: ignore[arg-type]


def test_replay_and_failures_do_not_expose_generated_text() -> None:
    sentinel = "PRIVATE_SENTINEL"
    replay = Replay(GENERATOR_VERSION, DEFAULT_SEED, 7)
    case = generate_unicode_text_cases(seed=DEFAULT_SEED, count=8)[7]
    object.__setattr__(case, "text", sentinel)

    assert sentinel not in repr(case)
    assert sentinel not in repr(replay)
    with pytest.raises(AssertionError) as error:
        assert_structural_invariant(
            False,
            invariant="harness.privacy",
            replay=replay,
        )
    assert sentinel not in str(error.value)
    assert str(replay) in str(error.value)


def test_invariant_name_must_be_a_safe_identifier() -> None:
    replay = Replay(GENERATOR_VERSION, DEFAULT_SEED, 0)
    with pytest.raises(ValueError):
        assert_structural_invariant(False, invariant="private text", replay=replay)
```

Before keeping the sentinel test, name the mutation it catches: adding `text`
back to `SyntheticTextCase.__repr__` or interpolating case text into the shared
failure path must make it fail.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
uv run --locked --extra dev pytest tests/test_generative_harness.py -v
```

Expected: collection fails because `tests.generative` does not exist. Do not
write the helper until this missing-contract failure is observed and recorded.

- [ ] **Step 3: Implement the minimal versioned hash-indexed generator**

Create `tests/generative.py` with frozen, slotted data classes. Use these exact
constants and safe invariant pattern:

```python
GENERATOR_VERSION = "unicode-structural-v1"
DEFAULT_SEED = 95001
DEFAULT_CASES = 64
MAX_CASES = 256
_MAX_SEED = 2**64 - 1
_SAFE_INVARIANT = re.compile(r"[a-z][a-z0-9_.-]{0,63}\Z")
```

Define this exact ordered, project-authored family catalog and export its keys
as `UNICODE_FAMILIES`:

```python
_FAMILY_FRAGMENTS = (
    ("ascii", "Ala ma kota"),
    ("polish_diacritics", "Zażółć gęślą jaźń"),
    ("non_bmp", "🙂𐍈"),
    ("combining_marks", "e\u0301"),
    ("lf", "\n"),
    ("crlf", "\r\n"),
    ("punctuation", ".?!,;:—"),
    ("quotes", '"„”«»'),
)
```

`Replay` validates exact current `GENERATOR_VERSION`, seed range/type, and
non-negative integer `case_index`. Its `__str__` returns exactly:

```text
generator=unicode-structural-v1 seed=<seed> case=<case_index>
```

`SyntheticTextCase` stores `text` with `field(repr=False)`, validates its
`Replay`, `frozenset[str]` family subset, and string text, and exposes no custom
serialization.

`generate_unicode_text_cases` validates seed and count before generation. For
index zero it returns the empty case. For every later index:

1. compute `sha256(f"{GENERATOR_VERSION}:{seed}:{index}".encode("ascii")).digest()`;
2. include the mandatory family at `(index - 1) % len(family_order)`;
3. include family `family_index` when `digest[family_index] % 3 == 0`, then add
   the mandatory family if it was not selected;
4. repeat each selected fragment `1 + digest[8 + family_index] % 2` times;
5. order selected family indexes by
   `(digest[16 + family_index], family_index)`;
6. join ordered fragments with separators selected from `("", " ", "\t")`
   using `digest[24 + position % 8] % 3` for each join position;
7. return exactly `count` immutable cases in ascending case-index order.

Keep the derivation local and direct; do not add an extensible strategy class or
production abstraction. `assert_structural_invariant` requires an actual
`bool`, validates the invariant name and `Replay`, returns normally for true
conditions, and otherwise raises `AssertionError` with exactly:

```text
structural invariant failed: <invariant>; <Replay.__str__ output>
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run:

```bash
uv run --locked --extra dev pytest tests/test_generative_harness.py -v
```

Expected: all harness tests pass with no warnings or text-bearing failure
output.

- [ ] **Step 5: Write the development documentation**

Create `docs/development/generative-invariants.md` with:

- the issue #95/#123 scope and repository-owned hash-indexed decision;
- rejected Hypothesis and `random.Random` alternatives and why;
- generator version `unicode-structural-v1`, seed `95001`, default budget 64,
  and hard maximum 256;
- all eight supported Unicode family names;
- a replay example that selects a reported case by seed and index without
  printing its text;
- the safe invariant assertion requirement;
- the boundary that generated structural invariants do not replace authored
  regressions or corpus gates and make no linguistic-quality claim;
- the prohibition on private text, model/holdout evaluation, and unbounded CI
  fuzzing.

- [ ] **Step 6: Self-review the complete issue diff**

Check:

```bash
git diff --check
git diff --stat
rg -n "TBD|TODO|PRIVATE_SENTINEL" docs tests/generative.py tests/test_generative_harness.py
```

Expected: no whitespace errors or placeholders; `PRIVATE_SENTINEL` appears only
in the privacy regression test. Confirm no file under `src/`, no dependency,
and no #119/corpus/holdout file changed.

- [ ] **Step 7: Run all required verification**

Run each command fresh and record complete outcomes:

```bash
uv run --locked --extra dev pytest tests/test_generative_harness.py -v
uv run --locked --extra dev pytest -m "not research and not slow and not model"
uv run --locked --extra dev ruff check .
uv run --locked --extra dev ruff format --check .
uv run --locked --extra dev mypy .
git diff --check
```

Expected: every command exits zero.

- [ ] **Step 8: Commit the one focused issue change**

Stage only the five issue files and verify the staged diff before committing:

```bash
git add \
  tests/generative.py \
  tests/test_generative_harness.py \
  docs/development/generative-invariants.md \
  docs/superpowers/specs/2026-08-02-deterministic-unicode-property-harness-design.md \
  docs/superpowers/plans/2026-08-02-issue-123-deterministic-unicode-harness.md
git diff --cached --check
git diff --cached --stat
git commit -m "test: add deterministic Unicode property harness (#123)"
```

Expected: one focused commit with no co-author, automation attribution, or tool
signature.
