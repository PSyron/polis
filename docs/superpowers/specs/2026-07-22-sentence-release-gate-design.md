# Installed-package sentence release gate design

## Scope

Issue #76 proves the behavior of the installable Polis package on individual
Polish sentences. It does not evaluate paragraphs and does not convert the
absence of a qualified local model into a model success. The gate covers the
currently implemented stack: built-in deterministic rules, the qualified local
LanguageTool punctuation subset, contextual inflection suggestions, and the
reviewable residual syntax rules.

The evaluator selects only corpus-v3 records with `unit == "sentence"`. Gold
edits, categories, expected output, and protected-negative labels are made
available only to scoring after analysis. Runtime construction receives the
source sentence and a frozen local configuration.

## Options considered

1. Replace #64 with a sentence-only gate. This loses the deferred paragraph
   requirements and makes future completion harder to audit.
2. Add an independent sentence gate and retain #64 for paragraphs. This is the
   selected option because it produces a complete, releasable unit without
   weakening or deleting the broader requirements.
3. Add a sentence mode inside #64. This leaves the result formally blocked by
   #43 and mixes completed sentence evidence with unfinished paragraph work.

## Components

### Frozen configuration

`experiments/sentence_release_gate/config.json` identifies corpus-v3 by SHA-256,
sets `sentence_only` to `true`, records source-policy version `1.1`, enumerates
the allowed automatic and reviewable sources, and declares all quality and
performance gates. It pins the LanguageTool 6.8 upstream revision and the
source-built local module identity but never names a model in core or public
data structures.

`frozen_gate.json` records hashes for the configuration, evaluator, installed
runner, relevant source-policy implementation, corpus, local LanguageTool
bridge, distributions, and the canonical closed-schema development report.
Before reservation, the evaluator verifies those identities and the report
digest and recomputes the development gates instead of trusting its serialized
decision flag. A holdout marker is created exclusively before the evaluator
loads any holdout record. A second reservation fails closed.

### Installed runner

`scripts/run_sentence_release_case.py` is invoked with the Python executable
from a clean wheel installation and from a working directory outside the
repository. It imports `polis` from that environment, verifies that the import
origin belongs to that installation, constructs one `Analyzer` from explicit
local-only configuration, and then processes one versioned request per input
line until EOF. It writes exactly one versioned JSON response per request. The
persistent runner is required to measure warm installed-package behavior while
reusing the single analyzer-owned LanguageTool process introduced by #77.

The request contains only the source sentence and local endpoint or executable
configuration. The response contains validated public result fields required
for scoring: findings, automatic findings, reviewable findings, corrected text,
explicitly selected corrected text, suggestion outcomes, elapsed time, process
RSS, and model-call count. Diagnostic errors contain no analyzed text.

The runner rejects zero or multiple sentences before analysis. It accepts only
an absolute executable path for the combined vendored LanguageTool stdio
service. No artifact is downloaded or updated implicitly.

### Evaluator and scorer

`experiments/sentence_release_gate/run_evaluation.py` owns corpus selection,
installed runner orchestration, exact-edit validation, metrics, privacy-safe
evidence, freeze verification, and one-shot holdout reservation. It never
imports the repository `src/polis` package into the installed subprocess.

For every case it validates each finding against the original sentence:

- `0 <= start <= end <= len(source)`;
- `source[start:end] == original`;
- the edit uses Unicode code-point half-open offsets;
- edits within one application set do not overlap or conflict;
- applying automatic findings reconstructs the runner's `corrected_text`;
- applying automatic plus explicitly selected reviewable findings reconstructs
  the runner's selected result.

Scoring compares exact `(start, end, original, suggestion)` values without using
the reported category or source to decide correctness. Category and source are
used only to break down already computed true positives, false positives, and
false negatives.

Automatic and reviewable channels are disjoint. Findings covered by source
policy `1.1` belong to the automatic channel; residual syntax and contextual
inflection findings belong to the reviewable channel. Model-generated findings,
if any are injected in a future configuration, remain reviewable regardless of
confidence.

### Reports

Development runs first. It qualifies only when:

- at least one automatic edit and at least one reviewable edit are proposed;
- automatic exact-edit precision is `1.00`;
- automatic correction accuracy among changed cases is `1.00`;
- reviewable exact-edit precision is at least `0.90`;
- structured outcome validity is `1.00`;
- neither channel changes a protected hard negative;
- all offsets and reconstructed outputs validate;
- measured performance remains within the frozen Mac mini thresholds.

