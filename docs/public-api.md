# Public Analysis Models

Polis exposes immutable, typed data models from both `polis` and `polis.core`.
This contract describes analysis data and the public analyzer surface.
The current package ships a thin runtime analyzer in `polis` and a stricter
contract in [ADR-0003](architecture/decisions/0003-public-api-and-exception-contract.md).

## Approved analyzer contract

The future package-root API is deliberately small:

```python
import polis
from polis import AnalysisOptions, Analyzer

analyzer = Analyzer.from_config("polis.toml")
result: polis.AnalysisResult = analyzer.analyze(
    "Te zdanie zawiera błąd.",
    options=AnalysisOptions(categories={"agreement"}, minimum_confidence=0.8),
)
corrected = result.apply(issue_ids=(result.issues[0].id,))
```

`Analyzer.from_config(path)` reads an explicit local TOML configuration and
never accesses the network. `Analyzer(config)` is the equivalent constructor
when a caller has already validated an `AnalyzerConfig`. `analyze()` blocks the
calling thread; `await analyze_async()` has identical inputs, result ordering,
filters, and failures for event-loop applications. Passing `None` for options
uses the default `AnalysisOptions()`; otherwise its category and confidence
filters are reflected in `result.options`.

One call either returns a complete, validated result for its required configured
scope or raises a controlled operational error. No partial `AnalysisResult` is returned.
This avoids a successful-looking result that silently omits a failed backend.
The current schema-version-1 result has no partial-state field; any future
partial-analysis feature needs an explicit versioned outcome contract.

The disabled-by-default LanguageTool rule is a documented narrow exception:
because it is an optional best-effort rule, local service failure is represented
as zero findings from that rule while completed built-in findings remain. This
does not alter failure handling for required analyzers or LLM backends and does
not introduce a partial-result field.

`result.apply(issue_ids)` applies only named findings from that result. It
validates the entire selection before changing output, rejects unknown,
duplicate, unsuggestable, overlapping, or same-boundary corrections, and then
applies compatible replacements right-to-left in original-text coordinates. An
empty selection returns the source text. The operation is atomic: a selection
error returns no partial corrected text.

## Conservative correction

`Analyzer.correct(text)` is the convenience path for a sentence or paragraph.
`await Analyzer.correct_async(text)` runs the identical orchestration without
starting an event loop; results, ordering, call budgets, failures, and policy
decisions are equivalent.
It returns `CorrectionResult` with `original_text`, `corrected_text`,
`applied_findings`, `skipped_findings`, and `suggestion_outcomes`.
It automatically applies only non-conflicting deterministic rule findings that are
covered by the calibrated source-policy. Currently that includes:

- `agreement.copula`
- `spelling.jestes`
- `spelling.wlasnie`
- `spelling.zeby`
- `syntax.comma_space`
- `syntax.list_space`
- `syntax.quote_space`
- `syntax.sentence_space`
- `languagetool.pl` (only the five explicit rule IDs documented below)
Remaining findings, including model-generated and unsuggestable cases, stay in
`skipped_findings`.

`suggestion_outcomes` is a versioned telemetry tuple for optional backend
attempts. For each suggestion-capable operation it records:

- `status`: one of `complete`, `unavailable`, `timed_out`, or `invalid_response`
- `backend`: stable backend identifier
- `operation`: operation name used for the suggestion call
- `suggestions`: number of model-sourced suggestions produced by analysis
- `model_calls`: actual calls made for that optional suggestion path
- `protocol_versions`: ordered specialist operation/version identifiers used
- `operation_version`: suggestion operation contract version
- `source_policy_version`: source-policy contract version

Source-policy version `1.1` adds automatic application of the explicitly
qualified `languagetool.pl` comma insertions. It does not authorize other
LanguageTool rules or category-wide correction.

The default analyzer also exposes the sentence-only deterministic sources
`syntax.missing_reflexive` and `syntax.missing_correlative`. They cover only the
three exact constructions documented in [rules.md](rules.md), and return no
finding when the input contains multiple sentences. They are deliberately not
listed in the automatic policy: `correct()` places their findings in
`skipped_findings`, and a caller can apply a chosen finding through
`apply_suggestions()`.

