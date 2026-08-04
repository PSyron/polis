# Immutable Rule Catalog Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add immutable, deterministic, privacy-safe rule metadata and catalog contracts for issue #150 without changing rule execution or frozen evidence.

**Architecture:** A focused `polis.rules.catalog` module owns the metadata value, static availability enum, catalog container, and contract errors. `polis.rules` re-exports these internal contracts, while the existing registry, analyzer composition root, policy, public `polis` API, inventories, and frozen artifacts remain untouched.

**Tech Stack:** Python 3.12, frozen slotted dataclasses, `enum.StrEnum`, pytest, Ruff, mypy.

## Global Constraints

- Work only on GitHub issue #150 and produce one focused commit referencing `#150`.
- Keep actively maintained authored project documentation in Polish; keep code, identifiers, imports, schemas, protocol literals, and GitHub metadata in English. Preserve the original language of historical `docs/superpowers/**` records. Paweł Cyroń remains the sole credited author.
- Do not migrate built-in or optional producers; those changes belong to #152 and #153.
- Do not add source selection or public configuration; those changes belong to #151.
- Do not change `RuleRegistration`, `DeterministicRuleRegistry`, `Analyzer._make_default_registry()`, `SourceBehavior`, or automatic-correction policy behavior.
- Do not edit or rerun any report, corpus, model, holdout, digest, marker, inventory snapshot, or frozen evidence.
- Add no production dependency and preserve the offline-only privacy boundary.
- Export the new contracts from `polis.rules` only, never from top-level `polis` or `polis.core`.

---

### Task 1: Lock the metadata and catalog contract with regression tests

**Files:**
- Create: `tests/test_rule_catalog.py`

**Interfaces:**
- Consumes: `Category`, `Source`, and `SourceKind` from `polis.core`.
- Produces test expectations for `RuleAvailability`, `RuleMetadata`, `RuleCatalog`, `RuleCatalogError`, `InvalidRuleMetadataError`, and `DuplicateRuleMetadataError` imported from `polis.rules`.

- [x] **Step 1: Add a valid metadata fixture and immutable-value tests**

```python
def _metadata(name: str = "example", **changes: object) -> RuleMetadata:
    values: dict[str, object] = {
        "source": Source(SourceKind.RULE, name),
        "operation": "analyze",
        "behavior_version": "1",
        "categories": frozenset({Category.SYNTAX}),
        "enabled_by_default": True,
        "availability": RuleAvailability.BUILT_IN,
        "description": "Checks example syntax.",
    }
    values.update(changes)
    return RuleMetadata(**cast(Any, values))


def test_rule_metadata_is_an_immutable_slotted_value() -> None:
    metadata = _metadata()

    assert metadata == _metadata()
    assert not hasattr(metadata, "__dict__")
    with pytest.raises(FrozenInstanceError):
        metadata.description = "Changed"  # type: ignore[misc]
```

Also assert the exact serialized enum values `built_in` and `requires_configuration` and every field on the valid value.

- [x] **Step 2: Add deterministic catalog enumeration and lookup tests**

```python
def test_rule_catalog_preserves_declared_order_and_supports_exact_lookup() -> None:
    second = _metadata("second")
    first = _metadata("first")
    catalog = RuleCatalog((second, first))

    assert catalog.entries() == (second, first)
    assert catalog.get(first.source) is first
    assert catalog.get(Source(SourceKind.RULE, "missing")) is None


def test_empty_rule_catalog_is_valid() -> None:
    assert RuleCatalog(()).entries() == ()
```

Assert the returned tuple cannot be mutated and the catalog has no `__dict__`.

- [x] **Step 3: Add fail-closed duplicate, malformed-field, and container tests**

Use parametrized cases to reject:

```python
(
    ("source", object()),
    ("source", Source(SourceKind.LLM, "example")),
    ("operation", ""),
    ("operation", " analyze"),
    ("behavior_version", ""),
    ("behavior_version", "1 "),
    ("categories", frozenset()),
    ("categories", {Category.SYNTAX}),
    ("categories", frozenset({"syntax"})),
    ("enabled_by_default", 1),
    ("availability", "built_in"),
    ("description", ""),
    ("description", " private text "),
)
```

