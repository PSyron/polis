# Adding deterministic rules

`polis.rules` owns deterministic rule registration and execution.

A registry entry is a `RuleRegistration` with:

- `rule`: object implementing the `polis.core.Rule` protocol
- `categories`: explicit categories this rule may emit

The registry enforces:

- one registration per unique `rule.source`
- stable rule execution order as registered
- category-based rule filtering
- output validation against the declared categories
- duplicate finding-id detection

Use this minimal pattern:

```python
from polis.core import Category, AnalysisOptions
from polis.rules import DeterministicRuleRegistry, RuleRegistration

registry = DeterministicRuleRegistry(
    [
        RuleRegistration(
            rule=MyRule(),
            categories=frozenset({Category.AGREEMENT, Category.SPELLING}),
        )
    ]
)

findings = registry.find("Tekst do analizy", options=AnalysisOptions(categories=None))
```

`source` must be stable and unique per registered rule (for example
`rule:agreement`), because finding identifiers are built from `category`,
`source`, `start`, `end`, and `original`.

## Spelling rule helpers

The first deterministic spelling rules are implemented as small, exact-pattern
helpers in `polis.rules.spelling`.

- `SpellingZebyRule` fixes `zeby` -> `żeby`.
- `SpellingWlasnieRule` fixes `wlasnie` -> `właśnie`.
- `SpellingJestesRule` fixes `jestes` -> `jesteś`.

These rules are intentionally conservative: they only match full word boundaries,
use category gating (`Category.SPELLING`), and keep casing for title-case and
all-uppercase tokens.

Difficult negatives are documented in tests and include correct words
(`właśnie`, `jesteś`) and longer strings that merely contain the typo fragment
(`wlasniew`, `zebyj`).

## Agreement rules

`AgreementCopulaRule` performs a focused, high-precision check for common
copula mismatches in fixed pronoun+verb patterns.

- `AgreementCopulaRule` (`Category.AGREEMENT`) fixes obvious cases such as
  `ona jestem` -> `ona jest`.

This rule intentionally prefers precision over broad coverage: it is limited to a
small set of subjects and first-person verb variants so behavior stays predictable.

## Syntax and punctuation rules

Selected syntax and punctuation helpers are in `polis.rules.syntax` and are split
by category:

- `SyntaxCommaSpacingRule` (`Category.PUNCTUATION`) inserts missing spaces after
  commas, and skips common abbreviation fragments like `itp,` and `m.in,`.
- `SyntaxListSpacingRule` (`Category.SYNTAX`) inserts missing space after a line
  list marker (`1.`, `-`, `*`) when the next token starts immediately.
- `SyntaxQuoteSpacingRule` (`Category.PUNCTUATION`) adds a missing space after an
  opening quotation mark that is attached directly to a word.

All three rules support category filtering through the shared `options.categories`
mechanism and return deterministic findings with stable IDs.

## Optional LanguageTool punctuation rule

`LocalLanguageToolRule` is registered only when `[language_tool]` is configured.
It accepts a separately installed local LanguageTool 6.8 server and maps only
`BRAK_PRZECINKA_ZE` and `BRAK_PRZECINKA_ZEBY` to minimal comma insertions with
source `rule:languagetool.pl` and confidence `0.85`.

The rule converts Java UTF-16 offsets to Python code-point offsets, minimizes
wide replacements, rejects ambiguous alternatives and conflicting findings,
and drops every unknown rule or non-comma change. Its reviewed corpus result is
18 true-positive insertions, zero false positives, six missed punctuation edits,
and no findings on 10 correct hard negatives. General LanguageTool spelling,
grammar, style, and morphology findings are intentionally excluded.

## Analysis normalization

Normalization is performed in `polis.analysis` by the following deterministic
steps:

1. `filter_findings` removes findings outside the requested category set and
   below `minimum_confidence`.
2. `deduplicate_findings` keeps one canonical representative for each
   stable finding identifier.
3. `prioritize_findings` sorts findings by source text position, then by
   confidence and tie-breakers to make output deterministic.
4. `normalize_findings` runs the full pipeline and is the standard helper for
   the public path.

The same rules apply to any analyzer output before presentation.

## Deterministic correction application

`polis.analysis` and `polis.core` validate selected finding ids and apply
replacements right-to-left using helpers in `polis.correction`.

- `findings_conflict` encodes span-level compatibility.
- `validate_non_conflicting_corrections` raises on invalid selection sets.
- `sort_findings_for_application` applies compatible findings in stable right-to-
  left order.

`AnalysisResult.apply` is the public API for explicit selection-only
correction.