Model findings are never auto-applied in this method; callers can still use
`CorrectionResult.apply_suggestions(finding_ids)` to explicitly select entries
from `skipped_findings`. The method atomically reapplies the automatic findings
and selected suggestions against the original text; unknown, duplicate,
unsuggestable, or conflicting selections use the existing controlled correction
errors.
An unchanged specialist result consumes one call. A changed candidate or syntax
proposal is validated and then consumes exactly one additional accept/reject
verifier call. The verifier cannot replace the proposal. Accepted specialist
edits carry original paragraph offsets and remain in `skipped_findings` until a
caller explicitly selects their IDs through `apply_suggestions()`.

Specialist orchestration is dependency-injected with
`Analyzer(config, specialist_engine=...)`. The default is `None`, so ordinary
construction makes no specialist calls. Issue #60 provides the
model-independent engine and fake-tested policy; no real model/runtime is
selected or enabled by this API.

`AnalyzerConfig` also accepts `language_tool_url` and
`language_tool_timeout_seconds`. A TOML `[language_tool]` table maps its
`base_url` and `timeout_seconds` keys to those fields. Omission disables all
LanguageTool I/O and registration.

`AnalyzerConfig` also accepts `contextual_inflection_stdio_path` and
`contextual_inflection_timeout_seconds`. The matching TOML section is:

```toml
[contextual_inflection]
stdio_path = "/absolute/path/to/run_stdio.sh"
timeout_seconds = 2.0
```

The path must reference an absolute executable. The optional rule emits
`Category.INFLECTION` findings from source-local evidence and finite
`synthesize_context` candidates. These findings are returned in
`skipped_findings`; callers may apply selected IDs with `apply_suggestions()`.
The rule abstains without I/O unless the input contains exactly one sentence.
For tests or embedding, callers can instead inject a `ContextMorphologyTransport`
with `Analyzer(config, contextual_inflection_transport=transport)`.

The preferred shared configuration uses
`AnalyzerConfig.vendored_language_tool_stdio_path` and
`AnalyzerConfig.vendored_language_tool_timeout_seconds`, mapped from:

```toml
[vendored_language_tool]
stdio_path = "/absolute/path/to/run_stdio.sh"
timeout_seconds = 2.0
```

This sentence-only mode creates one persistent local stdio session implementing
both LanguageTool check and contextual synthesis. It is mutually exclusive with
`[language_tool]` and `[contextual_inflection]`. It starts lazily, performs no
download, preserves source-policy `1.1`, and leaves contextual inflection
reviewable. Analyzer-owned sessions are terminated by `Analyzer.close()` or
context-manager exit. Transports injected by callers remain caller-owned and
are not closed by the analyzer.

`Analyzer.language_tool_process_start_count` is a read-only diagnostic for the
analyzer-owned vendored stdio session. It is `0` before the lazy local process
starts (and when no owned session is configured), and remains `1` while the
qualified persistent-session contract is respected. The sentence release gate
records this measured value; it does not infer a successful start from config.

The analyzer API above is implemented by a thin runtime in `polis` and remains
small by design. `polis.core` and `polis` directly re-export the same `AnalysisResult`
model and the checked examples prove bidirectional assignment compatibility
among both imports and analyzer returns. The stubs remain the authoritative typing
contract in `tests/typecheck/stubs/`, and the examples live in
`tests/typecheck/api_contract_examples.py`.

### Controlled failures

All controlled operational errors derive from `PolisError` and expose a stable
`code`, `retryable` flag, and a safe `context` mapping. They never contain the
analyzed text, source fragments, suggestions, prompts, full backend output, or
secrets. The complete hierarchy and context allowlist are in ADR-0003.

