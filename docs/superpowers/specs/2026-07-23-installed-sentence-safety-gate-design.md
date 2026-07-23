# Installed Sentence Safety Gate Design

## Scope

Issue #115 runs the installed-package sentence safety gate exactly once against
the independent corpus created by #114. It is the execution task that resolves
the older release-gate issue #76: a fully qualifying result closes #76, while a
failed result is recorded on #76 and leaves it open.

The work is sentence-only. It does not evaluate paragraphs, tune against
holdout evidence, qualify a production model, use corpus v3, or broaden the
majority coverage work owned by #85 and #90. A narrowly qualified analyzer
change derived only from the visible development split is permitted before the
configuration is frozen.

## Selected approach

Use a selective port from the closed, unmerged PR #79. Recover its installed
runner, scorer, artifact audit, privacy-safe reporting, native evidence, and
atomic one-shot reservation. Do not recover its corpus-v3 configuration,
development or holdout results, frozen hashes, consumed marker, or claims.

This is safer than cherry-picking PR #79 because none of its consumed evidence
can appear in the new experiment. It is safer than a rewrite because the
complex process, sandbox, resource, artifact, and report validation has already
been exercised.

## Experiment identity and files

The new experiment lives under `experiments/sentence_safety_gate/` and uses a
new identifier, configuration schema instance, report, frozen-gate record, and
holdout marker. The installed subprocess entry point is
`scripts/run_sentence_safety_case.py`.

The committed configuration identifies:

- `polis_polish_correction_safety_corpus_v1`;
- the canonical frozen digest
  `2fc05cd5552071ade7b392b3075d15bfaf57cf3f4b84df450c605b48d1615982`;
- the equivalent JSON and XML files;
- source-policy version `1.1` and the exact automatic/reviewable source sets;
- the LanguageTool 6.8 vendored runtime identity;
- all unchanged #76 quality and performance thresholds;
- the `macos-arm64-v1` evidence profile.

No result or marker from PR #79 is copied into this directory.

## Split isolation

Development and holdout loading are separate capabilities.

The development loader streams only the 80 `development` records from XML. It
must not materialize, retain, hash, log, or expose holdout text or gold edits.
The installed runner receives only one source sentence and frozen runtime
configuration; it never receives gold edits, expected output, protected labels,
or corpus identity.

The holdout loader is unavailable until all freeze inputs and the closed
development report verify and a matching one-shot marker has been created
atomically. It then uses the safety-corpus quality-gate selector to materialize
exactly 160 reviewed holdout cases for the scorer.

## Installed runner

Fresh wheel and sdist artifacts are built from the immutable #115 evaluation
snapshot recorded in `evaluated_source.json`. Their contents are audited before
use, installed offline into clean environments, and smoke-tested outside the
repository. Final evidence documentation and conservative post-verdict
maintenance are not represented as evaluated artifact contents. The persistent
wheel-installed runner constructs one `Analyzer` and exercises:

- `Analyzer.analyze()`;
- `Analyzer.correct()`;
- `CorrectionResult.apply_suggestions()`.

It returns a closed, versioned JSON response containing public finding fields,
the two correction results, structured suggestion outcomes, timing, resource
measurements, model-call count, and the analyzer-owned LanguageTool process
start count. A read-only analyzer diagnostic exposes only that count and no
analyzed text.

The runner rejects paragraphs, malformed requests, an import outside the clean
installation, non-absolute optional-runtime paths, and invalid source/channel
classification. Diagnostic errors never include analyzed text.

## Scoring semantics

Every observed edit is validated against the original sentence with Unicode
half-open offsets `[start, end)`. Automatic and explicitly selected reviewable
applications must reconstruct the runner outputs without overlap or conflict.

Gold matching uses only exact `(start, end, original, suggestion)` values.
Category and source are used solely for breakdowns. Automatic and reviewable
channels are disjoint.

Metrics follow #81:

- precision is undefined when a channel proposes no edits and therefore cannot
  pass a non-vacuous gate;
- automatic correction accuracy is exact expected-output equality among cases
  changed automatically;
- reviewable outcome validity is reported independently;
- recall is reported by category and source but cannot weaken safety gates;
- protected hard negatives are counted as cases changed automatically and
  reviewable findings emitted.

## Development and freeze phase

All reversible work finishes before holdout reservation:

1. validate the configuration and safety-corpus identities;
2. build and audit fresh wheel and sdist artifacts;
3. install and smoke-test both artifacts offline;
4. build or verify the vendored LanguageTool runtime without network access;
5. run the optional-component failure case;
6. complete macOS sandbox, network-denial, process, socket, pipe, RSS, and swap
   preflights;
7. run the complete 80-case development split twice;
8. validate quality, stability, performance, privacy, and report schema;
9. freeze hashes for configuration, evaluator, gate contracts, installed
   runner, source policy, corpus representations, LanguageTool inputs,
   artifacts, and the canonical closed development report.

The development phase cannot create a holdout marker or load holdout gold. If
any gate fails, the configuration is not frozen.

## Development-derived reviewable inflection support

The first development execution correctly failed closed because the
`reviewable` channel proposed no edits. Root-cause tracing established that the
installed runner and shared vendored LanguageTool process work: an existing
supported contextual-inflection example produces a reviewable finding. The 80
development cases contain none of the four existing contextual-inflection
evidence families and none of the two residual syntax families.

