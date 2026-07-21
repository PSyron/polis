# Deterministic Polish inflection candidate experiment

This experiment evaluates the real LanguageTool 6.8 Polish tagger and
synthesizer included in `third_party/languagetool-pl`. It generates finite,
auditable forms for explicit source spans. It does not decide which form fits
the sentence and never applies a correction.

## Contract

The local newline-delimited JSON request contains only the source text and
Unicode half-open spans:

```json
{"operation":"synthesize","language":"pl-PL","text":"Paweł","spans":[{"start":0,"end":5}]}
```

Each candidate has a content-derived `ltpl:` ID, the unchanged original range,
an optional lemma, a form, and sorted morphological features. Identical forms
from ambiguous analyses are merged; the lemma becomes `null` when analyses
disagree. The original surface is always present. `no-analysis`,
`unsupported-pos`, and `no-alternatives` are explicit outcomes and never cause
an invented alternative.

The bridge supports noun (`subst`) and adjective (`adj`) analyses. This covers
ordinary nouns/adjectives, first names, and nominal or adjectival surnames in
corpus v3. Capitalization is mapped from the source surface, including uppercase
inputs, and Polish diacritics are preserved.

## Reproduction

Build and verify the pinned Java module entirely from its local cache:

```bash
cd third_party/languagetool-pl
POLIS_LT_OFFLINE=1 ./scripts/build.sh
./scripts/verify.sh
```

Run the real integration test and benchmark from the repository root:

```bash
POLIS_LT_VENDOR_INTEGRATION=1 uv run pytest \
  tests/test_inflection_candidate_benchmark.py -q
uv run python -m experiments.inflection_candidates.run_benchmark
```

The runner processes the authored fixture first, then all eligible single-token
inflection edits from both frozen corpus-v3 splits in one warm stdio process.
Gold supplies only the target span and expected-form oracle. It is not sent as
a lemma, tag, form, or candidate. Reports contain case IDs and aggregate counts,
not source or expected text.

## Results

- Date: 2026-07-21
- LanguageTool: 6.8, commit
  `e807fcde6a6506191e1470744d2345da28c26be6`
- Corpus SHA-256:
  `bd2c186bb22e32f948ed6592c24bc2267c6a2a77b185bd9424310068e680a1f2`
- Authored fixture SHA-256:
  `939a3b9f42274d7307fbe51d9474392ce57cd0cd028fd1a028ab9a56db50380d`
- Runtime: OpenJDK 17.0.19, macOS 15.3.1, Apple M4 Mac mini, 16 GB

| Dataset / class | Cases | Expected recall | Unchanged coverage | Unsupported | Mean / p95 forms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Authored / ordinary | 4 | 1.000 | 1.000 | 1 | 16.5 / 41 |
| Authored / first name | 3 | 1.000 | 1.000 | 1 | 12.0 / 21 |
| Authored / surname | 2 | 1.000 | 1.000 | 0 | 10.5 / 11 |
| Development / ordinary | 10 | 1.000 | 1.000 | 0 | 23.5 / 41 |
| Development / first name | 1 | 1.000 | 1.000 | 0 | 14.0 / 14 |
| Development / surname | 13 | 1.000 | 1.000 | 0 | 11.1 / 16 |
| Holdout / ordinary | 17 | 1.000 | 1.000 | 0 | 18.9 / 33 |
| Holdout / first name | 1 | 1.000 | 1.000 | 0 | 10.0 / 10 |
| Holdout / surname | 16 | 1.000 | 1.000 | 0 | 10.8 / 19 |

The two authored unsupported cases are intentional controls: an unknown token
and an indeclinable name. Both retain their original form and do not trigger a
change. All 58 eligible corpus edits contain the expected form, and all 58
candidate sets contain the source form.

| Runtime measurement | Result |
| --- | ---: |
| Cold process plus first synthesis | 566.4 ms |
| Authored warm p50 / p95 | 1.09 / 7.15 ms |
| Development warm p50 / p95 | 1.44 / 2.68 ms |
| Holdout warm p50 / p95 | 0.89 / 1.75 ms |
| Peak RSS | 367,099,904 bytes (350.1 MiB) |
| Thin JAR plus runtime libraries | 54,072,194 bytes (51.6 MiB) |
| Included Polish resources | 8,821,678 bytes (8.4 MiB) |

## Licensing, packaging, and limitations

The LanguageTool derivative remains LGPL-2.1-or-later and runs as a separate
optional local process. Corresponding source, license, and notices remain in
`third_party/languagetool-pl`; the module stays excluded from Python wheels and
source distributions. The Polish analysis and synthesis dictionaries are
PoliMorf/Morfologik resources under the preserved BSD-2-Clause notice in
`org/languagetool/resource/pl/README.txt`.

LanguageTool is selected as the deterministic candidate source. A Morfeusz 2
comparison is not justified now because every required corpus class reached
full expected-form recall and unchanged coverage. The remaining problem is
contextual ranking, not morphology coverage. Candidate sets can still be wide
(ordinary-word p95 up to 41 distinct forms), so a later rule or model must
narrow or rank them and may never interpret synthesis alone as correctness.
