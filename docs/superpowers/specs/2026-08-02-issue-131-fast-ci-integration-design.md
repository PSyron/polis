# Fast CI Generated-Invariant Integration Design

## Context

Issue #131 is the final child of #95. The completed generated suites already
use the repository-owned `unicode-structural-v1` helper with synthetic Unicode
input, seed `95001`, and a default budget of 64 cases. This issue makes that
bounded contract explicit in every supported Fast CI matrix job and preserves
the existing fast-suite boundary.

The change is CI policy and developer evidence only. It must not change Polis
runtime behavior, introduce dependencies, read analyzed text, alter sentence
safety corpora, run holdouts or models, or claim linguistic quality from
structural properties.

## Considered approaches

### A second generated-test job or invocation

A separate command could carry generated-test settings, but it would violate
the issue requirement that Fast CI have exactly one filtered pytest invocation
and would make the matrix's test boundary harder to audit.

### Pinned metadata without generator wiring

Put explicit environment assignments for the accepted generator version, seed,
and case budget on the existing pytest step but leave `tests.generative`
unchanged. This looks small but provides
only an audit label: every completed property suite would still read its hard
coded defaults, so the workflow metadata would not actually control its run.

### Validated test-only configuration wrapper with policy enforcement

Make the no-argument `generate_unicode_text_cases()` path resolve one
test-only three-field environment contract. With no fields it retains the
existing default version, seed, and 64-case budget. If any field is set, all
three must be present; the version must equal `unicode-structural-v1`, the
seed must be an unsigned 64-bit integer, and the case budget must be an integer
from 1 through 256. Calls that explicitly provide a seed or count retain their
direct test-fixture semantics.

Put the accepted environment assignments on the existing pytest step, leaving
its command unchanged. Extend the existing workflow validator and its
contract tests to require those literal accepted values, reject missing,
duplicate, invalid, or excessive fields and preserve the one-command and
marker-filter checks. Document the resulting replay procedure.

This is the selected approach. It gives each Fast CI matrix job a visible,
machine-checked contract that actually controls all completed property suites,
without creating an additional execution path or changing runtime behavior.

## CI policy contract

The `Run pytest suite` step remains the sole `pytest`/`unittest` command and
continues to run:

```console
pytest -m "not research and not slow and not model"
```

Its step-level environment pins these exact values:

```yaml
env:
  POLIS_GENERATIVE_GENERATOR_VERSION: unicode-structural-v1
  POLIS_GENERATIVE_SEED: 95001
  POLIS_GENERATIVE_CASES: 64
```

The existing 10-minute Fast CI job timeout and supported OS/Python matrix stay
unchanged. `64` is accepted because it is the generator's default bounded
budget and is no greater than the 256-case hard maximum. The generator accepts
no environment fields as its default configuration; once any field is present,
it fails closed unless all three are present and valid. The policy validator
additionally requires the exact accepted CI values, rejects duplicate
assignments, and rejects an absent, invalid, or excessive field.

The configuration is test-only. Every completed generated suite calls the
no-argument generator path and therefore consumes the pinned Fast CI metadata;
Polis runtime code never reads these values.

## Replay, evidence, and privacy

A Fast CI failure should be replayed locally with the same metadata using the
existing fast selector. The reported generator identity, seed, and case index
are safe metadata; neither the command nor failure guidance prints generated
or analyzed text. The documentation must list the eight synthetic Unicode
families and the completed #95 invariant modules: segmentation reconstruction,
finding/result fidelity, correction conflict/application, rule registry order,
and sync/async pipeline parity.

These properties establish structural evidence only: offsets, reconstruction,
ordering, deterministic application, and parity over a bounded synthetic
source. Authored regressions and corpus gates remain the authority for Polish
linguistic quality. Bounded coverage cannot prove exhaustive Unicode behavior,
find linguistic defects, replace corpus evaluation, or validate models and
holdouts.

## Testing and verification

Test the workflow policy and the test-only generator configuration first. The
workflow regressions mutate a temporary workflow to remove, duplicate, corrupt,
or over-budget each field; the generator regressions prove no-environment
defaults, complete valid configuration, partial configuration failure, and
invalid version/seed/budget failure. Each mutation must make the relevant
contract fail. Then make the minimal harness, workflow, validator, and
documentation updates, and run the focused policy/property suites, complete
fast suite, Ruff, formatting, mypy, and whitespace checks. The supported GitHub
matrix remains the required post-push evidence and cannot be fabricated
locally.
