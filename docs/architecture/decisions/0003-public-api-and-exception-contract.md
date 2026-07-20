# ADR-0003: Public API and exception contract

- Status: Accepted
- Date: 2026-07-20
- Owner: Paweł Cyroń
- Issue: #6

## Context

The immutable, schema-versioned public models are already approved. Before
orchestration, local backends, and correction code are implemented, Polis needs
a stable construction API, analysis failure policy, and correction contract.
The API must remain offline-only and never expose analyzed text through errors.

## Decision

### Entry points

The future package root exposes `Analyzer`, `AnalyzerConfig`, the existing
`AnalysisOptions` and `AnalysisResult`, and the exception hierarchy below.

```python
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Self

class AnalyzerConfig:
    def __init__(self) -> None: ...
    @classmethod
    def from_toml(cls, path: str | Path) -> Self: ...

class Analyzer:
    def __init__(self, config: AnalyzerConfig) -> None: ...
    @classmethod
    def from_config(cls, path: str | Path) -> Self: ...
    def analyze(self, text: str, *, options: AnalysisOptions | None = None) -> AnalysisResult: ...
    async def analyze_async(self, text: str, *, options: AnalysisOptions | None = None) -> AnalysisResult: ...

class AnalysisResult:
    # Existing fields, constructor, validation, and JSON methods remain unchanged.
    def apply(self, issue_ids: Iterable[str]) -> str: ...
```

The existing canonical `polis.core.models.AnalysisResult` declaration gains
`apply`; `polis.core.AnalysisResult` and `polis.AnalysisResult` directly re-export
that same class. There is no subclass or parallel result type. Both analyzer
methods return that exact class, so assignments among either import and the
analyzer return type-check in both directions.

`Analyzer(config)` accepts an already validated typed configuration.
`Analyzer.from_config(path)` and `AnalyzerConfig.from_toml(path)` read only the
explicit local TOML path, never a network or implicit working-directory file.
`analyze()` is the synchronous primary call. `analyze_async()` is its
event-loop-safe equivalent with identical input, filtering, ordering, result,
and failure semantics; it does not create or own an event loop.

`text` must be a `str`; ordinary wrong Python types raise `TypeError`. With
`options=None`, the effective options are `AnalysisOptions()`; otherwise the
given immutable category and confidence filters are used unchanged and recorded
in `result.options`. Returned findings have a stable canonical order, never
backend completion order.

### Failure and partial-result policy

One call is atomic: it returns a fully validated `AnalysisResult` for the
configured scope or raises a `PolisError`. No partial `AnalysisResult` is returned.
Deterministic findings are not silently returned when a configured
backend is unavailable, times out, or provides invalid data. This preserves the
current closed schema-version-1 result, which has no diagnostics or
omitted-source state. A future partial-analysis feature requires an explicit,
versioned outcome type and must not reinterpret a successful result as partial.

An invalid backend response is one that fails decoding, its declared schema,
result-model invariants, source-span validation, allowed source checks, or a
configured response limit. It is rejected before a result is returned.

### Correction selection

`result.apply(issue_ids)` consumes the iterable once. Every identifier must be
a non-empty string, appear once, identify a finding in that exact result, and
name a finding with a non-`None` suggestion. An empty iterable returns the
original text. Unknown, duplicate, and unsuggestable selections raise a
`CorrectionSelectionError` subclass.

Selections conflict when non-empty half-open spans overlap, an insertion is at
or inside a selected replacement's closed boundary, or two insertions share an
offset. Touching non-empty ranges are compatible. The endpoint rule is
intentionally conservative: a caller must choose between an insertion and a
replacement at its boundary. The operation is atomic: it validates the complete
selection before output. For valid selections, replacements are applied from
greatest `start` to least; output is independent of selection order.

### Exception hierarchy

```python
class PolisError(Exception):
    code: str
    retryable: bool
    context: Mapping[str, str]

class ConfigurationError(PolisError): ...
class BackendUnavailableError(PolisError): ...
class AnalysisTimeoutError(PolisError): ...
class InvalidBackendResponseError(PolisError): ...
class CorrectionSelectionError(PolisError): ...
class UnknownFindingError(CorrectionSelectionError): ...
class UncorrectableFindingError(CorrectionSelectionError): ...
class CorrectionConflictError(CorrectionSelectionError): ...
```

`code`, `retryable`, the exception type, and the allowed context fields are
stable. `code` is lowercase and dot-separated. Context always contains
`operation`; `from_config` failures contain `path`, backend failures contain
`backend`, and correction failures contain `finding_ids` as a comma-separated,
lexicographically sorted list. Error text and context never include analyzed
text, source fragments, suggestions,
prompts, full backend output, or secrets.

| Exception | Condition | Code | Retryable | Context |
| --- | --- | --- | --- | --- |
| `ConfigurationError` | Missing, unreadable, malformed, or invalid configuration | `configuration.invalid` | No | `operation`, `path` |
| `BackendUnavailableError` | Configured local backend cannot start, be reached, or is unavailable | `backend.unavailable` | Yes | `operation`, `backend` |
| `AnalysisTimeoutError` | Configured analysis deadline expires | `analysis.timeout` | Yes | `operation`, `backend` |
| `InvalidBackendResponseError` | Backend output fails decoding, schema, safety, or validation | `backend.invalid_response` | No | `operation`, `backend` |
| `UnknownFindingError` | A selected ID is absent or duplicated | `correction.unknown_finding` | No | `operation`, `finding_ids` |
| `UncorrectableFindingError` | A selected finding lacks a replacement | `correction.uncorrectable_finding` | No | `operation`, `finding_ids` |
| `CorrectionConflictError` | Selections overlap or share an ambiguous boundary | `correction.conflict` | No | `operation`, `finding_ids` |

OS errors while reading a caller-owned configuration path are wrapped in
`ConfigurationError`. Programmer type errors and implementation defects are not
silently converted to controlled operational failures.

### Executable contract

The typing-only stub tree has one nominal `AnalysisResult` declaration in
`polis.core.models`; the `polis.core` and `polis` stubs directly re-export it.
It extends the future public surface only for type checking and has no runtime
module. Strict examples verify bidirectional result compatibility, synchronous
and asynchronous success, and every controlled public failure leaf. Runtime
implementation must preserve these signatures before exporting them from
`polis`.

## Consequences

- Later protocol and implementation work has stable entry points and errors.
- Applications distinguish retryable operational faults without parsing prose.
- A successful result never conceals a failed configured analyzer.

## Alternatives considered

- Returning findings plus hidden backend diagnostics was rejected because it
  would make incomplete results look complete under the closed JSON schema.
- Async-only calls were rejected because scripts and synchronous applications are
  primary library consumers.
- Automatic correction application was rejected because explicit non-conflicting
  selection is required for minimal, justified edits.
- Raw backend text in errors was rejected because it can disclose private input.

## Verification

```bash
uv run --locked --extra dev pytest tests/test_api_contract.py -v
uv run --locked --extra dev python scripts/typecheck_api_contract.py
```

The second command is portable across POSIX shells, PowerShell, and Command
Prompt. Its standard-library runner supplies the dedicated stub directory to
mypy without shell-specific environment-assignment syntax.
