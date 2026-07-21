# ADR-0008: Adopt a rules-first hybrid correction policy

- Status: Accepted
- Date: 2026-07-21
- Owner: Paweł Cyroń
- Issue: #65

## Context

The current deterministic analyzer is conservative but has limited coverage.
The source-built LanguageTool 6.8 subset delivered by #54 is genuine upstream
analysis, but it exposes only the two reviewed missing-comma rules. It is not a
general Polish corrector and has not passed the M5 automatic-correction gate.

The real-model evidence in ADR-0005 also rejects every tested model for
automatic correction. Small candidates were structurally stable only when they
returned no useful findings, while larger candidates were slower, malformed,
or unsafe on protected negative examples. A specialist corrected-text workflow
improved quality, but it remained below the release gates and took several
seconds per request.

M5 therefore needs a stable boundary between high-precision deterministic
correction and reviewable contextual suggestions. The boundary must improve
coverage without turning model fluency or self-reported confidence into
permission to alter user text.

## Decision

Adopt a rules-first hybrid architecture with two independently measured output
paths:

1. calibrated deterministic sources may become eligible for automatic
   correction under a versioned source-policy;
2. every edit that depends on model output is suggestion-only in the first
   hybrid release, even when a verifier accepts it.

This ADR defines policy for later M5 work. It does not change runtime behavior,
public data models, prompts, or backend selection.

## Components and interfaces

The existing package boundaries remain authoritative:

- `segmentation` supplies sentence and paragraph spans in original-text Unicode
  offsets;
- `rules` runs built-in rules and optional qualified deterministic analyzers,
  including only the two exposed LanguageTool rule IDs currently available;
- a deterministic morphology candidate generator may produce a finite candidate
  set with stable IDs, source span, lemma when known, form, and morphological
  features; generation does not claim contextual correctness;
- `llm` owns versioned specialist messages, schemas, response validation, and an
  injected `LocalGenerationBackend`; the backend protocol carries no model or
  server name into `core`;
- `analysis` routes only unresolved, eligible spans to specialist operations and
  normalizes accepted proposals back to validated original-text edits;
- `correction` resolves conflicts, evaluates source-policy eligibility, and
  applies only selected non-overlapping edits;
- `evaluation` measures automatic corrections and suggestions separately on
  frozen data.

Three specialist operations are allowed:

- **inflection candidate selection** returns `unchanged` or one stable candidate
  ID from the supplied finite candidate set; it cannot invent a form;
- **syntax proposal** returns unchanged text or one minimal corrected-text
  proposal for a bounded sentence;
- **proposal verification** can only accept or reject the existing candidate or
  syntax proposal; it cannot introduce a replacement, span, or third outcome.

The concrete request and response types belong to the `llm` layer and are
versioned by #59. Core orchestration continues to depend on model-independent
protocols and immutable public findings.

## Data flow and request budget

For each sentence in a paragraph, the hybrid pipeline follows this order:

1. segment the original text while retaining paragraph-relative offsets;
2. run configured deterministic rules;
3. normalize, deduplicate, and resolve deterministic conflicts;
4. identify unresolved spans eligible for a specialist operation;
5. generate finite inflection candidates where possible, or create a bounded
   syntax-proposal request;
6. validate the first response against its schema, candidate set, protected
   tokens, and original text;
7. if the first response is unchanged, stop after one model call;
8. if it proposes a change, make at most two model calls in total by asking the
   verifier to accept or reject that exact proposal;
9. convert an accepted change into a suggestion with original paragraph offsets,
   operation version, source, and calibrated confidence;
10. merge suggestions without discarding rejected or conflicting findings when
    they can be retained safely for audit.

The one model call / two model calls budget is per specialist operation. A
router must not run every operation blindly: it invokes another operation only
for a separately identified unresolved category. Deterministic analysis and
candidate generation do not consume the model-call budget.

## Correction eligibility

Automatic correction is granted by an explicit, versioned source-policy keyed
by deterministic source, rule or operation version, and category. A source may
enter that policy only after passing the automatic-correction gates on frozen
evaluation data. Eligibility cannot be inferred from `SourceKind.RULE`, a
numeric confidence threshold, model self-confidence, verifier acceptance, or
the reputation of an upstream engine.

For the first hybrid release:

- model-generated and model-selected edits are always suggestion-only;
- `Analyzer.correct()` may apply only non-conflicting findings approved by the
  calibrated deterministic source-policy;
- model suggestions remain in `skipped_findings` until a caller explicitly
  selects them through the public correction-selection path;
- a deterministic candidate does not become automatically correct merely
  because a model selected it;
