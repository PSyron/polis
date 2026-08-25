# Szybki start

```python
from polis import analyze, correct

analysis = analyze("Ona jestem tutaj.")
correction = correct("Zeby jutro,powiem o tym.")

assert analysis.issues
assert correction.corrected_text == "Żeby jutro, powiem o tym."
```

`analysis.issues` zawiera `Finding` z kategorią, opisem, minimalną sugestią,
źródłem, pewnością oraz zakresem `[start, end)`. `correct()` zwraca
`CorrectionResult`; korekta automatyczna obejmuje tylko niekolidujące,
zakwalifikowane zachowania. Wybór pozostałej sugestii jest jawny:

```python
reviewed = correction.apply_suggestions(
    [finding.id for finding in correction.skipped_findings]
)
```

Funkcje modułowe są wygodne dla pojedynczych wywołań i pamiętają analizator
leniwie, osobno dla każdej konfiguracji. Przy większej liczbie tekstów jawnie
utwórz jeden analizator i używaj go ponownie:

```python
from polis import Analyzer, AnalyzerConfig

analyzer = Analyzer(AnalyzerConfig())
analysis = analyzer.analyze("Ona jestem tutaj.")
correction = analyzer.correct("Zeby jutro,powiem o tym.")
```

Konfiguracja z pliku jest lokalna:

```python
from polis import Analyzer

analyzer = Analyzer.from_config("polis.toml")
```

Zobacz [przykład TOML](../examples/polis.toml), [reguły](rules.md) i
[publiczne API](public-api.md). Polis działa offline i wstrzymuje się, gdy
zmiana wymaga interpretacji znaczenia tekstu.
