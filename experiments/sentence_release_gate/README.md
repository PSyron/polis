# Installed-package sentence release gate

This experiment evaluates only reviewed corpus-v3 records whose unit is
`sentence`. The analyzer runs from a clean wheel installation outside the
repository and uses one explicit, local LanguageTool 6.8 stdio executable. Gold
edits remain in the repository-side scorer and are never sent to the installed
runner.

The runner exercises all three public correction paths:

- `Analyzer.analyze()`;
- conservative `Analyzer.correct()`;
- explicit `CorrectionResult.apply_suggestions()`.

Automatic and reviewable findings are scored separately as exact Unicode
`[start, end)` edits. Reports retain identifiers, counts, hashes, source names,
and measurements but no analyzed or corrected text.

The executable qualification profile is `macos-arm64-v1`. It owns native
`sandbox-exec`, `ps`, `lsof`, `sysctl`, and pipe-readiness evidence. Linux and
Windows fail closed before development or holdout execution; they require a
separate accepted platform profile and cannot inherit macOS evidence.

## Development result

The 2026-07-22 development run evaluated 69 sentences twice and qualified:

- automatic edit precision: `1.00` (`6 TP`, `0 FP`);
- automatic correction accuracy: `1.00`;
- reviewable edit precision: `1.00` (`18 TP`, `0 FP`);
- protected automatic changes: `0`;
- protected reviewable findings: `0`;
- warm in-process and installed-runner p95: below their `100 ms` and `500 ms`
  gates;
- combined peak RSS: below the `1 GiB` gate;
- analyzer-owned LanguageTool process starts: measured `1`;
- network access denied by the macOS sandbox; observed sockets, swap growth,
  and model calls: `0`;
- stable repetitions: `2 / 2`.

Exact timing, throughput, loaded RSS, and peak RSS values are recorded in
`report.json`. Per-category metrics report channel precision and recall;
per-source recall uses all gold edits as its explicit contribution denominator.
The report is generated after the audited artifacts and is intentionally excluded
from those artifacts, avoiding self-referential distribution hashes.

The completed paired-comma rules supply both exact edits for the two affected
sentences without broadening their reviewed shapes. The qualifying development
report was frozen before the independently reviewed one-shot holdout.

The development report SHA-256 is recorded in `frozen_gate.json`.
Holdout authorization revalidates configuration and artifact identities, recomputes
every quality gate, verifies that report digest, and only then creates the
one-shot marker. Before that irreversible step it completes wheel/sdist
installation, sdist smoke, fallback evaluation, and runner construction. A
native capability preflight runs a known loopback listening socket through the
process-tree `lsof` audit, rejects audit errors, verifies resource/swap/pipe
evidence, and proves that the sandbox permits local subprocesses while denying
network creation. Only unavoidable holdout evaluation follows reservation.

## One-shot holdout result

The single authorized holdout evaluated 142 sentences twice. It did not
qualify:

- automatic edit precision: `1.00` (`5 TP`, `0 FP`);
- holdout automatic correction accuracy: `0.80` (required `1.00`);
- reviewable edit precision: `1.00` (`10 TP`, `0 FP`);
- reviewable correction accuracy: `1.00`;
- protected automatic changes and reviewable findings: `0`;
- warm in-process p95: `8.491 ms`;
- warm end-to-end p95: `8.676 ms`;
- combined peak RSS: `429,572,096 bytes`;
- measured process starts: `1`;
- observed sockets, swap growth, and model calls: `0`;
- stable repetitions: `2 / 2`.

One of the five automatically changed holdout cases did not reconstruct its
complete reviewed correction, despite every proposed edit being exact. The
gate therefore rejected the configuration without weakening its threshold.
`holdout.started` records the consumed reservation; this holdout cannot be rerun
or used for tuning. The top-level sentence-only decision remains unqualified.

## Reproduction

Build the already bootstrapped vendored runtime without network access:

```bash
POLIS_LT_OFFLINE=1 third_party/languagetool-pl/scripts/build.sh
python -m build --no-isolation --outdir /tmp/polis-sentence-release-dist
```

Run development from the repository root:

```bash
PYTHONPATH="$PWD/src:$PWD" python -m experiments.sentence_release_gate.run_evaluation \
  --development \
  --config experiments/sentence_release_gate/config.json \
  --dist /tmp/polis-sentence-release-dist \
  --vendored-stdio "$PWD/third_party/languagetool-pl/scripts/run_stdio.sh" \
  --output experiments/sentence_release_gate/report.json \
  --freeze experiments/sentence_release_gate/frozen_gate.json
```

The command exits non-zero and does not freeze when any development gate fails.
The documented holdout has already been consumed exactly once and cannot be
reproduced with the same marker.
