# Version-bound automatic correction policy design

- Status: Approved for implementation
- Date: 2026-08-01
- Owner: Paweł Cyroń
- Issue: #84
- Governing decisions: ADR-0008, ADR-0020

## Context

`Analyzer.correct()` currently grants automatic-correction eligibility through
a map keyed primarily by `Source`. The entry also stores a category and minimum
confidence, but the lookup does not bind the privilege to the operation, the
rule behavior version, or the effective source-policy version. A changed rule
implementation can therefore retain an old automatic privilege as long as it
emits the same source and category.

ADR-0008 qualifies behavior only for an exact deterministic source or operation
version and category. Issue #84 makes that qualification executable. It adds no
new automatic privileges, does not qualify a model, does not alter quality
thresholds, and does not open or rerun a holdout.

## Decision

Move automatic eligibility into a dedicated correction-policy module. Policy
version `1.2` uses the complete immutable key:

```text
(source, category, operation, behavior_version, source_policy_version)
```

Every dimension must match an explicit policy entry. Unknown sources,
categories, operations, behavior versions, policy versions, and incomplete
source metadata fail closed and remain reviewable. Confidence remains an
additional threshold after the exact key matches; confidence never grants a
privilege by itself. `SourceKind.LLM` is denied unconditionally.

Policy `1.1` remains a historical identity. Its meaning is not changed in
place. The first exact-key policy is `1.2` and preserves only the automatic
behaviors already qualified under `1.1`.

## Module boundaries

Create `polis.correction.policy` as the owner of correction eligibility. It
contains:

- an immutable `SourceBehavior` value with `source`, `operation`, and
  `behavior_version`;
- an immutable `SourcePolicyKey` with all five identity dimensions;
- an immutable policy entry that adds `minimum_confidence`;
- the active policy version and its exact entries;
- one eligibility function that performs the fail-closed decision.

`polis.rules` owns association between a registered rule and its behavior
identity. Add a narrow runtime-checkable `VersionedRule` protocol extending the
existing rule shape with immutable `operation` and `behavior_version`
properties. Existing third-party implementations that satisfy only `Rule`
remain valid analyzers, but their findings cannot be auto-applied.

`DeterministicRuleRegistry` already requires unique sources and rejects findings
whose source differs from the registered rule. It will expose a read-only
lookup from a finding source to `SourceBehavior` only when the registered rule
satisfies `VersionedRule`. The analyzer does not trust metadata carried by a
finding and does not infer metadata from source names.

`polis.analyzer` remains the orchestration boundary. For each finding it asks
the registry for installed source behavior and delegates the complete decision
to the correction policy. The source-only policy map and analyzer-local policy
dataclasses are removed.

## Behavior identities

Every currently qualified built-in rule receives an explicit operation and
behavior version. Operation names describe the stable rule action; behavior
versions identify the exact implementation contract that was qualified. The
initial built-in identities use version `1.0` and are frozen in policy `1.2`.

The exact built-in identities are:

| Source | Operation | Behavior version |
| --- | --- | --- |
| `rule:agreement.copula` | `replace.copula_form` | `agreement-copula/1.0` |
| `rule:spelling.jestes` | `replace.common_typo` | `spelling-jestes/1.0` |
| `rule:spelling.wlasnie` | `replace.common_typo` | `spelling-wlasnie/1.0` |
| `rule:spelling.zeby` | `replace.common_typo` | `spelling-zeby/1.0` |
| `rule:syntax.comma_space` | `normalize.comma_spacing` | `syntax-comma-space/1.0` |
| `rule:syntax.list_space` | `normalize.list_marker_spacing` | `syntax-list-space/1.0` |
| `rule:syntax.quote_space` | `normalize.quote_spacing` | `syntax-quote-space/1.0` |
| `rule:syntax.sentence_space` | `normalize.sentence_spacing` | `syntax-sentence-space/1.0` |

LanguageTool uses a narrower identity:

```text
source = rule:languagetool.pl
category = punctuation
operation = check.allowlisted_comma
behavior_version = pl-6.8-five-rule-comma/1.0
source_policy_version = 1.2
```

That behavior identity covers LanguageTool 6.8 compatibility checking, the
five qualified upstream rule IDs, comma-only normalization, paired-comma
handling, conflict filtering, and sentence-scope restrictions. A change to any
of those behaviors requires a new behavior version and separate evidence before
an automatic-policy entry can be added.

Reviewable deterministic rules may declare behavior metadata for observability,
but they receive no automatic-policy entry. Missing metadata is permitted at
the rule protocol boundary and always denied by the policy.

## Public API and compatibility

