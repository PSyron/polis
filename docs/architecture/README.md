# Architecture Decision Records

Architecture Decision Records (ADRs) preserve decisions that shape Polis across
multiple milestones. An ADR is immutable once accepted; a later ADR supersedes it
when the policy changes.

| ADR | Status | Decision |
| --- | --- | --- |
| [ADR-0001](decisions/0001-python-platform-licensing-policy.md) | Accepted | Python, platform, licensing, and asset policy |
| [ADR-0002](decisions/0002-polish-nlp-dependency-strategy.md) | Accepted | Standard-library-first Polish NLP dependency strategy |
| [ADR-0003](decisions/0003-public-api-and-exception-contract.md) | Accepted | Public API and exception contract |
| [ADR-0004](decisions/0004-local-llm-backend-selection.md) | Accepted | First local backend strategy and seed selection for MVP |
| [ADR-0005](decisions/0005-real-local-polish-model-benchmark.md) | Accepted | No real model selected for automatic correction yet |
| [ADR-0006](decisions/0006-local-languagetool-benchmark.md) | Accepted | LanguageTool remains optional pending a narrow allowlisted adapter |
| [ADR-0007](decisions/0007-vendored-polish-languagetool-module.md) | Accepted | Source-built Polish LanguageTool 6.8 subset for M4 |
| [ADR-0008](decisions/0008-hybrid-correction-policy.md) | Accepted | Rules-first hybrid correction and suggestion policy for M5 |
| [ADR-0009](decisions/0009-specialist-prompt-benchmark.md) | Accepted | No specialist prompt protocol qualifies |
| [ADR-0010](decisions/0010-inflection-candidate-generation.md) | Accepted | LanguageTool supplies finite inflection candidates |
| [ADR-0011](decisions/0011-reject-bielik-1.5b-qlora.md) | Accepted | Bielik 1.5B QLoRA is rejected for the production backend |
| [ADR-0012](decisions/0012-reject-constrained-qwen35-2b.md) | Accepted | Constrained Qwen3.5 2B is rejected for the production backend |
| [ADR-0013](decisions/0013-reject-sentence-category-routing.md) | Accepted | Current sentence category-routing model matrix is rejected |
| [ADR-0014](decisions/0014-qualify-broader-polish-languagetool-rules.md) | Accepted | Four broader Polish LanguageTool sentence rules qualify |
| [ADR-0015](decisions/0015-qualify-contextual-inflection-routing.md) | Accepted | Deterministic contextual inflection routing qualifies as a suggestion source |
| [ADR-0016](decisions/0016-reject-qwen17-sentence-syntax-route.md) | Accepted | Qwen3 1.7B residual sentence syntax route is rejected |

The [analyzer and local backend protocol boundary](protocols.md) records the
runtime implementation seams that follow the accepted public API contract.