- deterministic findings win conflicts with model suggestions when the
  deterministic source is qualified; a safe rejected alternative remains
  auditable rather than being silently relabelled or applied.

The current confidence-based convenience behavior remains unchanged by this
documentation issue. Replacing it with source-policy enforcement is owned by
#60 and requires compatibility tests for the observable public behavior.

## Failure and outcome boundaries

Deterministic findings must survive failure of an optional suggestion backend.
That outcome must not look like a complete suggestion run. #60 must define a
versioned outcome that distinguishes at least `complete`, `unavailable`,
`timed_out`, and `invalid_response` suggestion states while exposing only safe
backend identifiers and operation metadata.

The closed `AnalysisResult` contract from ADR-0003 cannot be silently
reinterpreted as partial. Until a separately reviewed compatible outcome
contract exists, a configured required model backend retains ADR-0003's
all-or-error behavior. The optional model path may preserve deterministic
results only through the explicit versioned outcome. The narrow LanguageTool
exception in ADR-0006 remains contained inside its optional rule and does not
authorize hidden omission of model work.

Invalid candidate IDs, malformed JSON, excessive output, broad rewrites,
protected-token changes, unverifiable diffs, and verifier attempts to replace
text all reject the model proposal. They never invalidate already completed
deterministic analysis. Errors and diagnostics contain neither source text nor
raw model responses.

## Privacy boundary

All text processing remains on the user's device. Deterministic components run
in-process or through the checked-in local LanguageTool stdio workflow. Model
inference may use a direct local runtime or a numeric loopback endpoint only;
public hosts, redirects, proxies, DNS-based service discovery, implicit model
downloads, and cloud fallbacks are prohibited.

Model artifacts are prepared explicitly outside the repository. Core modules
do not name or start MLX, Ollama, llama.cpp, a concrete model, or a model
server. Runtime configuration is injected behind the local, model-independent
backend boundary. Prompts delimit analyzed text as data, and logs and controlled
errors do not contain that text.

## Quality gates

Qualification uses a frozen holdout that is independent of prompt examples,
training data, corpus lookup code, and model-generated gold answers. Results
are reported per category and separately for the two paths.

Automatic-correction gates:

- exact edit precision `1.00`;
- correction accuracy `1.00`;
- zero changed protected hard negatives.

Suggestion gates:

- exact edit precision at least `0.90`;
- `100%` valid structured outcomes;
- zero findings on protected hard negatives.

Protected negatives include correct inflection, names and surnames, marked but
grammatical word order, numbers, URLs, quotations, and unaffected formatting.
Recall is reported per category and guides later work, but it cannot compensate
for a failed precision, validity, privacy, or protected-negative gate.

Qualification is scoped to an exact source or specialist operation version,
category, corpus version, runtime configuration, and artifact revision. Passing
one category does not qualify another. Neither the current two-rule
LanguageTool subset nor any model measured in ADR-0005 is qualified by this
decision.

## Fine-tuning policy

Prompt-only specialist protocols are measured first on #57. Fine-tuning data
is then prepared independently by #62, and #63 may evaluate a Bielik 1.5B
adapter only against the frozen prompt-only baseline and holdout. Training or a
better development score does not make an adapter a production dependency.
Only the later model/runtime selection and production-adapter issues may do so,
and only after all safety, privacy, quality, memory, and licensing gates pass.

## Consequences

- Deterministic recall can grow independently from model availability.
- A small model receives narrow selection or proposal tasks rather than one
  all-purpose grammar-analysis prompt.
- Model suggestions can add reviewable value without entering the automatic
  correction path.
- Optional suggestion failure becomes visible without deleting deterministic
  results.
- The call budget bounds latency but may intentionally miss issues that cannot
  be routed confidently.
- Source qualification, corpus integrity, and runtime evidence become release
  requirements rather than implementation assumptions.

## Alternatives considered

- **Allow verified model edits to auto-apply.** Rejected because the verifier
  uses the same class of probabilistic evidence and cannot convert model output
  into deterministic proof.
- **Use one uniform gate for every finding.** Rejected because automatic edits
  and reviewable suggestions have different user risk and must be measured
  independently.
- **Remain rules-only.** Rejected as the M5 target because deterministic rules
  alone do not cover the required contextual inflection and syntax cases, though
  rules-only operation remains a supported fallback.

## Delivery order

The binding M5 dependency graph is maintained in
`docs/project/ROADMAP.md`. In summary, #65 precedes behavior changes; evidence
integrity and corpus isolation precede prompt or morphology experiments; those
experiments precede the hybrid policy implementation; runtime, fine-tuning,
adapter, and release-gate work follow only after their recorded prerequisites.