```python
from polis import (
    AnalysisTimeoutError,
    Analyzer,
    BackendUnavailableError,
    ConfigurationError,
    CorrectionConflictError,
    InvalidBackendResponseError,
    UncorrectableFindingError,
    UnknownFindingError,
)

try:
    analyzer = Analyzer.from_config("polis.toml")
except ConfigurationError as error:
    assert error.code == "configuration.invalid"
    assert error.retryable is False
    assert error.context["path"] == "polis.toml"

try:
    result = Analyzer.from_config("polis.toml").analyze("Tekst")
except BackendUnavailableError as error:
    assert error.retryable is True
    assert error.context["backend"]
except AnalysisTimeoutError as error:
    assert error.code == "analysis.timeout"
    assert error.context["backend"]
except InvalidBackendResponseError as error:
    assert error.retryable is False
    assert error.context["backend"]

try:
    result.apply(issue_ids=("finding_missing",))
except UnknownFindingError as error:
    assert error.code == "correction.unknown_finding"
    assert error.retryable is False
    assert error.context["finding_ids"] == "finding_missing"

try:
    result.apply(issue_ids=("finding_without_suggestion",))
except UncorrectableFindingError as error:
    assert error.code == "correction.uncorrectable_finding"
    assert error.retryable is False
    assert error.context["finding_ids"] == "finding_without_suggestion"

try:
    result.apply(issue_ids=("overlapping-first", "overlapping-second"))
except CorrectionConflictError as error:
    assert error.code == "correction.conflict"
    assert error.retryable is False
    assert error.context["finding_ids"]
```

## Constructing a result

```python
from polis import (
    AnalysisOptions,
    AnalysisResult,
    Category,
    Confidence,
    Finding,
    Severity,
    Source,
    SourceKind,
)

text = "Te zdanie zawiera błąd."
finding = Finding.create(
    category=Category.AGREEMENT,
    severity=Severity.ERROR,
    message="Niezgodność rodzaju zaimka i rzeczownika.",
    explanation="Forma „Te” nie zgadza się z rzeczownikiem „zdanie”.",
    original="Te zdanie",
    suggestion="To zdanie",
    start=0,
    end=9,
    confidence=Confidence(0.98),
    source=Source(SourceKind.RULE, "agreement"),
)
result = AnalysisResult(
    text=text,
    issues=(finding,),
    options=AnalysisOptions(
        categories={"agreement", "spelling"},
        minimum_confidence=0.75,
    ),
)
```

The models are frozen dataclasses. Collections are normalized to immutable
tuples or frozensets, so a result cannot be changed after validation.

## Field semantics

`Category` has the values `inflection`, `agreement`, `syntax`, `spelling`,
`punctuation`, and `style`. `Severity` has `error`, `warning`, and `suggestion`.
Severity describes presentation strength; it does not change the confidence
value.

A `Finding` contains:

| Field | Meaning |
| --- | --- |
| `id` | Deterministic identifier for selecting the underlying finding within a result. |
| `category` | Typed issue category. |
| `severity` | Typed presentation severity. |
| `message` | Short user-facing description. |
| `explanation` | Reason the text was reported. |
| `original` | Exact slice of the input located by `start:end`; empty for an insertion and potentially whitespace-only. |
| `suggestion` | Minimal replacement that differs from `original`, or `None` when no justified replacement is available. An empty string represents deletion of a non-empty original. |
| `start`, `end` | Half-open range in the original input. |
| `confidence` | Finite number from `0.0` through `1.0`, inclusive. |
| `source` | Analyzer family and stable name, serialized as `rule:name` or `llm:name`. |

`AnalysisOptions(categories=None)` means all categories. An empty category
collection means no categories. Category strings are normalized to `Category`
values. `minimum_confidence` defaults to `0.0` and is normalized to
`Confidence`.

## Extension and stability references

Extension points and boundaries are documented in:

- [rules](rules.md)
- [customization](customization.md)
- [offline operation](offline-operation.md)
- [protocols](architecture/protocols.md)
- [privacy](privacy.md)
- [compatibility and semver](compatibility.md)
- [limitations](limitations.md)

## Offsets and validation

Offsets always use Python string indices and the half-open convention
`[start, end)`. They count Unicode code points, not UTF-8 bytes and not visual
grapheme clusters. For example:

