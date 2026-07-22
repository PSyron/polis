# Privacy guarantees

Polis is designed for local analysis and avoids sending source text to networked
services.

Current guarantees:

- `polis.analyzer.Analyzer` and deterministic rules run fully in-process.
- CLI uses standard input / argument text and does not persist or upload it.
- `PolisError.context` intentionally contains only operation metadata (`operation`,
  `backend`, `path`, `finding_ids`), never analyzed fragments, full prompts, or raw
  response payloads.
- Specialist outcomes contain only a stable backend identifier, operation and
  protocol versions, status, suggestion count, and call count. They never carry
  source text, candidates, prompts, proposals, or raw responses.
- `[vendored_language_tool]` sends one sentence only to one persistent child
  process over local stdin/stdout. The child opens no network socket, and Polis
  does not download or update its Java artifacts.

## Operational defaults

- Exceptions are typed and stable (`code`, `retryable`, and `context`) to make
  local handling explicit.
- For local backend failures, we map transport/protocol issues to structured
  operational errors instead of exposing backend internals.
- Optional specialist failures use a fixed privacy-safe diagnostic and preserve
  completed deterministic findings. Injection does not authorize remote
  transport: a production adapter must separately enforce local-only execution.
- Vendored stdio failures expose only operation-level diagnostics; request text,
  response payloads, candidates, and corrections are not included in errors.
  Removing `[vendored_language_tool]` removes this optional process boundary.

## Recommended user practice

When testing or scripting:

- avoid logging full user texts at `DEBUG` level,
- avoid storing temporary files with sensitive text in world-readable paths,
- and rotate temporary working files when you capture CLI input/output.

## Audit status

For release-time privacy and dependency evidence, see
[Privacy and dependency audit](privacy-audit.md). It records network-blocking checks,
artifact scans, secret-detection status, and residual risks.
