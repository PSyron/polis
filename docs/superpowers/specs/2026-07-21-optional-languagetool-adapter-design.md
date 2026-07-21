# Optional LanguageTool Adapter Design

## Scope and decision

Issue #53 adds a disabled-by-default, separately installed LanguageTool 6.8
sidecar as a narrow punctuation rule. It accepts only the reviewed
`BRAK_PRZECINKA_ZE` and `BRAK_PRZECINKA_ZEBY` rule IDs. The #52 corpus run
measured 18/18 exact gold comma insertions from those IDs and 0/10 changed
negative cases.

Broad spelling, whitespace, style, generic grammar, diagnostic-only, and
unreviewed rules remain excluded. LanguageTool findings use confidence below
0.9 and therefore are never selected by `Analyzer.correct()`.

## Configuration and transport

Omitting `[language_tool]` performs no sidecar work. When present, it requires
a literal `http://127.0.0.1:<port>` or `http://[::1]:<port>` endpoint and a
positive timeout. DNS names, TLS, credentials, paths, queries, fragments,
redirects, proxies, and unbounded responses are rejected.

Before the first user text handled by an adapter instance, it sends a fixed public probe
and requires `software.name == "LanguageTool"` and `software.version == "6.8"`.
Every user-text response is checked again. The transport never starts,
downloads, or discovers a server.

## Parsing and findings

Java UTF-16 offsets are converted to Python code-point offsets and verified
against the source. Each allowed wide replacement is reduced through its
longest common prefix and suffix. The only accepted normalized operation is a
single comma insertion. Multiple alternatives must normalize to the same edit;
no replacement, no-op, malformed, ambiguous, unknown, or conflicting matches
produce no finding.

All emitted findings use source `rule:languagetool.pl`, category punctuation,
severity suggestion, fixed project-authored messages, and confidence 0.85.
Server messages and raw payloads never enter public errors or logs.

## Failure policy

The rule is best-effort enrichment. Expected local transport, timeout, version,
schema, encoding, size, and offset failures return no LanguageTool findings,
leaving built-in deterministic findings intact. This is a narrow exception to
ADR-0003 for this optional disabled-by-default rule only; it does not change
LLM or required-component failure semantics. Synchronous HTTP can block
`analyze_async()` for at most the configured short timeout and is documented as
a limitation.

## Verification

Fast tests use authored payloads and fake transports. A slow opt-in test covers
the real 6.8 server. The corpus quality test requires exactly 18 allowlisted
gold punctuation edits, precision 1.0, recall 0.75 over 24 punctuation edits,
F1 approximately 0.857, and zero findings on all 10 negatives.
