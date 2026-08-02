# Issue #146 Sentence Safety Gate v2 Design

## Authority and scope

GitHub issue #146 owns the one-shot installed-package evaluation of the frozen
`polis_polish_correction_safety_corpus_v2` corpus created by #119. The
experiment keeps every quality and performance threshold from #76 unchanged.
It is optional research under ADR-0020 and cannot block or redefine the
supported offline runtime release.

The maintainer authorized #146 to proceed autonomously through the holdout
after every reversible development requirement passes. That authorization does
not allow early holdout access, a repeat after reservation, tuning from holdout
evidence, threshold changes, or use of either consumed corpus-v3 or safety-v1
holdout.

## Selected approach

Create a new `experiments/sentence_safety_gate_v2/` experiment with new
configuration, evaluated-source, frozen-development, one-shot marker, and final
report identities. Import only the generic installed runner, scoring, artifact,
privacy, resource, and freeze primitives retained from #115; keep all
v2-specific loading, approval, reservation, admission, and report code in the
new package. Do not copy its configuration, reports, marker, results, corpus
identities, hashes, or case-level evidence.

This keeps the proven process without duplicating two large modules and while
separating the new decision from both consumed experiments. Updating the old
experiment in place would weaken its value as immutable negative evidence.
Rewriting the complete evaluator would add avoidable process and privacy risk.

## Frozen identities

The new configuration binds at least:

- corpus ID `polis_polish_correction_safety_corpus_v2`;
- candidate digest
  `c64f009f14f0cde8390a46acc24660305534576bc897f70e281ffebbbbca6f53`;
- frozen digest
  `53cfce6b9cbe3f188290a064b34527912ea8f2a85c9ed29a67984c5ef5caaa29`;
- the exact approval manifest and equivalent JSON/XML corpus representations;
- the active source-policy version and exact automatic/reviewable source sets;
- the installed runner, evaluator, schemas, quality contracts, runtime
  identities, and target evidence profile;
- the exact source commit/tree and freshly built wheel and sdist artifacts.

Any identity drift fails closed and requires a new experiment version. It must
never be repaired by changing a frozen file or deleting a marker.

## Phase 1: reversible development audit

Development code streams only the 80 `development` records. It must not
materialize, retain, hash, log, or expose holdout text or gold edits. The
installed runner receives one source-visible sentence and closed runtime
configuration; scorer-only gold remains in the evaluation process.

The phase performs these checks before any holdout reservation:

1. validate corpus identity, approval evidence, JSON/XML equivalence, and the
   absence of an existing v2 marker;
2. build and audit fresh wheel and sdist artifacts from the exact source tree;
3. install and smoke-test both artifacts offline in clean environments;
4. verify vendored LanguageTool and optional-component failure behavior;
5. verify network denial, process/socket/pipe bounds, RSS, swap, and private
   path controls on the target macOS evidence profile;
6. execute all 80 development cases twice through the installed public API;
7. validate exact edits, reconstructed outputs, channel separation, quality,
   performance, stability, protected negatives, and report privacy;
8. freeze every input hash and the canonical closed development report.

No analyzer, source policy, threshold, or runtime behavior may be tuned in
#146. If either development repetition or any preflight fails, the experiment
stops without creating a marker or opening holdout data.

## Installed runner and scoring

Fresh installed artifacts exercise `Analyzer.analyze()`,
`Analyzer.correct()`, and explicit `CorrectionResult.apply_suggestions()`.
The runner response uses a closed versioned schema and contains only public
finding fields, correction outcomes, timings, resource measurements, model
call count, and analyzer-owned LanguageTool process count.

All edits are checked against the original sentence with Unicode half-open
offsets `[start, end)`. Gold matching uses exact `(start, end, original,
suggestion)` tuples. Automatic and reviewable channels are separate. Undefined
precision from zero proposed edits cannot pass a gate.

The unchanged thresholds are:

