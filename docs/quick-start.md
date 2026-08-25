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

## Cykl życia i współbieżność

`Analyzer` zbuduj raz i przechowuj przez cały czas życia procesu lub obsługującego
go komponentu. Nie twórz analizatora przy każdym żądaniu: pomiar referencyjny dla
issue #421 (commit `bb842fe`) wyniósł 34,5 ms na import `polis`, 23,8 ms na
konstrukcję `Analyzer`, 1,0 ms na pierwszą analizę oraz 0,047 ms na ciepłą analizę.
Wartości zależą od sprzętu i środowiska, ale konstrukcja ładuje stan dostawcy
morfologii, a kolejne analizy korzystają z już zbudowanego rejestru reguł.

```python
from polis import Analyzer, AnalyzerConfig

analyzer = Analyzer(AnalyzerConfig())

def handle_text(text: str) -> str:
    return analyzer.analyze(text).to_json()
```

Jedna instancja `Analyzer` jest bezpieczna wątkowo dla współbieżnych wywołań
`analyze()` i `correct()`. Możesz współdzielić ją między wątkami; nie potrzebujesz
blokady ani puli instancji. Nie modyfikuj konfiguracji ani prywatnego stanu
analizatora po konstrukcji. Domyślny runtime nie posiada zasobów wymagających
zamykania; `close()` oraz kontekst `with` są zachowane jako zgodnościowy no-op.

Zobacz [przykład TOML](../examples/polis.toml), [reguły](rules.md) i
[publiczne API](public-api.md). Polis działa offline i wstrzymuje się, gdy
zmiana wymaga interpretacji znaczenia tekstu.