Only a qualifying development report may freeze the gate and reserve holdout.
The same gates apply independently to the one-shot holdout. Recall is reported
by category and source but has no minimum because Polis prefers an abstention to
an unjustified correction. A channel proposing zero holdout edits fails its
non-vacuous precision gate.

The committed report contains case IDs, counts, source identifiers, categories,
hashes of edit records, timings, memory measurements, call counts, environment
identity, and decisions. It contains no source sentence, expected output,
original span text, suggestion text, raw response, or private path.

## Optional local components

The gate starts the single vendored LanguageTool stdio service from an explicit
local executable. The analyzer-owned session serves both the allowlisted
punctuation checks and contextual morphology, so there is one process and no
HTTP listener. This is an optional production component, but the full sentence
gate requires it because it evaluates the complete qualified sentence stack. A
separate failure-path run replaces the service with a failing local executable
and verifies that built-in deterministic findings remain intact while both
optional sources abstain safely.

The installed runner reads the analyzer-owned session's public measured process
start count. Zero starts or a restart count other than one fails the frozen gate;
configuration alone is not accepted as evidence of persistence.

The current executable evidence profile is explicitly `macos-arm64-v1`. The
installed runner and every child execute inside a macOS sandbox that denies
all network operations. Proxy variables are removed, and socket inspection
remains independent corroborating evidence. The evaluation path uses stdio only
and therefore permits zero network sockets. Linux and Windows fail closed before
evaluation or reservation; either needs a separate platform-native evidence
profile and cannot inherit the macOS result. Before reserving holdout, a native
preflight proves local subprocess execution under the sandbox, denied network,
and usable `ps`, `lsof`, `sysctl`, pipe-readiness, RSS, socket, and swap evidence.
The socket audit must observe a known listening loopback socket; `lsof` errors
cannot be treated as a valid zero-socket result.

All reversible holdout-independent work finishes before reservation: audited
wheel and sdist installation, installed-sdist smoke, optional-component fallback
evaluation, and installed-runner construction. Reservation occurs immediately
before loading and evaluating the holdout, so setup failure cannot consume the
one-shot run.

## Performance evidence

The runner records a cold first sentence and warm measurements for all remaining
sentences. The report includes p50 and p95 latency, cases and characters per
second, loaded Python RSS, peak Python RSS, LanguageTool process RSS, combined
peak RSS, and model calls per sentence. Since no real model is qualified, the
expected model-call count is exactly zero; this is reported as the current
configuration, not as evidence that model correction works.

The frozen target thresholds are conservative relative to existing evidence:
warm p95 at most `100 ms` for in-process rules excluding optional service start,
warm end-to-end p95 at most `500 ms`, combined peak RSS at most `1 GiB`, no
swap growth, and zero model calls. Cold service startup is measured and reported
but does not share the warm latency threshold.

## Packaging and documentation

The gate builds wheel and sdist, validates their content allowlists, installs
each without dependencies into a clean environment, and runs public API smoke
tests. Neither artifact may contain model weights, caches, corpus-v3, Java build
products, optional runtime dependencies, or private text.

Documentation updates cover quick start, public API, offline setup, quality and
performance evidence, privacy, limitations, changelog, roadmap, and release
checklist. Every statement is explicitly sentence-only. #64 retains paragraph
coverage, and #43 retains the production-model qualification requirement.

## Error handling

Configuration mismatch, artifact hash mismatch, invalid runner JSON, invalid
offset, conflicting edit, leaked text in a report, unavailable installed
package, unexpected non-loopback access, failed development gate, or repeated
holdout reservation stops the run with a non-zero exit. Optional component
failure during a dedicated fallback case is an expected observation only when
the deterministic result remains complete and privacy-safe.

## Testing strategy

Tests are added before implementation for configuration closure, sentence-only
selection, gold isolation, runner protocol, offset validation, exact scoring,
channel separation, non-vacuous gates, privacy-safe reports, freeze hashes,
one-shot holdout, optional failure, installed-wheel execution, and deterministic
repeatability. The final verification runs Ruff, format check, strict mypy,
complete pytest, real local LanguageTool integration, offline network denial,
wheel/sdist build and clean installation, artifact-content verification, and
the frozen development and holdout evaluations.
