# Customization guides

`polis` exposes stable extension points for deterministic rules and local-generation
backends. The runtime `Analyzer` is intentionally narrow today; advanced
composition currently goes through the internal pipeline helpers.

## Add a custom deterministic rule

Implement `polis.core.Rule` and register it in `DeterministicRuleRegistry`.

```python
from polis.core import AnalysisOptions, Category, Confidence, Finding, Source, SourceKind, Severity
from polis.rules import DeterministicRuleRegistry, RuleRegistration
from polis.analysis.pipeline import analyze_text


class DoubleSpaceRule:
    @property
    def source(self) -> Source:
        return Source(SourceKind.RULE, "double_space")

    def find(self, text: str, *, options: AnalysisOptions) -> tuple[Finding, ...]:
        if "  " not in text:
            return ()

        index = text.index("  ")
        return (
            Finding.create(
                category=Category.STYLE,
                severity=Severity.WARNING,
                message="Double space",
                explanation="Two spaces are rarely intentional in running text.",
                original="  ",
                suggestion=" ",
                start=index,
                end=index + 2,
                confidence=Confidence(0.95),
                source=Source(SourceKind.RULE, "double_space"),
            ),
        )


registry = DeterministicRuleRegistry(
    [
        RuleRegistration(
            rule=DoubleSpaceRule(),
            categories=frozenset({Category.STYLE}),
        )
    ]
)

result = analyze_text(
    "To  jest tekst z podwójną spacją.",
    registry=registry,
    local_backend=None,
)
```

Rules should be deterministic and lightweight; keep one responsibility per rule and
prefer stable source identifiers.

## Add a custom local backend

For local-generation sources used in the pipeline, implement an object with:

- `name` attribute
- `generate_findings(text, policy=None, clock=None, sleep=None, operation=...)`

Returning an empty tuple is a valid backend behavior.

```python
import asyncio
from polis.analysis.pipeline import analyze_text_async
from polis.core import AnalysisOptions
from polis.core import Finding
from polis.rules import DeterministicRuleRegistry


class PassThroughBackend:
    name = "noop"

    async def generate_findings(
        self,
        text: str,
        *,
        policy: object | None = None,
        clock: object | None = None,
        sleep: object | None = None,
        operation: str = "analysis.llm.generate",
    ) -> tuple[Finding, ...]:
        del text, policy, clock, sleep, operation
        return ()


async def run_analysis() -> None:
    result = await analyze_text_async(
        "To jest tekst.",
        registry=DeterministicRuleRegistry(()),
        local_backend=PassThroughBackend(),
        options=AnalysisOptions(),
    )
    assert isinstance(result, tuple)

asyncio.run(run_analysis())
```

For validated structured backend responses, prefer `polis.llm.adapter.MockHeuristicBackend`
plus a dedicated transport implementation.

## Add a specialist suggestion backend

Issue #60 exposes `HybridSuggestionEngine` for role-separated #59 contracts. A
specialist backend implements `name` and asynchronous
`generate(request: PromptRequest) -> str`; a deterministic router returns
`SyntaxTask` or `InflectionTask` values for unresolved sentence-local work.
Inject the composed engine with `Analyzer(config, specialist_engine=engine)`.

The router, not the model, decides which operation is eligible. Candidate tasks
must use a finite candidate set containing the original surface form. Syntax
tasks can declare protected name spans; URLs, numbers, and quotations are
protected by the engine. The default analyzer injects neither component and
makes no specialist calls. A custom adapter must remain local, must not download
artifacts implicitly, and must preserve request roles and native chat templating.

## Enable the vendored sentence layer

The preferred sentence-only configuration shares one persistent local process
between the five reviewed comma rules and contextual inflection candidate
generation. Build the pinned subset explicitly first; Polis does not download
or update Java artifacts:

```console
cd third_party/languagetool-pl
./scripts/build.sh
```

Then use the absolute executable path:

```toml
[vendored_language_tool]
stdio_path = "/absolute/path/to/polis/third_party/languagetool-pl/scripts/run_stdio.sh"
timeout_seconds = 2.0
```

Construct the analyzer with `Analyzer.from_config(...)` and close it through a
`with` block or `Analyzer.close()`. Repeated sentence calls reuse one JVM.
Source-policy `1.1` automatically applies only qualified punctuation findings;
contextual inflection findings stay reviewable and require explicit
`apply_suggestions()` selection. The path, timeout, malformed response, and
process failures are bounded and preserve built-in deterministic findings.

Removing `[vendored_language_tool]` disables the shared process. The configured
path must be absolute and executable. This section is mutually exclusive with
the legacy `[language_tool]` and `[contextual_inflection]` modes below.

## Enable the reviewed LanguageTool HTTP layer

This compatibility mode is optional and disabled by default. Run a separately installed
LanguageTool 6.8 server on numeric loopback and add:

```toml
[language_tool]
base_url = "http://127.0.0.1:8081"
timeout_seconds = 1.0
```

The endpoint must use plain HTTP, an explicit port, and literal `127.0.0.0/8`
or `::1`; hostnames, credentials, paths, queries, proxies, redirects, other
versions, and remote services are rejected. The adapter keeps only five
explicitly reviewed Polish comma rule IDs. Source-policy version `1.1`
automatically applies their non-conflicting comma insertions; every other
LanguageTool rule remains filtered out.

The call is synchronous and may wait for `timeout_seconds`, including through
`analyze_async()`. If the optional server is unavailable or returns invalid
data, analysis continues with the built-in rules and no LanguageTool findings.
Removing `[language_tool]` fully removes the adapter from the analyzer registry.

## Enable per-call contextual inflection suggestions

Build the pinned local module, then point Polis at its absolute stdio runner:

```toml
[contextual_inflection]
stdio_path = "/absolute/path/to/polis/third_party/languagetool-pl/scripts/run_stdio.sh"
timeout_seconds = 2.0
```

The executable is invoked directly without a shell and receives one sentence
through stdin in a new process for each eligible call. It returns only finite
local candidates. Qualified surname and
narrow government findings remain reviewable: `correct()` does not apply them,
and callers must select their IDs through `apply_suggestions()`. Omission of
the section disables all contextual morphology I/O. Multi-sentence input also
skips this rule without starting the process.

The same configuration works with the sentence-oriented CLI example:

```console
python -m polis.cli --config examples/polis.toml analyze --json \
  "Rozmawiałem z Janem Nowak po przerwie."
```

The JSON output contains a reviewable `Nowakiem` suggestion. The CLI does not
apply it unless its finding ID is passed explicitly with `--apply`.
