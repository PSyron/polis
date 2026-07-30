# Quick-start for Polis

This project is runtime-first and offline: the default analyzer runs in-process
and does not send input to external services. No tested local model has
qualified for production correction or suggestions.

The default installation contains no production model or LanguageTool
dependency. LanguageTool is an optional local adapter with narrow, sentence-only
coverage; enable it only through an explicit caller-supplied loopback service or
the separately built vendored executable. Polis does not include DOCX/ODT/RTF
adapters, a GUI, or stylistic rewriting.

## Install dependencies

```console
uv sync --locked --extra dev
```

## API usage

```python
from polis import Analyzer, AnalyzerConfig, AnalysisOptions

analyzer = Analyzer(AnalyzerConfig())
result = analyzer.analyze("Witaj, świecie.")

options = AnalysisOptions(categories={"spelling", "punctuation"}, minimum_confidence=0.5)
filtered = analyzer.analyze("Witaj, świecie.", options=options)
print(len(filtered.issues))
```

## CLI usage

```console
python -m polis.cli analyze --json "Witaj,świecie."
printf 'Witaj,świecie.' | python -m polis.cli analyze --stdin --json
```

## Apply selected findings

```python
result = analyzer.analyze("Witaj,świecie.")
first = result.issues[0].id
corrected = result.apply((first,))
print(corrected)
```

Automatic correction is conservative: only covered, high-confidence,
non-conflicting deterministic findings are applied. Model and contextual
findings remain reviewable until the caller selects them explicitly.

Research corpora, benchmark runners, and holdout workflows are repository-only
development assets. Run them through the commands in the research workflow
guide, not as part of the default runtime quick start. `polis.evaluation`
remains an import-compatible evaluator namespace for the current 0.x line; it
is not the primary analysis API.
