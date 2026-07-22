# Contextual Polish inflection routing

Issue #71 evaluates one Polish sentence at a time. A source-only detector finds
closed government or adjacent-name relations, and the pinned local
LanguageTool 6.8 tagger/synthesizer supplies every finite form. The ranker
selects a unique constrained form or abstains. It never receives a corpus ID,
stratum, tag, expected output, or gold span.

## Frozen route

The route recognizes:

- surname agreement with the case, number, and compatible gender of an
  adjacent already-inflected first name;
- singular genitive after `bez` for one noun or an adjective-noun pair;
- singular dative after a `przygląd… się` form for the same narrow phrase;
- singular dative after a `podzięk…` form for one capitalized first name.

The experimental `synthesize_context` operation preserves complete upstream
morphological tags in addition to the existing merged feature list. The
original `synthesize` response and its candidate identifiers remain unchanged.
Every proposal cites a visible `ltpl:` candidate ID derived from its complete
record.

| Split | TP / FP / FN | Precision / supported recall | Protected changes | Warm p95 | Peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Development (69 sentences) | 13 / 0 / 8 | 1.000 / 0.619 | 0 | 3.84 ms | 339,886,080 B |
| Holdout (142 sentences) | 10 / 0 / 5 | 1.000 / 0.667 | 0 | 4.19 ms | 326,877,184 B |

Development target detection covered 19/20 inflection-stratum edits. Holdout
covered 15/45 because the closed patterns intentionally exclude other
government and verbal-agreement shapes. Among detected holdout targets,
surname recall was 0.714. First-name ambiguity caused abstention, and the one
supported ordinary-word holdout edit was missed. These zero-denominator or
single-case slices are reported without claiming broader coverage.

The built runtime occupied 54,073,873 bytes. The committed report contains
identifiers, hashes, counts, timings, and booleans only; it contains no source
sentences, expected forms, raw responses, or private text.

## Reproduction

Build offline, run development, and freeze all routing and scoring inputs:

```bash
POLIS_LT_OFFLINE=1 third_party/languagetool-pl/scripts/build.sh
uv run --locked --extra dev python -m \
  experiments.contextual_inflection_routing.run_benchmark \
  --output experiments/contextual_inflection_routing/report.json \
  --freeze experiments/contextual_inflection_routing/frozen_router.json
```

The holdout command atomically creates its marker and refuses a second run:

```bash
uv run --locked --extra dev python -m \
  experiments.contextual_inflection_routing.run_benchmark \
  --output experiments/contextual_inflection_routing/report.json \
  --holdout \
  --frozen experiments/contextual_inflection_routing/frozen_router.json \
  --holdout-marker experiments/contextual_inflection_routing/holdout.started
```

This experiment qualifies a suggestion source. It does not register or
automatically apply the router in the analyzer.
