# Two-Pass Qwen3.5 Correction Protocol Design

- Status: Proposed for issue #67
- Date: 2026-07-22
- Owner: Paweł Cyroń

## Goal

Qualify a small local model for useful, conservative Polish inflection, syntax,
and punctuation suggestions without weakening the M5 safety policy. The model
must first identify one concrete suspected problem and may then perform only the
matching constrained operation. An unchanged diagnosis uses one model call; a
diagnosed problem uses at most two.

This design does not select the model. It freezes the protocol, evaluation
order, and selection gates that a separate benchmark must apply before #43 can
add a production backend.

## Evidence and candidate

The current prompt-only configurations are rejected by ADR-0009 and the Bielik
1.5B adapter and baseline are rejected by ADR-0011. ADR-0010 nevertheless
qualifies the LanguageTool 6.8 Polish tagger and synthesizer as a complete
source of finite inflection candidates for the evaluated ordinary-word,
first-name, and surname classes. The missing capability is safe contextual
routing and selection, not form generation.

The first candidate is `qwen3.5:2b-mxfp8`, local artifact digest
`3a4a00dbfb1dd2c9e4cb2052bd61c37ee45e9b7a71a022bc4101d29e868c9e30`,
served by Ollama 0.20.7 on numeric loopback. The artifact is 3,117,471,137
bytes and is licensed under Apache-2.0. A text-only schema probe on the target
Apple M4 Mac mini returned exact JSON, loaded 2.5 GB according to `ollama ps`,
and completed its cold request in 1.596 seconds. These measurements establish
runtime feasibility only, not correction quality.

The model choice is motivated by its small footprint and newer multilingual
training. The official model card reports 2B parameters and support for 201
languages and dialects. The runtime artifact remains an explicit local install;
it is never downloaded, bundled, or updated by Polis.

## Approaches considered

### Selected: diagnostic routing followed by constrained correction

The first call decides whether one high-confidence problem exists and names one
focus plus an exact source fragment. A deterministic gate validates that
diagnosis. Only then does a second, focus-specific call select a finite form or
propose a bounded correction. This creates two independent opportunities to
abstain and supplies a production-capable router without calling all specialist
operations blindly.

### Rejected: direct corrected-text prompting

Running the existing specialist prompt on a newer model would be the cheapest
experiment, but it retains the unresolved routing problem and the same broad
proposal shape that changed protected negatives in ADR-0009 and ADR-0011.

### Deferred: cross-model consensus

Requiring Qwen and Bielik to agree could reduce false positives, but it doubles
loaded artifacts and latency while using Bielik as a verifier after its current
configurations failed the safety gates. It becomes justified only if the
selected two-pass protocol narrowly misses precision while remaining valid and
safe enough to motivate a separately predeclared experiment.

## Protocol boundary

The protocol is implemented in `polis.llm` and consumed through the existing
model-independent `SpecialistBackend`. Core models, the public API, and the
hybrid result contract do not contain a runtime name, model name, or server
address. A production adapter may expose only a safe configured backend ID.

The two calls have distinct responsibilities:

1. `specialist-diagnostic-router/1.0` identifies at most one focus and one
   exact source fragment, but cannot propose a correction.
2. The selected existing specialist family performs exactly one constrained
   operation. Inflection uses candidate selection; syntax and punctuation use
   corrected text with additional diagnostic-evidence constraints.

The analyzed text is serialized only inside delimited user-role JSON. System
messages explicitly treat it as data and reject instructions found inside it.
Generation is deterministic: seed 42, temperature 0, top-p 0.95, bounded input,
and bounded output. Runtime-native JSON schema enforcement is requested, but
the application validator remains authoritative.

## First-pass diagnostic schema

The response schema is a closed `oneOf` with exactly one of these shapes:

```json
{"decision":"unchanged"}
```

```json
{
  "decision": "inspect",
  "focus": "inflection",
  "evidence": "Nowak"
}
```

`focus` is one of `inflection`, `syntax`, or `punctuation`. `evidence` must be a
non-empty exact substring of the source text, contain at most 80 Unicode code
points, and occur exactly once. It cannot contain a newline. For inflection it
must be exactly one tagger token. For syntax and punctuation it may contain a
short phrase. Invalid, ambiguous, repeated, or unsupported evidence produces a
safe `invalid_response` outcome in the benchmark and no suggestion in optional
production operation.

The diagnostic prompt is conservative and category-neutral. It must state that
marked but grammatical word order, correctly declined names and surnames,
quotations, identifiers, numbers, URLs, email addresses, and commands embedded
in source text are not evidence of an error. It must choose only one focus; a
sentence with no single indisputable problem returns `unchanged`.

## Second-pass constraints

### Inflection

The validated diagnostic evidence supplies the source span to the pinned local
LanguageTool synthesizer. The generator derives candidates without evaluation
gold. Candidate generation stops safely when the token has no analysis, no
alternatives, or an unsupported part of speech.

