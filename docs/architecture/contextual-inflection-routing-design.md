# Contextual Polish Inflection Routing Design

- Status: Accepted for issue #71
- Date: 2026-07-22
- Owner: Paweł Cyroń

## Objective

Select a finite LanguageTool form for a narrowly detected inflection target in
one Polish sentence. Detection and selection receive source text, token spans,
and local morphology only. Case identifiers, corpus strata, tags, expected
outputs, and gold spans remain scorer-only.

## Alternatives

1. **Explicit government and adjacent-name agreement — selected.** Detect a
   small closed set of contextual relations and select only a unique finite
   form satisfying their morphological constraints.
2. **Ask a compact model to choose from all forms.** Deferred because the
   deterministic constraints can first reduce ambiguity and establish a safe
   baseline without model weights or prompt variance.
3. **Rank forms by corpus frequency.** Rejected because frequency alone does
   not establish government or agreement and no approved local frequency
   resource is currently part of the runtime.

## Source-only evidence

The router recognizes only these sentence-local patterns:

- two adjacent capitalized word tokens: the second token is a surname target
  when its current morphology does not overlap the first token's current case,
  number, and compatible gender;
- `bez` followed by one noun or an adjective-noun pair: the phrase requires
  singular genitive while preserving the head noun's number and gender;
- a source form beginning with `przygląd` followed by `się` and one noun or an
  adjective-noun pair: the phrase requires singular dative;
- a source form beginning with `podzięk` followed by one capitalized token:
  the token is a first-name target requiring singular dative.

Tokenization and target spans are derived from source text before any corpus
wrapper is consulted. Unsupported punctuation layouts, more than two phrase
tokens, missing analyses, indeclinable forms, plural ambiguity, incompatible
lemmas, and non-unique selections cause abstention.

## Candidate constraints

The existing local `synthesize` operation supplies every candidate. A proposal
must preserve the requested Unicode half-open span, cite its `ltpl:` candidate
ID, differ from the source surface, and be the only distinct form satisfying
the evidence. Adjectives additionally preserve positive degree and agree with
the selected noun in case, number, and gender. Surnames preserve the adjacent
first name's current case and number and require compatible gender.

The unchanged source form is used only to infer its visible morphological
features. Gold never chooses a target, feature, candidate, or abstention.

## Evaluation and holdout

Development evaluates all 69 corpus-v3 sentences, not only known inflection
cases. Metrics include target detection, candidate provenance, exact edit
TP/FP/FN, protected-negative suggestions, class recall for first names,
surnames, and ordinary words, abstentions, warm p95, process RSS, and runtime
disk size. Raw sentences and synthesis responses are not committed.

A development candidate requires edit precision at least 0.90, supported
inflection recall at least 0.25, zero protected-negative suggestions, valid
non-conflicting applications, and warm p95 at most 50 ms beyond the warm local
process. The router and configuration are frozen before one holdout run. A
failed development result leaves holdout unopened.

## Production boundary

The experiment is suggestion-only and is not registered in the analyzer. A
passing result requires a separate source-policy decision before automatic
correction. Paragraphs, generated forms, cloud calls, and unconstrained
rewriting are excluded.
