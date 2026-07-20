# Architecture Decision Records

Architecture Decision Records (ADRs) preserve decisions that shape Polis across
multiple milestones. An ADR is immutable once accepted; a later ADR supersedes it
when the policy changes.

| ADR | Status | Decision |
| --- | --- | --- |
| [ADR-0001](decisions/0001-python-platform-licensing-policy.md) | Accepted | Python, platform, licensing, and asset policy |
| [ADR-0002](decisions/0002-polish-nlp-dependency-strategy.md) | Accepted | Standard-library-first Polish NLP dependency strategy |
| [ADR-0003](decisions/0003-public-api-and-exception-contract.md) | Accepted | Public API and exception contract |

The [analyzer and local backend protocol boundary](protocols.md) records the
runtime implementation seams that follow the accepted public API contract.
