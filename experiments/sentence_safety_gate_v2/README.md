# Sentence safety gate v2 (#146)

This sentence-only optional research experiment evaluates the installed Polis
package against the independent, approved safety corpus v2. It freezes source
policy `1.2`, the active automatic and reviewable source sets, the vendored
LanguageTool 6.8 runtime, the `macos-arm64-v1` platform profile, and the
unchanged gates owned by #76. Preparing this experiment does not qualify a
production model and does not qualify paragraph behavior.

The one permitted development audit ran over exactly 80 development cases in
two stable repetitions and was not qualified. It produced the immutable,
aggregate-only `report.json` with SHA-256
`7485c543a5abcfe45096cfc9334b59cf4c5dd510186c6318a44d0c38cdeb1141`.
There is no frozen gate. `holdout.started` remains absent, and the holdout was
not reserved, materialized, or run. No development rerun or tuning is allowed,
#76 remains open, and Task 6 is forbidden.

The manifest records a cycle-free pre-evaluation tree independently of the
current `HEAD`. A hermetic temporary Git index always starts from pinned base
commit `3035eb201f48bd84a5ada364ae41a96293259e50`, applies the SHA-bound zero-context
forward Git patch `pre_evaluation_inputs.patch`, and verifies a closed mapping of all 12
changed paths, statuses, modes, and target blobs before `git write-tree` must
equal `5162007cfc9eac13aed415256ee698e5d0c5de4b`. The patch contains every byte
needed to materialize the input tree; it does not read `HEAD` or current files.
An alternate `HEAD` with added upstream paths therefore reconstructs the same
tree. Unknown changes, hash drift, patch failure, mode drift, blob drift, or Git
errors are hard failures.

The final manifest, aggregate report, outcome documentation, provenance patch,
post-evaluation audit tests, and import/type/configuration hygiene edits are not
claimed as evaluated inputs. The forward patch retains the actual
pre-evaluation test blob
`b149a2c702311f9a5cc5da6926c2d8f1c5bdbfb1` and evaluator blob
`f54e0c848c570b2dab7bce76928b67b17478c601`. The later hygiene edits only sort
imports, add a static `cast`, and make Ruff and mypy include the v2 package;
they do not change runtime behavior or the recorded result.

## Reversible commands

Build the vendored runtime offline, then build one fresh wheel and one source
distribution in the ignored experiment directory before running these commands.

Run platform, offline-installation, privacy, and resource preflight without
loading corpus cases:

```console
uv run --locked --extra dev python \
  -m experiments.sentence_safety_gate_v2.run_evaluation \
  --preflight \
  --config experiments/sentence_safety_gate_v2/config.json \
  --dist "$PWD/.superpowers/issue-146-dist" \
  --vendored-stdio "$PWD/third_party/languagetool-pl/scripts/run_stdio.sh"
```

The following command was run once over the 80 development cases. It must not
be rerun. It writes a freeze only when every development gate passes; this run
did not pass and therefore wrote no frozen gate:

```console
uv run --locked --extra dev python \
  -m experiments.sentence_safety_gate_v2.run_evaluation \
  --development \
  --config experiments/sentence_safety_gate_v2/config.json \
  --dist "$PWD/.superpowers/issue-146-dist" \
  --vendored-stdio "$PWD/third_party/languagetool-pl/scripts/run_stdio.sh" \
  --output experiments/sentence_safety_gate_v2/report.json \
  --freeze experiments/sentence_safety_gate_v2/frozen_gate.json
```

The planned metadata verification below was not run because no frozen gate was
created. It is retained only as the rejected workflow step and must not be run:

```console
uv run --locked --extra dev python \
  -m experiments.sentence_safety_gate_v2.run_evaluation \
  --verify-development \
  --config experiments/sentence_safety_gate_v2/config.json \
  --dist "$PWD/.superpowers/issue-146-dist" \
  --vendored-stdio "$PWD/third_party/languagetool-pl/scripts/run_stdio.sh" \
  --output experiments/sentence_safety_gate_v2/report.json \
  --freeze experiments/sentence_safety_gate_v2/frozen_gate.json
```

The real marker remained absent throughout these steps.

## Development result

The two stable repetitions produced the same aggregate outcome. The automatic
channel recorded 20 true positives, 40 false negatives, no false positives,
precision `1.00`, recall `0.3333333333333333`, and correction accuracy `1.00`.
The reviewable channel proposed no edits, recorded 60 false negatives and no
false positives, and had recall `0.00`; its precision was null, so the required
non-vacuous reviewable gate did not pass. Structured outcome validity was
`1.00`, and protected automatic changes and reviewable findings were both zero.
All recorded privacy and performance evidence remained within its unchanged
limits. These aggregates do not expose sentence, edit, identifier, or raw
runtime evidence.

## Irreversible command

Issue #146 would have carried autonomous authorization for the command below
only after qualifying development, frozen verification, and independent review.
Development did not qualify and no freeze exists, so `--holdout` is not
authorized and must not be run. Had every condition passed, the one-shot command
would have run without prompting. Task 6 is forbidden.

```console
uv run --locked --extra dev python \
  -m experiments.sentence_safety_gate_v2.run_evaluation \
  --holdout \
  --config experiments/sentence_safety_gate_v2/config.json \
  --dist "$PWD/.superpowers/issue-146-dist" \
  --vendored-stdio "$PWD/third_party/languagetool-pl/scripts/run_stdio.sh" \
  --output experiments/sentence_safety_gate_v2/report.json \
  --frozen experiments/sentence_safety_gate_v2/frozen_gate.json \
  --holdout-marker experiments/sentence_safety_gate_v2/holdout.started
```

Once marker creation is attempted, the holdout is permanently consumed even
if the process fails or is interrupted. Repetition, tuning, marker replacement,
and early access are forbidden. There is no recovery command and no retry path.
Only aggregate report metadata may be inspected after reservation.
