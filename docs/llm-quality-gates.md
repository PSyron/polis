# Hybrid correction quality gates

ADR-0008 separates automatic deterministic corrections from reviewable model
suggestions. Each path is measured independently against exact original-text
edits on a frozen holdout. Fluency, JSON validity, speed, model confidence, or a
strong aggregate score cannot compensate for a failed path-specific gate.

## Shared safety gates

- Protected hard negatives include correct inflection, names and surnames,
  marked but grammatical word order, numbers, URLs, quotations, and unaffected
  formatting.
- All analyzed text remains local after explicit artifact preparation. A model
  runtime is direct local inference or uses a numeric loopback endpoint only.
- Gold answers cannot be embedded in benchmark execution, prompt examples,
  training records, or corpus-specific lookup branches.
- Recall, F1, complete-output accuracy, latency, throughput, memory, and calls
  per case are reported per category even when they are not release gates.

Failure of a shared safety or privacy gate rejects the exact source, operation,
runtime, and artifact configuration under test.

## Automatic-correction gates

Automatic eligibility is evaluated per deterministic source, rule or operation
version, and category:

- exact edit precision: **1.00**;
- correction accuracy: **1.00**;
- protected hard negatives: **0** changed cases.

Passing these metrics does not itself change runtime policy. The exact source
must also be added to the versioned automatic-correction source policy. Rule
provenance, engine identity, or confidence alone never grants eligibility.

## Suggestion gates

Model-dependent edits remain suggestion-only for the first hybrid release,
including finite-candidate selections and verifier-accepted proposals:

- exact edit precision: at least **0.90**;
- valid structured outcomes: **100%**;
- protected hard negatives: **0** findings.

Recall is reported for `inflection`, `syntax`, and `punctuation` and guides
later improvement. Low recall is acceptable for a conservative release; it
never permits a lower precision, validity, or protected-negative threshold.

## Selection evidence

Evidence records prompt and schema versions, exact model revision and
quantization, runtime version, hardware class, operating system, corpus and
split hashes, loaded memory, cold and warm latency, throughput, model calls,
and offline verification. Development and holdout results remain separate.

The original LanguageTool two-rule subset and every model in ADR-0005 predate
these M5 gates. ADR-0014 later qualified four exact LanguageTool rule IDs and
source-policy version `1.1` integrates the resulting five-ID allowlist. A model
adapter may proceed only after its exact prompt, runtime, model, and source
policies pass their applicable gates.
