# Deterministic Unicode Property Harness Design

## Context

Issue #95 requires bounded, replayable structural properties before broader
internal migrations can affect original-text offsets. Issue #123 is the first
atomic child: it owns only the shared test generator, safe replay contract, and
documentation. Later children own segmentation, finding/result, correction,
registry, pipeline, and CI properties.

The harness must preserve the offline product boundary, add no production
dependency, use only synthetic data, and never put analyzed text into its
failure message. It is structural test infrastructure, not Polish linguistic
quality evidence.

## Considered approaches

### Hypothesis

Hypothesis provides mature strategies and shrinking, but it would add and
govern a new development dependency before shrinking or example persistence has
a current consumer. Its default counterexample reporting is also broader than
the seed-only failure contract required here. This remains a future option if
the repository-owned domain becomes too complex to maintain.

### `random.Random`

A private `random.Random` instance avoids global state and can be seeded, but a
test would still need to pin the exact pseudo-random call sequence to make
generator changes and cross-version drift explicit. The helper needs indexed
replay rather than mutable-stream replay, so a random stream does not simplify
the contract.

### Versioned hash-indexed generation

Use SHA-256 over the canonical ASCII tuple
`<generator-version>:<seed>:<case-index>` and derive every selection from its
digest. Each case is independently replayable and the algorithm is stable
across the supported Python and operating-system matrix. This approach uses the
standard library, has no mutable global state, and makes a generator-version
bump mandatory when the algorithm or fragment catalog changes.

This is the selected approach.

## Public test-support contract

Create `tests/generative.py` with these test-only values and types:

- `GENERATOR_VERSION = "unicode-structural-v1"`
- `DEFAULT_SEED = 95001`
- `DEFAULT_CASES = 64`
- `MAX_CASES = 256`
- `UNICODE_FAMILIES`, the exact family names `ascii`,
  `polish_diacritics`, `non_bmp`, `combining_marks`, `lf`, `crlf`,
  `punctuation`, and `quotes`
- immutable `Replay(generator_version, seed, case_index)`
- immutable `SyntheticTextCase(replay, families, text)`, with `text` excluded
  from `repr`
- `generate_unicode_text_cases(seed=..., count=...)`
- `assert_structural_invariant(condition, invariant, replay)`

Seeds are integers in `[0, 2**64 - 1]`. Case budgets are integers in
`[1, MAX_CASES]`; booleans are not integers for either contract. Invalid types
raise `TypeError`, while out-of-range values raise `ValueError`, before any case
is generated.

Case index zero is the explicit empty-string case. Every later case includes
one mandatory family selected by cycling through the ordered family catalog;
digest bytes select any additional families, fragment repetitions, separators,
and fragment ordering. Therefore the default 64-case run covers every declared
family while still producing combinations that vary by seed. Case generation
returns an immutable tuple with exactly `count` entries.

`Replay.__str__` and the representation of both data classes contain only the
generator version, seed, case index, and family names. Generated text is never
included. `assert_structural_invariant` accepts only a stable invariant name
matching `[a-z][a-z0-9_.-]{0,63}` and raises `AssertionError` containing that
name plus the replay metadata when the condition is false. This gives later
property tests a common privacy-safe failure path.

## Synthetic family catalog

The catalog uses project-authored literals only:

- ASCII words and spaces;
- Polish letters with diacritics;
- emoji and another non-BMP scalar;
- a decomposed base letter plus combining mark;
- `\n` and `\r\n` boundaries;
- sentence and clause punctuation;
- ASCII, Polish, and typographic quote characters.

The family label records structural coverage. It does not assert that a string
is grammatically correct or representative of Polish prose.

## Replay and budget

The initial local and Fast CI defaults are generator version
`unicode-structural-v1`, seed `95001`, 64 cases, and a hard maximum of 256
cases per generated property call. A failing case is replayed by calling the
same property with the reported version, seed, and case index; until the final
CI-integration child pins environment wiring, tests call the versioned helper
directly with these constants.

Later issues may add command-line or environment selection only through a
separate accepted contract. This issue does not read ambient environment state,
which keeps local and CI behavior identical.

## Error handling and privacy

The helper never reads files, uses the network, or accepts analyzed user text.
All generated strings are synthetic. Even so, the failure contract is designed
for the stricter production privacy boundary: safe diagnostics include only an
invariant name and replay metadata. The sentinel tests prove that neither data
class representation nor an invariant failure contains case text.

## Testing

Tests first import the missing support API and fail. The minimal implementation
then demonstrates:

- exact repeated-run reproducibility;
- different-seed divergence;
- exact count and input validation;
- empty-case behavior and complete default family coverage;
- privacy-safe representations and assertion failures;
- no production or dependency changes.

The full fast pytest suite, Ruff lint, Ruff format check, and mypy must pass
before the focused commit and PR.

## Consequences and limitations

The harness gives deterministic structural breadth but no shrinking and no
claim of exhaustive input coverage. Its bounded cases cannot prove linguistic
quality; authored regressions and corpus gates remain authoritative. Any defect
found by a later property suite must receive a separate regression-first bug
issue rather than expanding the property issue.
