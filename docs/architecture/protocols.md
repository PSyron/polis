# Analyzer and Local Backend Protocols

The runtime protocols in `polis.core.protocols` define implementation seams;
they do not implement analysis. They use the existing immutable
`AnalysisOptions`, `AnalysisResult`, `Finding`, and `Source` models, so future
implementations cannot introduce a competing result or finding format.

## DeterministicAnalyzer

`DeterministicAnalyzer` owns one deterministic source and synchronously returns
a tuple of validated `Finding` values for one input and effective options. It
is created by a future composition root, has no shared mutable call state, and
returns findings in its own deterministic order. It does not call local
generation, merge other output, apply corrections, retry work, or return an
incomplete result. A future orchestrator owns conversion of operational
failures into the controlled errors in ADR-0003.

## Rule

`Rule` is a separately registered synchronous deterministic analyzer entry. Its
stable source must identify a rule and it returns only its own validated
findings. Rule construction, lifecycle, and ordering are owned by a registry;
a rule does not select other rules or make cross-rule failure decisions.

## RuleRegistry

`RuleRegistry` executes the configured rules in deterministic order for one
analysis call. Its lifecycle is configuration before an analysis call and
read-only use during the call. It owns category selection and validates the
output of registered rules; it does not call local generation or merge
local-backend findings.

## LocalGenerationBackend

`LocalGenerationBackend` is asynchronous because a future analysis boundary
must be able to await local generation without owning an event loop. It accepts
one already-constructed prompt and returns raw response text. The backend name
is a safe stable identifier for controlled error context; it is not a model
name requirement.

Cancellation and deadline ownership belongs to the orchestrator. The backend
does not create a timeout, retry, response validator, finding, or analysis
result. It remains a local implementation boundary: this protocol does not
authorize a network call, model-server dependency, or model download.

The legacy finding path passes one flat prompt through this protocol for
compatibility. The specialist path from #59 exposes a model-independent
`PromptRequest` in `polis.llm`: two ordered role messages, a closed response
schema, protocol and schema versions, deterministic generation settings, and
explicit limits. A future runtime adapter must apply its native chat template
to those messages instead of flattening them. Neither request shape contains a
runtime or model name, and adding specialist orchestration does not silently
reinterpret the existing flat finding contract.

Issue #60 adds `HybridSuggestionEngine` in `polis.analysis.hybrid`. It consumes
an injected deterministic task router and specialist backend, never a model or
server name. Tasks use sentence-local offsets; accepted edits are translated
once into original paragraph offsets. Unchanged output stops after one call,
changed output receives one accept/reject verifier call, and every resulting
finding is suggestion-only. Optional failures return explicit safe status while
the analyzer retains deterministic findings and source-policy corrections.

## LocalFindingBackend

`LocalFindingBackend` is the separate composed local boundary used by the
analysis pipeline. It accepts a text fragment and returns validated,
fragment-local findings. Its implementation owns prompt construction,
raw-response validation, and validation of an implementation-specific retry
policy. The pipeline owns fragment iteration, forwarding the injected clock and
sleep callable, translation to original-text offsets, and canonical public
error context.

It does not replace `LocalGenerationBackend`: that protocol remains the raw
prompt-to-response boundary. Keeping both contracts separate lets adapters
expose only the operation their consumer needs without coupling core to a
specific model server or retry-policy implementation.

## MonotonicClock

`MonotonicClock` is the only time dependency required at this stage. A future
orchestrator injects it to calculate one analysis deadline consistently and
test deterministically. Rules and local backends do not own independent clocks
or deadline policies.

## AnalysisOrchestrator

`AnalysisOrchestrator` describes the synchronous and event-loop-safe future
entry points. Both consume `str` text and effective `AnalysisOptions`, and both
return the existing `AnalysisResult` type. The orchestrator owns dependency
lifecycle, option forwarding, canonical ordering, result validation, filtering,
deadline enforcement, cancellation, and translation to the ADR-0003 controlled
error hierarchy.

No partial `AnalysisResult` is returned. When any configured deterministic
component or local backend fails, the future implementation raises the relevant
controlled error rather than returning a result that conceals missing work.

Retry policy is intentionally not a protocol yet. There is no implemented
retry behavior or complete runtime exception hierarchy to parameterize, and a
premature retry abstraction would assign error-classification policy before its
owner exists. When retry behavior is introduced, a dedicated issue must define
its deterministic inputs, cancellation behavior, deadline interaction, and
ADR-0003 error translation.
