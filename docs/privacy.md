# Privacy guarantees

Polis is designed for local analysis and avoids sending source text to networked
services.

Current guarantees:

- `polis.analyzer.Analyzer` and deterministic rules run fully in-process.
- CLI uses standard input / argument text and does not persist or upload it.
- `PolisError.context` intentionally contains only operation metadata (`operation`,
  `backend`, `path`, `finding_ids`), never analyzed fragments, full prompts, or raw
  response payloads.

## Operational defaults

- Exceptions are typed and stable (`code`, `retryable`, and `context`) to make
  local handling explicit.
- For local backend failures, we map transport/protocol issues to structured
  operational errors instead of exposing backend internals.

## Recommended user practice

When testing or scripting:

- avoid logging full user texts at `DEBUG` level,
- avoid storing temporary files with sensitive text in world-readable paths,
- and rotate temporary working files when you capture CLI input/output.

## Audit status

For release-time privacy and dependency evidence, see
[Privacy and dependency audit](privacy-audit.md). It records network-blocking checks,
artifact scans, secret-detection status, and residual risks.