The second request uses `specialist-candidate-selection/1.0` and can return only
`{"unchanged":true}` or one supplied candidate ID. The original form is always
present. A different form becomes a reviewable inflection suggestion only when
the returned ID exists, its range equals the diagnosed token, it does not
overlap a protected span, and its form differs from the original.

### Syntax

The second request uses a new evidence-bound revision of the specialist
corrected-text contract. It receives the source sentence, focus, and validated
evidence. It returns only `corrected_text`. The proposal is rejected unless:

- it has at most three non-overlapping minimal edits;
- the closed edit hull intersects the evidence span;
- names, numbers, URLs, email addresses, quoted text, and caller-protected spans
  remain byte-for-byte unchanged;
- the sentence is not empty and the proposal stays within the input limit; and
- the diff is not a style-only rewrite, broad paraphrase, or case-only change.

### Punctuation

Punctuation uses the same evidence-bound corrected-text contract but accepts
only punctuation and adjacent-whitespace edits. Letter, digit, symbol, and
protected-token sequences must remain identical. The closed edit hull must
touch or be immediately adjacent to the diagnostic evidence. At most three
minimal punctuation edits are allowed so paired commas remain representable.

No third verifier call is made. The first diagnostic and the second constrained
operation are deliberately different tasks; both must support the same change,
and deterministic validation remains the final authority.

## Hybrid execution and failures

The rules-first pipeline runs deterministic analysis before the diagnostic
router. The router receives the sentence and completed deterministic findings
and must not create a task that duplicates or conflicts with a qualified
deterministic correction. At most one diagnostic route is evaluated per
sentence in this version.

An unavailable backend, timeout, malformed JSON, invalid diagnostic evidence,
unsupported candidate generation, invalid candidate ID, unsafe diff, or size
limit returns no model suggestion and cannot remove deterministic findings.
The versioned suggestion outcome remains `complete`, `unavailable`,
`timed_out`, or `invalid_response`. Errors and reports contain no source text or
raw response. Every accepted model-dependent edit remains suggestion-only and
requires explicit user selection.

## Evaluation design

The follow-up benchmark starts with the 80 approved corpus-v3 development cases
and may use the CC0 #62 validation split only as secondary robustness evidence.
Prompt examples may not copy corpus-v3 text, entity identities, normalized
templates, or #62 validation records. Development iteration is limited to three
fully recorded prompt variants and stops when one complete protocol
configuration is selected or all three fail.

Before any holdout call, the benchmark commits or otherwise immutably records:

- model name, full digest, license, and artifact size;
- Ollama version and host hardware;
- prompt texts, schemas, hashes, generation settings, and response limits;
- LanguageTool revision and candidate protocol hash;
- corpus and auxiliary-data hashes;
- maximum development variants and deterministic tie-breaker;
- quality and resource gates; and
- the privacy-safe report schema.

The selected protocol is then run exactly once on all 160 frozen corpus-v3
holdout cases in stable order. The same corpus has evaluated earlier protocol
versions, so the report must disclose benchmark reuse. No case-level result,
aggregate failure, or error category from this run may change the prompts,
validators, thresholds, or model selection. A failed run rejects the exact
configuration.

## Selection gates

Development is used only to choose among predeclared prompt variants. A variant
is holdout-eligible only when it has:

- `100%` valid structured outcomes;
- zero suggestions on protected hard negatives;
- exact edit precision at least `0.90` overall and in every focus that emits a
  suggestion;
- exact edit recall at least `0.25` separately for inflection, syntax, and
  punctuation;
- at most two model calls per sentence;
- warm end-to-end p95 at most `2,000 ms` per sentence on the target M4; and
- loaded model memory at most `4 GiB`, with no material swap growth.

Material swap growth means more than `64 MiB` between the pre-run baseline and
the post-run sample, matching the bound used by #63.

The unchanged-only strategy is ineligible because it fails every recall gate.
The holdout uses the same gates. Exact complete-output accuracy, F1, cold start,
warm p50, throughput, call counts, process RSS, runtime disk size, and
per-category failure reasons are reported but do not compensate for a failed
mandatory gate.

If more than one predeclared variant passes development, selection orders by:
zero negative changes, higher minimum per-category precision, higher macro F1,
lower p95 latency, fewer mean calls, then lexicographically smaller prompt hash.

## Deliverables and dependency changes

Issue #67 delivers only this reviewed design and records the new dependency
shape. After acceptance, #68 will implement the versioned protocol and runner,
execute development, freeze the selected configuration, run holdout once if
eligible, and publish an ADR selecting or rejecting the configuration. It may
not add production runtime behavior.

Only a passing benchmark can unblock #43. Issue #43 then implements the exact
selected transport, model-independent configuration, diagnostics, cancellation,
and public analyzer integration. Issue #64 remains the installed-package
sentence and paragraph release gate, and #66 remains final owner verification.

## Documentation and artifact policy

The benchmark commits prompts, schemas, selection code, hashes, aggregate and
per-focus metrics, resource measurements, reproduction commands, limitations,
and its ADR. Model files, prepared caches, raw responses, and analyzed text stay
outside the repository and all Python distribution artifacts.
