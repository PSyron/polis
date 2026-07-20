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
