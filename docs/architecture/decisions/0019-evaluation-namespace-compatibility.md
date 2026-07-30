# ADR-0019: Preserve `polis.evaluation` compatibility through the 0.x line

- Status: Accepted
- Date: 2026-07-29
- Owner: Paweł Cyroń
- Issue: #120

## Context

The runtime-first product boundary narrows Polis around the offline analyzer,
its typed result models, and the small supported package surface documented in
`polis` and `polis.core`. The repository still contains evaluation validators,
metrics, and corpus loaders under `polis.evaluation`. Those imports are used by
existing tests, documentation, and local development workflows.

Packaging cleanup for the runtime-first line excludes large non-runtime assets
from shipped artifacts. That cleanup raises a compatibility risk: `polis.evaluation`
could be removed or made incomplete as a side effect even though the current
0.x line still documents and exercises selected validator imports.

## Decision

For the current 0.x development line, `polis.evaluation` remains an
import-compatible namespace for repository evaluation tooling. Existing
documented validator imports, including `load_dataset()` and
`validate_dataset()`, remain available.

`polis.evaluation` is not the primary product interface for text analysis. The
supported runtime product surface remains the analyzer and result contracts
exported from `polis` and `polis.core`.

Runtime-first packaging must retain the lightweight `polis.evaluation` Python
modules needed for compatibility, but it must not ship large evaluation or
research payloads as part of that namespace. Large corpora, holdouts, reports,
experiments, and training assets remain excluded from distributable artifacts.

Any future extraction, removal, or deprecation of `polis.evaluation` requires
all of the following in a separate issue and implementation plan:

- an import inventory of the currently supported compatibility surface;
- an explicit migration or deprecation path for affected callers;
- documentation updates that distinguish the new home from the runtime API;
- artifact verification confirming the intended shipped boundary.

Silent removal of `polis.evaluation` during packaging cleanup is explicitly
rejected.

## Consequences

- The 0.x line keeps source compatibility for existing repository evaluation
  imports while the runtime product stays focused on the analyzer API.
- Runtime documentation must avoid presenting `polis.evaluation` as the main
  way to analyze text.
- Packaging and artifact checks may shrink shipped content, but not by breaking
  the accepted compatibility namespace.

## Alternatives considered

- **Remove `polis.evaluation` immediately.** Rejected because it would break
  accepted 0.x imports without an inventory, migration path, or dedicated
  compatibility change.
- **Promote `polis.evaluation` to a primary runtime API.** Rejected because the
  namespace serves repository evaluation and provenance workflows, not the
  supported analyzer contract.
- **Keep shipping all evaluation assets.** Rejected because runtime-first
  artifacts must exclude large corpora and research baggage that are not part
  of the supported runtime product.