```python
text = "🙂 Te zdanie"
assert text[2:11] == "Te zdanie"
```

`Finding` rejects boolean or negative offsets, reversed ranges, ranges whose
code-point length differs from `len(original)`, blank messages or explanations,
malformed identifiers and sources, and invalid confidence values including
`NaN`, infinity, and numeric values too large for a finite Python float.
Negative confidence zero is normalized to positive `0.0`, so it has one
canonical JSON representation. `original` is preserved verbatim: an insertion
uses `start == end` and `original == ""`, while deletion of whitespace can use a
whitespace-only `original` and `suggestion == ""`. `AnalysisResult` additionally
verifies that every range is within `text`, that `text[start:end]` equals
`original`, and that finding identifiers are unique. Zero-width insertions are
valid at any boundary through the end of the input. Invalid Python construction
raises `TypeError` for a wrong value type and `ValueError` for a value outside
the contract.

Any non-`None` suggestion must differ exactly from `original`. This rejects both
ordinary no-op replacements and the zero-width `original == suggestion == ""`
case. Use `None` to represent a finding without a justified replacement. A valid
insertion has an empty `original` and a non-empty suggestion; a valid deletion
has a non-empty (possibly whitespace-only) `original` and an empty suggestion.

`Finding.create()` produces an identifier with the form
`finding_<32 lowercase hexadecimal characters>`. It hashes canonical identity
data with a versioned 128-bit BLAKE2b digest. Identity consists of category,
source, start, end, original text, and optional suggestion. Message,
explanation, severity, and confidence are presentation or calibration data and
do not change the identifier. Identity strings are hashed exactly as supplied,
including Unicode representation, case, and whitespace; Polis does not apply
Unicode or textual normalization. An identity change does change the
identifier. Distinct findings with the same identity therefore have the same
identifier and cannot coexist in one result, and any other identifier collision
is likewise rejected. Identifiers are not intended as permanent cross-document
database keys.

## JSON schema version 1

Use either the free functions or the result convenience methods:

```python
from polis import AnalysisResult, analysis_result_from_json, analysis_result_to_json

encoded = analysis_result_to_json(result)
assert result.to_json() == encoded
assert analysis_result_from_json(encoded) == result
assert AnalysisResult.from_json(encoded) == result
```

The top-level schema is:

```json
{
  "schema_version": 1,
  "text": "Te zdanie zawiera błąd.",
  "options": {
    "categories": ["agreement", "spelling"],
    "minimum_confidence": 0.75
  },
  "issues": [
    {
      "id": "finding_b89cbdbde56272994279f763b05cf63b",
      "category": "agreement",
      "severity": "error",
      "message": "Niezgodność rodzaju zaimka i rzeczownika.",
      "explanation": "Forma „Te” nie zgadza się z rzeczownikiem „zdanie”.",
      "original": "Te zdanie",
      "suggestion": "To zdanie",
      "start": 0,
      "end": 9,
      "confidence": 0.98,
      "source": "rule:agreement"
    }
  ]
}
```

Serialization is deterministic: object keys and option categories are sorted,
Polish characters remain unescaped, and insignificant whitespace is omitted.
Issue order is preserved. A serialize-deserialize round trip preserves text,
options, issue order, `None` versus empty-string suggestions, identifiers, and
all typed field values.

The decoder is deliberately strict. It rejects duplicate object keys, missing
or unknown fields, unknown schema versions, unknown enum values, malformed
identifiers and sources, booleans where numbers are required, non-finite
numbers, identifiers that do not match their identity fields, duplicate
categories or finding identifiers, and findings that do not match the source
text.

## Compatibility expectations

Schema version 1 is an exact closed schema. Producers must emit every documented
field, and consumers must not silently ignore unknown fields. Changes that add,
remove, rename, or reinterpret a field; add an enum value; or change identifier
identity inputs require a new schema version and an explicit compatibility path.
Documentation clarifications and validation fixes that do not alter accepted
data may retain the current version.

The current decoder accepts only schema version 1. Applications that persist
results should persist `schema_version` and must not assume a future package can
read an unsupported version without a documented migration.