Each metadata failure must be `InvalidRuleMetadataError` with only `invalid rule metadata field: <field>`. Reject a duplicate source with `DuplicateRuleMetadataError`; reject list, set, generator, non-`RuleMetadata` entries, and a non-`Source` lookup with `RuleCatalogError`. Assertions must prove a sentinel such as `PRIVATE_ANALYZED_SENTENCE` never appears in any error message.

Also reject behavior-overriding subclasses of `Source`, `str`, `frozenset`,
`tuple`, and `RuleMetadata`, including a `Source.name` string subclass and a
`Source` subclass passed to `get()`. These regressions prove the stored values
and lookups cannot change iteration, equality, hashing, or string rendering
after validation.

- [x] **Step 4: Add package-boundary regression assertions**

```python
def test_rule_catalog_contracts_are_internal_to_rules_package() -> None:
    import polis

    assert "RuleCatalog" not in polis.__all__
    assert "RuleMetadata" not in polis.__all__
    assert not hasattr(polis, "RuleCatalog")
    assert not hasattr(polis, "RuleMetadata")
```

- [x] **Step 5: Run the new tests and capture the expected RED result**

Run: `.venv/bin/pytest tests/test_rule_catalog.py -q`

Expected: collection fails because the new catalog contracts cannot yet be imported from `polis.rules`. This is the contract failure the production change must fix.

### Task 2: Implement the minimal immutable contracts

**Files:**
- Create: `src/polis/rules/catalog.py`
- Modify: `src/polis/rules/__init__.py`
- Test: `tests/test_rule_catalog.py`

**Interfaces:**
- Consumes: `Category`, `Source`, and `SourceKind` from `polis.core`.
- Produces:
  - `RuleAvailability(StrEnum)` with `BUILT_IN` and `REQUIRES_CONFIGURATION`.
  - `RuleMetadata(source, operation, behavior_version, categories, enabled_by_default, availability, description)` as `@dataclass(frozen=True, slots=True)`.
  - `RuleCatalog(entries: tuple[RuleMetadata, ...])`, `entries() -> tuple[RuleMetadata, ...]`, and `get(source: Source) -> RuleMetadata | None`.
  - `RuleCatalogError(ValueError)`, `InvalidRuleMetadataError`, and `DuplicateRuleMetadataError`.

- [x] **Step 1: Add privacy-safe error and availability types**

```python
class RuleCatalogError(ValueError):
    """Base error for invalid rule catalog contracts."""


class InvalidRuleMetadataError(RuleCatalogError):
    """Raised when rule metadata violates its contract."""


class DuplicateRuleMetadataError(RuleCatalogError):
    """Raised when a catalog contains a duplicate rule source."""


class RuleAvailability(StrEnum):
    BUILT_IN = "built_in"
    REQUIRES_CONFIGURATION = "requires_configuration"
```

- [x] **Step 2: Implement exact metadata validation**

```python
@dataclass(frozen=True, slots=True)
class RuleMetadata:
    source: Source
    operation: str
    behavior_version: str
    categories: frozenset[Category]
    enabled_by_default: bool
    availability: RuleAvailability
    description: str

    def __post_init__(self) -> None:
        if (
            type(self.source) is not Source
            or self.source.kind is not SourceKind.RULE
            or type(self.source.name) is not str
        ):
            _invalid("source")
        for field_name in ("operation", "behavior_version", "description"):
            value = getattr(self, field_name)
            if type(value) is not str or not value or value != value.strip():
                _invalid(field_name)
        if (
            type(self.categories) is not frozenset
            or not self.categories
            or any(not isinstance(category, Category) for category in self.categories)
        ):
            _invalid("categories")
        if type(self.enabled_by_default) is not bool:
            _invalid("enabled_by_default")
        if not isinstance(self.availability, RuleAvailability):
            _invalid("availability")
```

`_invalid(field_name)` raises only `InvalidRuleMetadataError(f"invalid rule metadata field: {field_name}")`; it must never interpolate the invalid value.

- [x] **Step 3: Implement atomic ordered catalog validation**