- automatic exact-edit precision `1.00`;
- automatic correction accuracy `1.00`;
- zero automatically changed protected hard negatives;
- reviewable exact-edit precision at least `0.90`;
- valid structured outcomes `1.00`;
- zero reviewable findings on protected hard negatives;
- warm in-process p95 at most `100 ms`;
- warm installed-runner p95 at most `500 ms`;
- combined peak RSS at most `1 GiB`;
- zero swap growth, sockets, and model calls;
- exactly one analyzer-owned LanguageTool process start;
- two identical development decisions.

## Phase 2: irreversible one-shot holdout

The holdout command first revalidates all frozen identities and recomputes the
development decision. Only a complete pass can continue. It then creates a new
v2 marker using exclusive creation, flushes and synchronizes the marker and
its parent directory, and verifies the persisted reservation before requesting
quality-gate access.

Successful synchronization returns a process-local, unforgeable, single-use
reservation capability. No capability is returned when any write, flush, file
`fsync`, or parent-directory `fsync` step fails. The loader requires and
consumes that capability before reading raw corpus or approval bytes. A marker
without the capability, including a manually created marker or one left by a
failed synchronization, permanently blocks execution but cannot authorize
evidence access. A consumed capability cannot authorize a second load.

Only after reservation may the corpus-v2 selector validate the exact raw
corpus and approval manifest and materialize exactly 160 reviewed holdout
cases. The marker remains consumed whether evaluation passes, fails, crashes,
or is interrupted. Existing or mismatched markers always reject execution.

No person or development tool receives case-level holdout output. The command
returns only an aggregate privacy-safe report and exit status. There is no
retry path.

## Reports and result publication

Committed reports may contain corpus/configuration/artifact identities, counts,
aggregate metrics, category/source breakdowns, timings, resource evidence,
environment identity, and verdict. They must not contain sentence text,
expected output, original spans, suggestion text, raw runtime responses,
private paths, or per-case outcomes.

The final result is posted to #146 and #76:

- if every gate passes, #146 and #76 may close as completed;
- if any gate fails, #146 closes as a completed one-shot experiment and #76
  remains open with the immutable negative result;
- if development fails, #146 remains unresolved or closes with a development
  blocker, but no holdout evidence exists and no qualification claim is made.

Documentation remains sentence-only and must not claim paragraph support, a
qualified production model, or runtime-release authority.

## Error handling

Schema, identity, digest, artifact, offset, reconstruction, channel, privacy,
platform, sandbox, network, process, socket, resource, stability, freeze, and
reservation violations fail closed with non-zero status. Error messages use
privacy-safe identifiers and never include analyzed or expected text.

## Testing and review

Tests are written before implementation and cover:

- exact v2 configuration and approval identities;
- strict 80/160 split isolation and absence of holdout reads in development;
- runner/source and scorer/gold separation;
- exact Unicode offsets, reconstruction, and channel separation;
- non-vacuous metric semantics and all unchanged thresholds;
- protected negatives and optional-component failure;
- private-data rejection in reports and errors;
- complete freeze hashing and development-decision recomputation;
- atomic durable reservation, mismatch rejection, interruption behavior, and
  permanent repeat denial;
- artifact contents, clean offline installation, import origin, sandbox,
  network, sockets, processes, RSS, swap, and stable repetitions;
- proof that all corpus-v3, safety-v1, #115 marker/report/result/digest, and
  corpus-v2 source artifacts remain unchanged.

Before the irreversible phase, focused synthetic and hash-based corpus-v2
validation, the full
fast pytest suite, Ruff lint and format checks, mypy, distribution audits, real
vendored integration, clean installations, both development repetitions, and
an independent review must pass. A second independent review checks the final
aggregate report and #76 disposition before publication and merge.

After reservation, no test or verification command may load corpus-v2 raw
records or case-level gold. Post-result checks are limited to frozen hashes,
marker/report metadata, aggregate schema, source code, and unrelated fast
runtime tests.
