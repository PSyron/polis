# Public Analysis Models

Polis exposes immutable, typed data models from both `polis` and `polis.core`.
This contract describes analysis data only. Analyzer orchestration and correction
application are not part of the current package.

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