```python
@dataclass(frozen=True, slots=True, init=False)
class RuleCatalog:
    _entries: tuple[RuleMetadata, ...]

    def __init__(self, entries: tuple[RuleMetadata, ...]) -> None:
        if type(entries) is not tuple:
            raise RuleCatalogError("catalog entries must be an ordered tuple")
        seen: set[Source] = set()
        for entry in entries:
            if type(entry) is not RuleMetadata:
                raise RuleCatalogError("catalog entries must contain RuleMetadata values")
            if entry.source in seen:
                raise DuplicateRuleMetadataError(
                    f"duplicate rule metadata source: {entry.source}"
                )
            seen.add(entry.source)
        object.__setattr__(self, "_entries", entries)

    def entries(self) -> tuple[RuleMetadata, ...]:
        return self._entries

    def get(self, source: Source) -> RuleMetadata | None:
        if type(source) is not Source or type(source.name) is not str:
            raise RuleCatalogError("catalog lookup source must be a Source")
        return next((entry for entry in self._entries if entry.source == source), None)
```

- [x] **Step 4: Re-export only through `polis.rules`**

Import the six catalog symbols in `src/polis/rules/__init__.py` and add them to that module's `__all__`. Do not modify `src/polis/__init__.py` or `src/polis/core/__init__.py`.

- [x] **Step 5: Run the focused tests and capture GREEN**

Run: `.venv/bin/pytest tests/test_rule_catalog.py -q`

Expected: all new catalog tests pass.

- [x] **Step 6: Run focused compatibility tests**

Run: `.venv/bin/pytest tests/test_rules.py tests/test_protocols.py tests/test_rule_catalog_inventory.py tests/test_automatic_correction_policy.py -q`

Expected: all pass with no registry, inventory, protocol, or policy changes.

### Task 3: Verify, review, publish, and integrate issue #150

**Files:**
- Verify only: all tracked project files.
- Commit: the design, plan, catalog module, package export, and catalog test from Tasks 1–2.

**Interfaces:**
- Consumes: the completed issue #150 implementation.
- Produces: one reviewed commit, one ready PR that closes #150, green CI, and a merged `main`.

- [x] **Step 1: Run the complete local verification suite**

Run each command separately and retain the result:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy .
git diff --check
```

Expected: every command exits 0. Also inspect `git diff --name-only` and confirm that no frozen artifact, inventory snapshot, analyzer composition, policy implementation, or issue #151/#152/#153 file is changed.

- [x] **Step 2: Request independent code review**

Use `superpowers:requesting-code-review` and give the reviewer issue #150, the accepted design, the exact base/head diff, contract boundaries, and verification results. Resolve every important finding with `superpowers:receiving-code-review`, rerun the affected focused checks, and request a follow-up review when code changes materially.

- [x] **Step 3: Re-run final verification after review**

Run the same five commands from Step 1 from the reviewed tree. Expected: every command exits 0 with no unreviewed material change.

- [ ] **Step 4: Create the single focused commit**

```bash
git add docs/superpowers/specs/2026-08-04-issue-150-rule-catalog-contracts-design.md \
  docs/superpowers/plans/2026-08-04-issue-150-rule-catalog-contracts.md \
  src/polis/rules/catalog.py src/polis/rules/__init__.py \
  tests/test_rule_catalog.py
git commit -m "feat: add immutable rule catalog contracts (#150)"
```

Confirm the commit author is Paweł Cyroń and no trailers or tooling attribution were added.

- [ ] **Step 5: Push and open a ready pull request**

Push `feature/issue-150-rule-catalog-contracts` and open a non-draft PR whose English body contains `Closes #150`, the exact contract summary, RED/GREEN evidence, full verification results, privacy/evidence immutability confirmation, and the deliberate exclusions for #151/#152/#153.

- [ ] **Step 6: Wait for green CI and independent GitHub review, then merge**

Do not merge until all required checks are green and the independent review is recorded without unresolved important findings. Merge using the repository's accepted method, verify `main` contains the focused commit, verify issue #150 is closed, and remove the short-lived local worktree/branch only after integration is confirmed.

- [ ] **Step 7: Stop at the issue boundary**

Report issue and PR numbers, exact cause/scope, changed files, RED and GREEN results, all checks, independent review, CI, commit, merge state, frozen-evidence confirmation, and the next permitted issue. Do not start #151, #152, or #153 in this task.
