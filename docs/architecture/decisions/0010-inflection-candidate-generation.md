# ADR-0010: Use LanguageTool for finite inflection candidates

- Status: Accepted
- Date: 2026-07-21
- Owner: Paweł Cyroń
- Issue: #58

## Context

ADR-0008 permits a deterministic morphology component to provide finite forms
to a later suggestion-only selector. Issue #57 invalidated an early candidate
diagnostic because it built options from evaluation gold. A valid generator
must instead derive every lemma, tag, and form from local linguistic resources.

The pinned LanguageTool 6.8 subset already contains the real Polish tagger,
PoliMorf dictionaries, and Polish synthesizer. The experiment extended its
separate local stdio boundary with explicit source spans and evaluated ordinary
words, first names, and surnames. Gold was used only to identify an evaluated
span and score whether the expected form occurred.

## Decision

Use the LanguageTool Polish tagger and synthesizer as the deterministic source
of finite inflection candidates.

The generator returns stable IDs, original Unicode ranges, optional lemmas,
forms, and morphological features. Duplicate forms are merged, ambiguous lemmas
are omitted, and the original form is always retained. Unknown or unsupported
tokens produce an explicit safe outcome rather than an invented form. These
records establish morphological possibility only, not contextual correctness.

All 24 eligible development edits and 34 eligible holdout edits reached 1.000
expected-form recall and 1.000 unchanged coverage. Recall was 1.000 separately
for ordinary words, first names, and surnames. Warm p95 was 2.68 ms on
development and 1.75 ms on holdout. The measured process used 350.1 MiB peak
RSS and 51.6 MiB of runtime files.

Do not time-box Morfeusz 2 now. LanguageTool did not miss a required candidate
class; the remaining uncertainty is contextual ranking and candidate-set width,
which a second morphology engine would not resolve.

## Consequences

- #57's candidate-selection contract may consume these records only when spans
  are supplied independently of evaluation answers.
- Candidate generation remains an optional LGPL-2.1-or-later local process and
  is not added to Python distribution dependencies.
- No synthesized form is applied automatically or presented as correct without
  a later qualified selector and the ADR-0008 safety policy.
- Later work should reduce or rank ambiguity before prompting a small model;
  ordinary-word p95 reached 41 distinct forms despite complete recall.
- A Morfeusz comparison becomes justified only if new independently reviewed
  classes demonstrate a LanguageTool coverage gap.
