# Quick-start for Polis

This project is offline-first: analysis runs in-process and does not require sending input
to external services.

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