The selected development-only adjustment extends the existing
`rule:languagetool.contextual_inflection` source with one narrow nominal
agreement family. It considers an adjacent pair only when the left surface is a
plausible Polish adjective or demonstrative and the right surface is a
plausible feminine accusative noun. The local morphology bridge must then
confirm:

- the right surface has a `subst:sg:acc:f` reading;
- the left surface has an adjective reading;
- exactly one left candidate agrees in singular, accusative, and feminine;
- the candidate differs from the source surface.

The resulting finding remains reviewable and is never added to the automatic
source policy. The implementation reuses the existing bounded
`synthesize_context` protocol, stable candidate identity, conflict rejection,
and fail-closed response validation. It does not change the Java bridge,
production dependencies, gate thresholds, corpus, source-policy version, or
configured source sets.

Tests cover demonstrative and ordinary adjective corrections, an already
agreeing phrase, non-feminine/non-accusative neighbors, malformed morphology,
and protected development negatives. After focused and full verification, new
wheel and sdist artifacts are built and the full 80-case development gate is
run again. Only a qualifying report may be frozen; holdout access still
requires the separate owner checkpoint.

### Post-verdict disposition

The one-shot holdout later rejected the complete reviewable source with `0 TP /
2 FP`. The nominal-agreement extension was therefore removed from active
runtime without selecting a replacement or inspecting the consumed records for
tuning. The evaluated commit, tree, and distribution hashes remain separately
recorded so the negative result is not attributed to the post-verdict runtime.

## Explicit owner checkpoint

After a qualifying development report and frozen-gate record exist, execution
stops. The owner receives the development verdict, exact frozen identities,
preflight evidence, and the command that would reserve the holdout.

The assistant must not run the holdout until Paweł Cyroń explicitly replies
with an instruction equivalent to `run the holdout`. The earlier authorization
to implement #115 does not authorize this irreversible step.

## One-shot holdout phase

After explicit owner authorization, holdout execution revalidates every frozen
input and recomputes the development decision rather than trusting a serialized
boolean. It repeats all unavoidable native preflight checks, then creates the
new holdout marker atomically and durably before materializing any holdout
record. Reusable post-verdict maintenance flushes and fsyncs the marker and its
parent directory on the POSIX release profile. The evaluated snapshot used
exclusive creation but did not perform those durability syscalls; its marker
was nevertheless retained before materialization and remains consumed. This
maintenance must not be used to rerun that holdout.

An existing marker, mismatched hash, failed preflight, or changed report fails
closed. The marker is retained whether evaluation passes, fails, or is
interrupted, so the same holdout cannot run again.

The final privacy-safe report records identifiers, counts, metric values,
source/category breakdowns, hashes, timing, resource evidence, environment
identity, and the verdict. It contains no source sentence, expected output,
original span text, suggestion text, raw model/runtime response, or private
path.

## Quality gates

The predeclared #76 thresholds remain unchanged:

- automatic exact-edit precision `1.00`;
- automatic correction accuracy `1.00`;
- zero automatically changed protected hard negatives;
- reviewable exact-edit precision at least `0.90`;
- structured outcome validity `1.00`;
- zero reviewable findings on protected hard negatives;
- warm in-process p95 at most `100 ms`;
- warm installed-runner p95 at most `500 ms`;
- combined peak RSS at most `1 GiB`;
- zero swap growth, sockets, and model calls;
- exactly one analyzer-owned LanguageTool process start;
- two stable repetitions.

Both channels must propose at least one edit to receive a precision verdict.

## Result publication

The final result is posted to #115 and #76 with the frozen configuration,
artifact, corpus, report, and marker identities.

- If every gate passes, #115 and #76 may be closed as completed.
- If any gate fails, #115 is closed as a completed one-shot experiment, #76
  stays open, and the consumed holdout must not be rerun or used for tuning.

Documentation remains explicit that evidence is sentence-only and does not
qualify paragraph support or a production model.

## Error handling

Closed-schema, identity, artifact, offset, reconstruction, channel, report,
privacy, platform, sandbox, network, process, socket, resource, stability, and
one-shot violations all fail closed with non-zero status. Errors retain only
privacy-safe identifiers and never analyzed or expected text.

Optional component failure is acceptable only in its dedicated negative test,
where deterministic behavior remains intact and unavailable optional sources
abstain safely.

## Testing

Tests are written before implementation and cover:

- exact configuration and safety-corpus identity;
- 80/160 split isolation and absence of holdout materialization in development;
- scorer-only gold data and runner request closure;
- Unicode offsets, edit reconstruction, and channel separation;
- #81 undefined/non-vacuous precision semantics;
- protected hard negatives and optional-component failure;
- privacy-safe reports and error messages;
- complete freeze hashing and development-report recomputation;
- atomic one-shot reservation, mismatch rejection, and repeat denial;
- wheel/sdist content, clean offline installation, and import origin;
- macOS sandbox, network, socket, process, pipe, RSS, and swap evidence;
- deterministic repeated development execution;
- the explicit absence of a holdout marker before owner authorization.

Before the owner checkpoint, focused tests, the full pytest suite, Ruff,
formatting, mypy, real vendored LanguageTool integration, distribution audits,
clean installations, and the complete development evaluation must pass.
