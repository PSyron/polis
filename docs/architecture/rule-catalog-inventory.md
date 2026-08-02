# Rule catalog inventory

Status: evidence for issue #148 and input to the ownership decision in #149.

The machine-readable source for this snapshot is
[`rule-catalog-inventory.json`](rule-catalog-inventory.json). A test compares its
12 catalog candidates with the standard analyzer's default and optional runtime
registrations and with every entry in automatic correction policy `1.2`.

This inventory changes no runtime behavior or public contract. It records the
current composition root, including fail-closed policy gaps, before catalog
ownership and selection precedence are decided.

## Current boundary

The standard analyzer constructs ten deterministic rules by default and two
additional local rules only when their transports are configured or injected.
All 12 use `SourceKind.RULE`, expose an operation and behavior version, and are
therefore current catalog candidates.

`availability` distinguishes default registration from optional registration.
It does not claim that a local dependency is installed, healthy, or executing.
Both optional rules may share the vendored LanguageTool stdio session, or use
their separate injected/configured transports, without changing their source
identity.

The automatic-correction object records policy evidence rather than granting
permission. `eligible` means an exact source, category, operation, behavior
version, policy version, and confidence threshold entry exists today.
`fail_closed_review_only` means no exact policy entry exists; the finding remains
review-only. In particular, the two residual syntax rules and contextual
inflection are not automatically applied.

## Category distinction

There are currently two different category facts:

- `category` is the single category the rule implementation can emit;
- `registry_categories` is the selection scope stored in `RuleRegistration`.

For all ten default rules, `registry_categories` is `null`. The registry therefore
selects them for any non-empty category request and each rule filters itself.
The two optional rules have explicit singleton registration scopes. The inventory
preserves both facts because #149 must decide which one a future catalog owns.

## Construction and consumers

`Analyzer` is the composition root and `polis.analyzer._make_default_registry`
constructs every standard registration. Runtime analysis consumes the registry
through `find()`. Correction additionally consumes `source_behavior()` to make an
exact, fail-closed policy decision. A finding's source also contributes to its
stable identifier.

There is no production consumer for a human-readable rule description today.
The roles in the JSON snapshot are documentation for #149 and must not be treated
as a reason to add a runtime abstraction before a consumer exists.

## Explicit exclusions

- LLM and finding backends emit dynamic `llm:` sources, are not registered in
  `DeterministicRuleRegistry`, and are always ineligible for automatic correction.
- HTTP/stdio transports and process sessions support rule execution but do not
  emit findings as independent rule sources.
- `TypoSpellingRule` and manually supplied `RuleRegistration` values are extension
  mechanisms, not concrete sources in the standard analyzer.
- Synthetic test rules, typed examples, and documentation-only examples are not
  production runtime registrations.

## Questions carried into #149

1. Does the catalog own only the 12 curated standard sources, or also custom
   registrations?
2. Is the source of truth the catalog, each rule implementation, or the
   registration at the composition root?
3. Does catalog category metadata represent emitted categories, selection scope,
   or both?
4. Is registration order a compatibility guarantee?
5. How should `available`, `enabled by default`, `configured`, and transport
   health remain distinct?
6. Should one optional source keep one catalog entry across injected, HTTP, and
   vendored stdio transports?
7. How can the catalog reference policy evidence without becoming an automatic
   correction allowlist?
8. Are descriptions stable user-facing metadata or documentation only?
9. How should versioned custom rules and the non-versioned generic
   `TypoSpellingRule` boundary be represented?
10. Should future inspection expose the curated catalog, the effective configured
    registry, or both?

## Validation and privacy

`tests/test_rule_catalog_inventory.py` constructs registries with transports that
raise if any text analysis is attempted. It compares only source and metadata
identities. The test uses no corpus, model, holdout, network request, or private
text, and failures contain catalog metadata only.
