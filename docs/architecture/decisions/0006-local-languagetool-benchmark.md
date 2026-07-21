# ADR-0006: Keep LanguageTool optional and evaluate a narrow rule adapter

- Status: Accepted
- Date: 2026-07-21
- Owner: Paweł Cyroń
- Issue: #52

## Context

No evaluated local LLM satisfies the release quality gates. LanguageTool 6.8
offers an open-source Polish rule module and a local HTTP server, so it was
evaluated as a deterministic layer that could run before a smaller local
model.

The experiment used the Homebrew LanguageTool 6.8 bottle, OpenJDK 17.0.19,
`language=pl-PL`, and a server listening only on `127.0.0.1:8081`. The complete
33-case corpus was sent through POST `/v2/check`. A second measured run used
invalid external HTTP/HTTPS proxies and an explicit loopback exception; it
still completed through the local endpoint. `lsof` showed only the loopback
listener for the server process.

## Evidence

The corpus contains 23 incorrect cases and 10 correct hard negatives. All
positive cases now contain explicit gold edits. The report identified the
corpus by SHA-256
`d5ce257f78a67ad2bdc6ed71ed1ec4f4403d0f287a71db7a316e68bd32f4d468`.

| Measurement | Result |
| --- | ---: |
| Complete expected outputs | 17/33 |
| Incorrect cases completely corrected | 7/23 |
| Correct negatives unchanged | 10/10 |
| Exact gold edits | 3/50 |
| Exact edit precision / recall / F1 | 0.088 / 0.060 / 0.071 |
| Exact spelling edit precision / recall / F1 | 1.000 / 1.000 / 1.000 |
| Warm latency p50 / p95 | 46.8 ms / 59.7 ms |
| Cold start through first completed check | 1,340 ms |
| Java RSS after first check | 644,880 KiB |
| LanguageTool installation | 413.7 MB |
| OpenJDK 17 installation | 319.4 MB |

LanguageTool completely corrected the three spelling cases, three spacing
cases, and the simple missing comma before `że`. It did not correct agreement,
surname inflection, the subordinate-clause rewrite, or the combined
inflection/syntax cases. It returned partial punctuation findings for several
combined cases but could not produce their complete expected outputs.

Exact edit metrics are deliberately stricter than corrected-output metrics.
LanguageTool frequently represents an insertion as a wider replacement, for
example replacing `,p` with `, p`. That can produce the correct text but does
not match the corpus insertion span. A production adapter would need a tested
minimal-edit normalization policy before its findings could be compared or
merged as Polis findings.

## Decision

LanguageTool is not adopted as the default Polish analyzer and does not replace
the existing deterministic rules. Its general grammar output is not accurate
enough for automatic correction on this corpus, and a roughly 733 MB external
runtime footprint is too large for a mandatory dependency.

The result does justify a separate, optional integration experiment limited to
reviewed high-precision rule IDs and categories. That follow-up may expose a
loopback LanguageTool sidecar as a rule analyzer, normalize edits, and feed only
validated residual findings into later analysis. It must remain disabled by
default and must not make its suggestions automatically applicable until its
own allowlist passes zero-negative and per-category gates.

The small local LLM remains responsible only for residual contextual problems,
especially word order and constructions that deterministic rules cannot
resolve. LanguageTool is a possible first layer, not a replacement for that
model.

## Consequences

- The production Python package keeps zero runtime dependencies.
- Public or premium LanguageTool APIs remain prohibited by the offline policy.
- A follow-up issue may implement an optional local adapter with strict
  version, loopback, offset, category, and allowlist validation.
- The benchmark remains reproducible and its generated report stays ignored
  because reports may describe local runtime details.