`Finding` and analysis-result JSON schema version 1 remain unchanged. A
deserialized finding cannot carry or recreate an automatic privilege;
`AnalysisResult.apply()` continues to represent explicit caller selection.
Adding provenance to every finding would require a public schema migration and
would put an authorization claim on untrusted serialized data, so that design
is rejected.

Add the additive field `source_policy_version: str` to `CorrectionResult`, with
the active value `1.2`. All `SuggestionOutcome` values obtain the same version
from the active policy rather than an independent literal default. Thus a
deterministic-only correction result records its effective policy even when no
suggestion outcome exists.

No canonical `CorrectionResult` JSON schema is introduced by this issue.

## Correction flow

For each normalized finding, `Analyzer.correct_async()` follows this sequence:

1. reject findings without a suggestion;
2. resolve installed source behavior from the deterministic registry;
3. construct the full key using the finding category and active policy version;
4. reject model sources regardless of confidence or metadata;
5. require an exact policy entry;
6. require the entry's confidence threshold;
7. retain the existing conflict check against already selected findings;
8. apply only findings that pass every step.

Any failure in steps 2 through 6 routes the finding to `skipped_findings`; it is
not an operational exception. Existing explicit selection through
`CorrectionResult.apply_suggestions()` remains available.

## Evidence and reporting

The installed sentence-safety runner request/response protocol advances from
schema version 1 to schema version 2. Its response adds top-level
`source_policy_version`, copied from the actual `CorrectionResult`. The response
validator requires the field and rejects unknown versions or a mismatch with
the requested frozen configuration. The evaluation report schema remains
version 1; runner protocol identity and report identity are separate contracts.

Evaluation code must derive report environment policy identity from validated
runtime observations, not copy it solely from configuration. Repeated
observations must agree. This prevents a config-only claim from masking an
installed runtime using another policy.

The committed historical policy-`1.1` report and its inputs remain unchanged
and continue to validate as report schema version 1.
Running current policy-`1.2` code against a frozen `1.1` configuration must fail
closed unless a separate, authorized evaluation configuration is created.
Issue #84 uses unit, integration, installation, and development-data tests only;
it does not consume or rerun the one-shot holdout.

## Testing strategy

Development follows red-green-refactor. Tests cover:

- exact policy-key equality and immutability;
- independent drift of source, category, operation, behavior version, and
  source-policy version;
- missing `VersionedRule` metadata and unknown registrations;
- source-name-only regression protection;
- preservation of every existing qualified built-in automatic correction;
- exact LanguageTool behavior identity and version drift to reviewable;
- unconditional model routing to reviewable at confidence `1.0`;
- agreement between `CorrectionResult` and all `SuggestionOutcome` policy
  versions;
- unchanged Finding schema-v1 serialization and compatibility snapshots;
- runner schema-v2 serialization and validation;
- runtime/config policy mismatch and inconsistent repeated observations failing
  closed;
- installed-artifact evidence reading the observed runtime policy version.

The historical report is validated but not regenerated. Slow model and holdout
tests are collected only unless an existing non-consuming test explicitly
requires execution.

## Documentation changes

Update ADR-0008 implementation notes, the public API, rule documentation,
quality gates, limitations, and compatibility notes. Documentation must state
that policy `1.2` changes enforcement identity without adding qualified
behaviors and that behavior-version changes require new direct evidence.

## Alternatives rejected

### Add provenance fields to `Finding`

Rejected because it requires a public analysis-schema migration and lets
serialized data appear to assert its own automatic privilege. Finding identity
and explicit selection do not need this metadata.

### Continue source-keyed lookup and version the policy globally

Rejected because a global version alone does not detect behavior drift under a
stable source name. It leaves the defect in #84 intact.

### Hash rule source code or package artifacts at runtime

Rejected because runtime hashes are brittle across builds, packaging, and
semantically irrelevant refactors. Explicit behavior versions are stable,
reviewable release identities.

## Risks and controls

- **Forgotten behavior-version bump:** colocate metadata with each rule and add
  tests that freeze every qualified policy entry and its documented identity.
- **Custom rule accidentally auto-applied:** absent metadata or absent exact
  policy entry fails closed.
- **Model privilege through forged source:** source kind is checked
  unconditionally and behavior is resolved from the deterministic registry.
- **Evidence claims configuration rather than runtime:** runner schema v2 emits
  the observed result version and evaluation validates agreement.
- **Historical evidence mutation:** existing report, corpus, and holdout files
  are excluded from the implementation write set.

## Definition of done

Issue #84 is complete when every acceptance criterion and required regression
test passes; public Finding schema v1 remains byte-stable; current qualified
behavior still auto-applies only with exact policy-`1.2` identities; all drift
cases become reviewable; deterministic results and release evidence expose the
effective policy version; documentation is updated; the full fast quality
suite passes; and no holdout, real-model evaluation, or historical report is
changed.
