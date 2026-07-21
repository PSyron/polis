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

## Enable the reviewed LanguageTool layer

LanguageTool is optional and disabled by default. Run a separately installed
LanguageTool 6.8 server on numeric loopback and add:

```toml
[language_tool]
base_url = "http://127.0.0.1:8081"
timeout_seconds = 1.0
```

The endpoint must use plain HTTP, an explicit port, and literal `127.0.0.0/8`
or `::1`; hostnames, credentials, paths, queries, proxies, redirects, other
versions, and remote services are rejected. The adapter keeps only two reviewed
Polish comma rules. Its confidence is deliberately below the automatic
correction threshold, so callers review and explicitly select its findings.

The call is synchronous and may wait for `timeout_seconds`, including through
`analyze_async()`. If the optional server is unavailable or returns invalid
data, analysis continues with the built-in rules and no LanguageTool findings.
Removing `[language_tool]` fully removes the adapter from the analyzer registry.
